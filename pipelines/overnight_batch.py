"""Scoped two-style experiments; original auto_runs and central holds are untouched.
Conservative policy: ONE initial image per style; failed reviews stop, never repair.
"""
import json
import fcntl
import time
import threading
from typing import Literal
from pydantic import Field, model_validator
from artifacts import canonical, digest
from evaluations import PaidReview
from style_specs import Hash
from pathlib import Path
from decimal import Decimal
from auto_adapter import Adapter


class BatchAdapter(Adapter):
    def __init__(self,*args,authorization_path=None,reference_paths=None):
        super().__init__(*args)
        self.authorization_path=Path(authorization_path or Path(__file__).with_name('OVERNIGHT_TWO_STYLE_AUTHORIZATION.md'))
        self.reference_paths=[Path(p) for p in (reference_paths or ['/root/.hermes/cache/images/img_6c8d5452390d.jpg','/root/.hermes/cache/images/img_632abdd839ed.jpg'])]

    def freeze(self,request):
        import io
        from PIL import Image
        authorized=[]
        for path in self.reference_paths:
            raw=path.read_bytes();im=Image.open(io.BytesIO(raw)).convert('RGBA')
            authorized.append((digest(raw),im.size,digest(im.tobytes())))
        matched=[]
        for sid in request.style_spec_ids:
            refs=self.styles.inputs(sid)
            primary=[r for r in refs if r['role']=='style_only' and r['crop'] is None]
            if len(primary)!=1:raise ValueError('one uncropped authorized style reference required')
            im=Image.open(io.BytesIO(primary[0]['raw'])).convert('RGBA')
            matches=[x[0] for x in authorized if (x[1],x[2])==(im.size,digest(im.tobytes()))]
            if len(matches)!=1 or any(r['source_sha256']!=primary[0]['source_sha256'] for r in refs):
                raise ValueError('style does not match authorized JPEG pixels')
            matched.append(matches[0])
        if len(set(matched))!=2:raise ValueError('two distinct authorized image references required')
        layout=self.load(request.revision)
        from layout_core import validate
        if digest(canonical(layout))!=request.revision or not validate(layout)['valid']:
            raise ValueError('invalid or stale canonical layout')
        return dict(revision=request.revision,density=request.density,styles=request.style_spec_ids,authorized_jpeg_sha256=matched,
                    layout_sha256=digest(canonical(layout)),guide_sha256=digest(self.files(request.revision)['clean-guide.png']),
                    style_sha256=[digest(canonical(self.styles.get(s))) for s in request.style_spec_ids],
                    authorization_sha256=digest(self.authorization_path.read_bytes()),
                    gate_sha256=digest(Path(__file__).with_name('production_gate.py').read_bytes()),
                    registration_sha256=digest(Path(__file__).with_name('auto_adapter.py').read_bytes()),
                    registration_limits=dict(residual_px=2.5,relative_scale=.01,translation_px=1.5))

    def validate(self,w):
        f=w['frozen']
        request=Start(revision=f['revision'],density=f['density'],style_spec_ids=f['styles'],confirm_paid=True)
        if self.freeze(request)!=f:raise ValueError('frozen scope drift')
        if [a['style_spec_id'] for a in w['styles']]!=f['styles']:raise ValueError('active style drift')
        for a in w['styles']:
            if a.get('quote_id') and self.g.get_quote(a['quote_id'])['binding']!=self.binding(w,a):
                raise ValueError('quote scope drift')

    def preflight(self):
        total=Decimal(str(self.g.policy['total_usd']))
        if not self.g.policy.get('approved') or not total.is_finite() or not 0<total<=10 or not 0<self.g.policy['max_attempts']<=7:
            raise ValueError('central policy exceeds authorized scope or disabled')
        return super().preflight()

    def inputs(self,w,a):
        return self.files(w['frozen']['revision'])['clean-guide.png'],self.styles.inputs(a['style_spec_id'])

    def binding(self,w,a):
        guide,refs=self.inputs(w,a)
        return dict(layout_revision=w['frozen']['revision'],guide_sha256=digest(guide),
                    style_spec_id=a['style_spec_id'],style_id=refs[0]['reference_id'],style_sha256=refs[0]['input_sha256'],
                    style_references=[{k:v for k,v in r.items() if k!='raw'} for r in refs],
                    prompt=self.styles.prompt(a['style_spec_id']),overnight_batch_id=w['id'],density=w['frozen']['density'])

    def prepare(self,w,a):
        meta=self.preflight();q=self.g.quote(self.binding(w,a))
        self.headroom(meta,q)
        a['review_reservation_estimate_usd']=str(self.review_estimate(meta))
        return q

    @staticmethod
    def review_estimate(meta):
        from evaluations import validate_model
        validate_model(meta)
        return Decimal(meta['pricing']['prompt'])*meta['context_length']+Decimal(meta['pricing']['completion'])*4096

    def headroom(self,meta,q):
        status=self.g.status();total=Decimal(str(self.g.policy['total_usd']))
        if not status['enabled'] or not total.is_finite() or not 0<total<=10 or not 0<self.g.policy['max_attempts']<=7:
            raise ValueError('central policy exceeds scope or disabled')
        if Decimal(status['reserved_usd'])+self.review_estimate(meta)+Decimal(q['reserve_microusd'])/1000000>total:
            raise ValueError('image plus review headroom insufficient')

    def submit(self,w,a):
        meta=self.preflight();self.headroom(meta,self.g.get_quote(a['quote_id']))
        guide,refs=self.inputs(w,a)
        return self.g.confirm(a['quote_id'],w['frozen']['revision'],guide,refs[0]['raw'],[r['raw'] for r in refs[1:]])

    def prepare_review(self,w,a):
        return self.ev.prepare(a['candidate_id'],a['style_spec_id'],w['frozen']['density'])

    def review(self,w,a,recover=False):
        e=self.ev.get(a['evaluation_id'])
        if recover:
            e=self.ev.recover(e['id'])  # never run(), even if intent preceded POST
        elif e['status']=='prepared_unreviewed':
            e=self.ev.run(e['id'],self.preflight(),self.reviewer.post)
        elif e['status']!='reviewed':
            e=self.ev.recover(e['id'])
        if e['status']!='reviewed':return None
        return {**self.summary(e),'findings':e['gate']['findings']}



class Start(PaidReview):
    revision: Hash
    style_spec_ids: list[Hash] = Field(min_length=2,max_length=2)
    density: Literal[1,2] = 1

    @model_validator(mode='after')
    def distinct(self):
        if len(set(self.style_spec_ids))!=2:raise ValueError('exactly two distinct immutable styles required')
        return self


class OvernightBatch:
    def __init__(self,g,adapter):
        self.g=g;self.adapter=adapter;self.workers={};self.worker_lock=threading.Lock()
        with g.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS overnight_batches(id TEXT PRIMARY KEY, authorization TEXT UNIQUE NOT NULL, record TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS overnight_cancellations(id TEXT PRIMARY KEY, requested_at REAL NOT NULL)')

    def start(self,request):
        request=Start.model_validate(request.model_dump())
        frozen=self.adapter.freeze(request)
        rid=digest(canonical(frozen))
        with self.g.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT id,record FROM overnight_batches LIMIT 1').fetchone()
            if old:
                if old[0]!=rid:raise ValueError('overnight authorization already bound; no reset')
                return json.loads(old[1])
            for row in db.execute('SELECT record FROM jobs'):
                if json.loads(row[0])['binding']['layout_revision']==request.revision:
                    raise ValueError('fresh revision required; existing generation lineage retained')
            w=dict(id=rid,frozen=frozen,status='running',limits=dict(initial_per_style=1,repair_per_style=0,new_images=2,alltime_images=7),
                   styles=[dict(style_spec_id=sid,phase='prepare',status='running',source_candidate_id=None,candidate_id=None,evaluation_id=None,stop_reason=None,journal=[]) for sid in request.style_spec_ids])
            db.execute('INSERT INTO overnight_batches VALUES (?,?,?)',(rid,frozen['authorization_sha256'],canonical(w).decode()))
        return self.get(rid)

    def get(self,rid):
        with self.g.connect() as db:
            row=db.execute('SELECT record FROM overnight_batches WHERE id=?',(rid,)).fetchone()
            cancelled=db.execute('SELECT requested_at FROM overnight_cancellations WHERE id=?',(rid,)).fetchone()
        if not row:raise ValueError('batch missing')
        w=json.loads(row[0])
        if digest(canonical(w['frozen']))!=rid:raise ValueError('batch binding drift')
        if cancelled:
            w.update(status='cancelled',cancel_requested_at=cancelled[0])
        return w

    def cancel(self,rid):
        # Independent durable intent cannot be overwritten by an in-flight worker.
        # Provider operations already in flight may finish; never release their holds.
        with self.g.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT record FROM overnight_batches WHERE id=?',(rid,)).fetchone()
            if not row:raise ValueError('batch missing')
            if json.loads(row[0])['status'] not in ('completed','succeeded','blocked','cancelled'):
                db.execute('INSERT OR IGNORE INTO overnight_cancellations VALUES (?,?)',(rid,time.time()))
        return self.get(rid)

    def public(self,rid):
        """Derived labels only: historical terminal records are never migrated."""
        w=self.get(rid)
        for a in w['styles']:
            a['display_status']='cancelled' if w['status']=='cancelled' and a['status']=='running' else a['status']
            if a['status']=='stopped':
                review=a.get('review') or {}
                a['display_status']='succeeded' if review.get('approved') and review.get('valid') and a.get('stop_reason')=='all_strict_criteria_pass' else 'blocked'
        w['display_status']=w['status']
        if w['status']=='completed':
            w['display_status']='succeeded' if all(a['display_status']=='succeeded' for a in w['styles']) else 'blocked'
        w['terminal']=w['status'] in ('completed','succeeded','blocked','cancelled')
        w['can_cancel']=not w['terminal']
        w['can_resume']=not w['terminal'] and (w['status']=='running' or any(a['status']=='running' and a['phase'] in ('submitting','reviewing') for a in w['styles']))
        return w

    def save(self,w):
        with self.g.connect() as db:
            db.execute('UPDATE overnight_batches SET record=? WHERE id=?',(canonical(w).decode(),w['id']))
        return self.get(w['id'])

    def resume(self,rid):
        # Only receipt recovery can reopen an interrupted paid phase, never a POST.
        return self.tick(rid,recovery=True)

    def finish_style(self,w,a,reason):
        a.update(status='succeeded' if reason=='all_strict_criteria_pass' else 'blocked',stop_reason=reason)
        a['journal'].append(dict(phase=a['phase'],reason=reason,at=time.time()))
        if all(x['status']!='running' for x in w['styles']):
            w['status']='succeeded' if all(x['status']=='succeeded' for x in w['styles']) else 'blocked'
        return self.save(w)

    def pause(self,w,a,reason):
        w['status']='needs_attention';a['stop_reason']=reason
        a['journal'].append(dict(phase=a['phase'],reason=reason,at=time.time()))
        return self.save(w)

    def tick(self,rid,recovery=False):
        self.get(rid)
        with (self.g.root/('overnight-'+rid+'.lock')).open('a') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return self.get(rid)
            w=self.get(rid)
            if w['status'] in ('completed','succeeded','blocked','cancelled'):return w
            a=next(x for x in w['styles'] if x['status']=='running')
            if w['status']!='running' and not (recovery and a['phase'] in ('submitting','reviewing')):return w
            try:
                self.adapter.validate(w)
                return self.advance(w,a)
            except Exception:
                # Raw provider exceptions can contain credentials or signed URLs.
                return self.pause(w,a,'operation_failed; retained intent and holds; no automatic retry')

    def advance(self,w,a):
        phase=a['phase']
        if phase=='prepare':
            q=self.adapter.prepare(w,a);a['quote_id']=q['id'];a['phase']='submit'
        elif phase in ('submit','submitting'):
            if phase=='submit':
                a['phase']='submitting';self.save(w)
                if self.get(w['id'])['status']=='cancelled':return self.get(w['id'])
                j=self.adapter.submit(w,a)
            else:j=self.adapter.recover(w,a)
            if not j or not j.get('prediction_id'):return self.pause(w,a,'unknown_submission; receipt required; no retry')
            a.update(job_id=j['id'],job_status=j['status'],prediction_id=j['prediction_id'],phase='poll',polls=0,stop_reason=None)
            w['status']='running'
        elif phase=='poll':
            j=self.adapter.poll(w,a);a['job_status']=j['status'];a['polls']+=1
            if j['status']=='candidate_ready':
                a.update(source_candidate_id=j['candidate_id'],candidate_id=j['candidate_id'],phase='register')
            elif j['status'] in ('preparing','submitting','ambiguous','preparation_failed'):
                return self.pause(w,a,'unknown_submission; no retry')
            elif j['status'] in ('failed','cancelled','deleted','timeout'):
                return self.finish_style(w,a,'provider_'+j['status'])
            elif a['polls']>=120:return self.finish_style(w,a,'poll_limit; retained prediction; no resubmission')
        elif phase=='register':
            r=self.adapter.register(w,a);a['registration']=r
            if r.get('blocker'):return self.finish_style(w,a,r['blocker'])
            a.update(candidate_id=r['candidate_id'],phase='review')
        elif phase=='review':
            e=self.adapter.prepare_review(w,a);a.update(evaluation_id=e['id'],phase='review_ready')
        elif phase in ('review_ready','reviewing'):
            a['phase']='reviewing';self.save(w)
            if self.get(w['id'])['status']=='cancelled':return self.get(w['id'])
            result=self.adapter.review(w,a,recover=phase=='reviewing')
            if not result:return self.pause(w,a,'unknown_review; receipt required; no retry')
            a['review']=result;w['status']='running'
            reason=('all_strict_criteria_pass' if result['approved'] and result['valid'] else
                    'strict_review_failed; repairs disabled; no blind reroll' if result['valid'] else
                    'invalid_review; no citation repair or retry')
            return self.finish_style(w,a,reason)
        else:return self.pause(w,a,'unknown_phase; no retry')
        a['journal'].append(dict(phase=a['phase'],at=time.time()))
        return self.save(w)

    def launch(self,rid):
        def worker():
            while self.get(rid)['status']=='running':
                self.tick(rid)
                time.sleep(1)
        with self.worker_lock:
            old=self.workers.get(rid)
            if self.get(rid)['status']=='running' and not (old and old.is_alive()):
                thread=threading.Thread(target=worker,daemon=True,name='overnight-'+rid[:8])
                self.workers[rid]=thread;thread.start()
        return self.get(rid)


def install(app,files,record,load,register,poll):
    """Call after generation/styles/evaluations have been installed; no policy writes."""
    from fastapi import HTTPException
    service=OvernightBatch(app.state.generation,BatchAdapter(app,files,record,load,register,poll))
    app.state.overnight_batch=service
    def guarded(fn):
        try:return fn()
        except (ValueError,KeyError,FileNotFoundError):
            raise HTTPException(409,'Batch missing, stale, already bound or unauthorized; no reset/retry.') from None
    @app.post('/api/overnight-batch/start',status_code=201)
    def start(body:Start):
        w=guarded(lambda:service.start(body))
        guarded(lambda:service.launch(w['id']))
        return guarded(lambda:service.public(w['id']))
    @app.get('/api/overnight-batch')
    def saved():
        with service.g.connect() as db:ids=[r[0] for r in db.execute('SELECT id FROM overnight_batches ORDER BY id')]
        return guarded(lambda:[service.public(rid) for rid in ids])
    @app.get('/api/overnight-batch/{rid}')
    def get(rid:str):return guarded(lambda:service.public(rid))
    @app.post('/api/overnight-batch/{rid}/resume')
    def resume(rid:str):
        guarded(lambda:service.resume(rid))
        guarded(lambda:service.launch(rid))
        return guarded(lambda:service.public(rid))
    @app.post('/api/overnight-batch/{rid}/cancel')
    def cancel(rid:str):
        guarded(lambda:service.cancel(rid))
        return guarded(lambda:service.public(rid))
    return service
