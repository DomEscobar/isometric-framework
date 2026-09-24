"""Opt-in, durable, step-driven corrections; never edits sources, layout or collision.
Each next attempt requires the previous job's reviewed new candidate. No blind retry.
"""
import json
from pydantic import Field
from fastapi import HTTPException
from artifacts import canonical,digest
from style_specs import Strict,Hash
from evaluations import PaidReview

class CorrectionRequest(Strict):
    evaluation_id: Hash
    enabled: bool=False
    max_attempts: int=Field(default=1,ge=1,le=3)
class CorrectionStep(PaidReview):
    evaluation_id: Hash

class Corrections:
    def __init__(self,g,evaluations,submit):
        self.g=g;self.evaluations=evaluations;self.submit=submit
        with g.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS corrections(id TEXT PRIMARY KEY,record TEXT NOT NULL)')
    def actionable(self,ev):
        if ev['status']!='reviewed' or ev['gate']['production_approved'] or not ev['gate']['findings']:raise ValueError('no-op: reviewed actionable findings required')
        findings=[f for f in ev['gate']['findings'] if f.get('correction') and f.get('blocking')]
        if not findings:raise ValueError('no-op: no blocking structured corrections')
        return findings
    def create(self,request):
        if not request.enabled:raise ValueError('explicit opt-in required; auto-repair defaults OFF')
        ev=self.evaluations.get(request.evaluation_id);self.actionable(ev)
        initial=dict(request=request.model_dump(),layout_revision=ev['binding']['layout_revision'],style_spec_id=ev['binding']['style_spec_id'],candidate_id=ev['binding']['candidate_id'],shared_project_budget_usd=self.g.policy['total_usd'])
        cid=digest(canonical(initial));w=dict(id=cid,initial=initial,status='ready',attempts=[])
        with self.g.connect() as db:db.execute('INSERT OR IGNORE INTO corrections VALUES (?,?)',(cid,canonical(w).decode()))
        return self.get(cid)
    def get(self,cid):
        with self.g.connect() as db:row=db.execute('SELECT record FROM corrections WHERE id=?',(cid,)).fetchone()
        if not row:raise ValueError('correction missing')
        w=json.loads(row[0])
        if w['id']!=cid or digest(canonical(w['initial']))!=cid:raise ValueError('correction binding drift')
        return w
    def step(self,cid,eid):
        ev=self.evaluations.get(eid);findings=self.actionable(ev)
        with self.g.connect() as db:
            db.execute('BEGIN IMMEDIATE');w=self.get(cid)
            if w['status'] in ('preparing','ambiguous','blocked'):raise ValueError('ambiguous/blocked attempt cannot be retried')
            if len(w['attempts'])>=w['initial']['request']['max_attempts']:raise ValueError('correction attempt cap reached')
            if ev['binding']['layout_revision']!=w['initial']['layout_revision']:raise ValueError('canonical geometry change forbidden')
            if ev['binding']['style_spec_id']!=w['initial']['style_spec_id']:raise ValueError('style change needs separate opt-in workflow')
            if not w['attempts']:
                if eid!=w['initial']['request']['evaluation_id']:raise ValueError('wrong initial evaluation')
            else:
                j=self.g.get(w['attempts'][-1]['job_id'])
                if j['status']!='candidate_ready' or ev['binding']['candidate_id']!=j['candidate_id']:raise ValueError('previous new candidate must be imported and reviewed first')
                prev=self.evaluations.get(w['attempts'][-1]['evaluation_id'])
                if ev['binding']['source_sha256']==prev['binding']['source_sha256']:raise ValueError('no-op: unchanged source cannot trigger another purchase')
            if any(a['evaluation_id']==eid for a in w['attempts']):raise ValueError('no-op: evaluation already attempted')
            prompt='Correct ONLY these structured visible findings while preserving the exact canonical layout, registration contract and all collision geometry. Do not add upright props. '+canonical(findings).decode()
            attempt=dict(evaluation_id=eid,prompt_sha256=digest(prompt.encode()),job_id=None)
            w['attempts'].append(attempt);w['status']='preparing'
            db.execute('UPDATE corrections SET record=? WHERE id=?',(canonical(w).decode(),cid))
        try:
            job=self.submit(w,prompt)
            attempt['job_id']=job['id'];w['status']=job['status']
        except Exception:
            w['status']='blocked';w['error']='Blocked or ambiguous preparation. No retry; inspect central job/receipt and reservations.'
        with self.g.connect() as db:db.execute('UPDATE corrections SET record=? WHERE id=?',(canonical(w).decode(),cid))
        return self.get(cid)


def install(app,files):
    g=app.state.generation;styles=app.state.styles
    def submit(w,correction):
        sid=w['initial']['style_spec_id'];refs=styles.inputs(sid);rid=w['initial']['layout_revision'];guide=files(rid)['clean-guide.png']
        binding=dict(layout_revision=rid,guide_sha256=digest(guide),style_spec_id=sid,style_id=refs[0]['reference_id'],style_sha256=refs[0]['input_sha256'],style_references=[{k:v for k,v in r.items() if k!='raw'} for r in refs],prompt=styles.prompt(sid)+'\n'+correction,correction_id=w['id'],correction_evaluation_id=w['attempts'][-1]['evaluation_id'])
        q=g.quote(binding)
        # Generation's existing transaction enforces SAME total budget and generation cap.
        return g.confirm(q['id'],rid,guide,refs[0]['raw'],[r['raw'] for r in refs[1:]])
    service=Corrections(g,app.state.evaluations,submit);app.state.corrections=service
    def guarded(fn):
        try:return fn()
        except (ValueError,KeyError,FileNotFoundError):raise HTTPException(409,'Correction disabled, no-op, stale, capped or unresolved; no automatic retry.') from None
    @app.post('/api/corrections',status_code=201)
    def create(body:CorrectionRequest):return guarded(lambda:service.create(body))
    @app.get('/api/corrections/{cid}')
    def read(cid:str):return guarded(lambda:service.get(cid))
    @app.post('/api/corrections/{cid}/step')
    def step(cid:str,body:CorrectionStep):return guarded(lambda:service.step(cid,body.evaluation_id))
