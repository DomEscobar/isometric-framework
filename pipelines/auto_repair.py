"""Bounded autonomous repair. SQLite durable checkpoints, process-safe local worker lock.
Unknown submissions stop, never retry. No state transition releases a liability.
"""
import json
import time
import fcntl
import threading
from pathlib import Path
from pydantic import Field
from artifacts import canonical,digest
from evaluations import PaidReview
from style_specs import Hash

class Start(PaidReview):
    evaluation_id: Hash
    max_iterations: int=Field(default=3,ge=1,le=15)

class AutoRepair:
    def __init__(self,g,adapter):
        self.g=g;self.adapter=adapter;self.workers={};self.worker_lock=threading.Lock()
        with g.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS auto_runs(id TEXT PRIMARY KEY, root TEXT UNIQUE, record TEXT NOT NULL)')
    def start(self,request):
        frozen=self.adapter.freeze(request.evaluation_id)
        root=digest(canonical(frozen))
        with self.g.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT record FROM auto_runs WHERE root=?',(root,)).fetchone()
            if old:return json.loads(old[0])
            # This authorization covers one development run, not fifteen per start.
            old=db.execute('SELECT record FROM auto_runs LIMIT 1').fetchone()
            if old:raise ValueError('authorization already bound to a different run')
            rid=digest(canonical(dict(root=root,authorization='AUTO_REPAIR_AUTHORIZATION.md')))
            w=dict(id=rid,root=root,frozen=frozen,max_iterations=request.max_iterations,status='running',phase='plan',iterations=[],latest_candidate_id=frozen['candidate_id'],best_candidate_id=frozen['candidate_id'],evaluation_id=request.evaluation_id,best_evaluation_id=request.evaluation_id,stop_reason=None,cancel_requested=False,events=[],created_at=time.time())
            db.execute('INSERT INTO auto_runs VALUES (?,?,?)',(rid,root,canonical(w).decode()))
        return self.get(rid)
    def continue_run(self,rid,authorization,max_iterations=15):
        """Create, but never launch, an explicitly authorized successor.

        The caller authenticates the new authorization document's SHA256. The
        adapter's continuation_seed is a READ-ONLY proof boundary: verify the
        retained best's registration, matching reviewed evaluation and receipts,
        frozen bindings and absence of unresolved paid intents. No hook means no
        continuation. This method neither opens policy nor releases liabilities.
        """
        if type(max_iterations) is not int or not 1 <= max_iterations <= 15:
            raise ValueError('lifetime iteration limit must be 1..15')
        if not isinstance(authorization,dict):raise ValueError('explicit authorization specification required')
        authorization=json.loads(canonical(authorization))
        ah=authorization.get('authorization_sha256','')
        if not isinstance(ah,str) or len(ah)!=64 or any(c not in '0123456789abcdef' for c in ah):
            raise ValueError('immutable new authorization SHA256 required')
        if authorization.get('parent_run_id')!=rid or not isinstance(authorization.get('reason'),str) or not authorization['reason'].strip():
            raise ValueError('authorization must bind parent and explicit selection reason')
        with self.g.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            # The unique parent binding serializes even different authorizations.
            db.execute('CREATE TABLE IF NOT EXISTS auto_continuations(parent TEXT PRIMARY KEY, child TEXT UNIQUE, authorization TEXT UNIQUE)')
            old=db.execute('SELECT child FROM auto_continuations WHERE parent=?',(rid,)).fetchone()
            if old:
                child=self.get(old[0])
                if child['continuation']['authorization']!=authorization or child['max_iterations']!=max_iterations:
                    raise ValueError('parent already bound to a different continuation')
                return child
            w=self.get(rid)
            if w['status']!='needs_attention' or w['cancel_requested']:
                raise ValueError('only an eligible terminal safety stop can continue')
            attempts=w['iterations'];last=attempts[-1] if attempts else {}
            registration_stop=(w['phase']=='register' and last.get('registration',{}).get('blocker')==w['stop_reason']
                               and str(w['stop_reason']).startswith('registration_')
                               and (last.get('job_status')=='candidate_ready' or last.get('plan',{}).get('action')=='register'))
            capped=(w['phase']=='plan' and w['stop_reason']=='iteration_limit' and last.get('review',{}).get('valid') is True)
            if not (registration_stop or capped):raise ValueError('stop is not safely continuable; unknown outcomes never retry')
            count=w.get('inherited_iterations',0)+len(attempts)
            if count>=max_iterations:raise ValueError('lifetime iteration limit exhausted')
            if authorization.get('candidate_id')!=w['best_candidate_id'] or authorization.get('evaluation_id')!=w['best_evaluation_id']:
                raise ValueError('explicit selection must be retained best and matching evaluation')
            ancestor=w
            while True:
                if ah==ancestor['frozen'].get('authorization_sha256') or ah==ancestor.get('continuation',{}).get('authorization',{}).get('authorization_sha256'):
                    raise ValueError('new authorization required')
                if 'continuation' not in ancestor:break
                ancestor=self.get(ancestor['continuation']['parent_run_id'])
            prove=getattr(self.adapter,'continuation_seed',None)
            if not callable(prove):raise ValueError('adapter cannot prove safe reviewed registered seed')
            self.adapter.validate(w)
            proof=prove(json.loads(canonical(w)))
            expected=dict(candidate_id=w['best_candidate_id'],evaluation_id=w['best_evaluation_id'],
                          frozen_sha256=digest(canonical(w['frozen'])),registered=True,reviewed=True,valid=True,no_unknown_liabilities=True)
            if not isinstance(proof,dict) or any(proof.get(k)!=v or (v is True and proof.get(k) is not True) for k,v in expected.items()):
                raise ValueError('safe seed proof missing or mismatched')
            lineage=dict(parent_run_id=rid,parent_record_sha256=digest(db.execute('SELECT record FROM auto_runs WHERE id=?',(rid,)).fetchone()[0].encode()),
                         authorization=authorization,previous_latest_candidate_id=w['latest_candidate_id'],
                         previous_evaluation_id=w['evaluation_id'],parent_stop_reason=w['stop_reason'],seed_proof=proof)
            root=digest(canonical(dict(frozen=w['frozen'],continuation=lineage)))
            child=dict(id=root,root=root,frozen=w['frozen'],continuation=lineage,
                       max_iterations=max_iterations,inherited_iterations=count,status='running',phase='plan',iterations=[],
                       latest_candidate_id=w['best_candidate_id'],best_candidate_id=w['best_candidate_id'],
                       evaluation_id=w['best_evaluation_id'],best_evaluation_id=w['best_evaluation_id'],
                       stop_reason=None,cancel_requested=False,events=[],created_at=time.time())
            if w.get('best_review'):child['best_review']=w['best_review']
            db.execute('INSERT INTO auto_runs VALUES (?,?,?)',(root,root,canonical(child).decode()))
            db.execute('INSERT INTO auto_continuations VALUES (?,?,?)',(rid,root,ah))
        return self.get(root)

    def recover_seed(self,rid):
        """Doc-authorized FREE bootstrap, not acceptance of the invalid old review.

        Re-register the retained best's ORIGINAL with the frozen estimator, then
        require a distinct exact-density evaluation before any image correction.
        History, unsafe latest, liabilities and old verdicts remain untouched.
        """
        authorization=self.adapter.quality_authorization(rid)
        with self.g.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE IF NOT EXISTS auto_continuations(parent TEXT PRIMARY KEY, child TEXT UNIQUE, authorization TEXT UNIQUE)')
            old=db.execute('SELECT child FROM auto_continuations WHERE parent=?',(rid,)).fetchone()
            if old:
                child=self.get(old[0])
                if child['continuation'].get('authorization')!=authorization:raise ValueError('parent already bound to different authority')
                return child
            w=self.get(rid);self.adapter.validate(w)
            last=w['iterations'][-1] if w['iterations'] else {}
            if not (w['status']=='needs_attention' and not w['cancel_requested'] and w['phase']=='register'
                    and last.get('registration',{}).get('blocker')==w['stop_reason']
                    and str(w['stop_reason']).startswith('registration_')):
                raise ValueError('only a known terminal registration stop can bootstrap')
            count=len(self.history(w))
            if count>=15:raise ValueError('lifetime iteration limit exhausted')
            # Read-only source/frozen proof; no writes while holding the ledger lock.
            plan=self.adapter.recovery_plan(w)
            lineage=dict(parent_run_id=rid,parent_record_sha256=digest(canonical(w)),
                         authorization=authorization,mode='seed-registration-recovery',
                         previous_latest_candidate_id=w['latest_candidate_id'],
                         previous_evaluation_id=w['evaluation_id'],parent_stop_reason=w['stop_reason'])
            root=digest(canonical(dict(frozen=w['frozen'],continuation=lineage)))
            a=dict(id=root+':'+str(count+1),number=count+1,plan=plan,
                   input_candidate_id=w['best_candidate_id'],input_evaluation_id=w['best_evaluation_id'],
                   candidate_id=w['best_candidate_id'],created_at=time.time(),polls=0)
            child=dict(id=root,root=root,frozen=w['frozen'],continuation=lineage,
                       max_iterations=15,inherited_iterations=count,status='running',phase='register',iterations=[a],
                       latest_candidate_id=w['best_candidate_id'],best_candidate_id=w['best_candidate_id'],
                       evaluation_id=w['best_evaluation_id'],best_evaluation_id=w['best_evaluation_id'],
                       best_review=self.adapter.baseline(w),stop_reason=None,cancel_requested=False,events=[],created_at=time.time())
            db.execute('INSERT INTO auto_runs VALUES (?,?,?)',(root,root,canonical(child).decode()))
            db.execute('INSERT INTO auto_continuations VALUES (?,?,?)',(rid,root,authorization['authorization_sha256']))
        return self.get(root)

    def constrained_run(self,rid):
        """One genuinely masked correction from a proven reviewed ancestor.
        Same authorization/ledger, sealed parent, no reset and no arbitrary seed.
        """
        authority=self.adapter.constrained_authorization(rid)
        with self.g.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE IF NOT EXISTS auto_continuations(parent TEXT PRIMARY KEY, child TEXT UNIQUE, authorization TEXT UNIQUE)')
            old=db.execute('SELECT child FROM auto_continuations WHERE parent=?',(rid,)).fetchone()
            if old:
                child=self.get(old[0])
                if child['continuation'].get('authorization')!=authority:raise ValueError('different constrained authority')
                return child
            w=self.get(rid);self.adapter.validate(w);history=self.history(w)
            last=w['iterations'][-1] if w['iterations'] else {}
            if not (w['status']=='needs_attention' and not w['cancel_requested'] and w['phase']=='register'
                    and last.get('registration',{}).get('blocker')==w['stop_reason']
                    and str(w['stop_reason']).startswith('registration_') and last.get('job_status')=='candidate_ready'):
                raise ValueError('known registration safety stop required')
            if len(history)>=15:raise ValueError('lifetime iteration limit exhausted')
            proof=self.adapter.constrained_seed(w)
            if not all(proof.get(k) is True for k in ('eligible','registered','reviewed','valid','no_unknown_liabilities')):
                raise ValueError('constrained seed proof failed')
            if not any(a.get('candidate_id')==proof['candidate_id'] and a.get('review',{}).get('id')==proof['evaluation_id'] and a.get('review',{}).get('valid') is True for a in history):
                raise ValueError('seed is not a reviewed historical iteration')
            link=dict(parent_run_id=rid,parent_record_sha256=digest(canonical(w)),authorization=authority,
                      mode='constrained-mask-recovery',seed_proof=proof,previous_latest_candidate_id=w['latest_candidate_id'],
                      previous_evaluation_id=w['evaluation_id'],parent_stop_reason=w['stop_reason'])
            root=digest(canonical(dict(frozen=w['frozen'],continuation=link)))
            child=dict(id=root,root=root,frozen=w['frozen'],continuation=link,max_iterations=15,
                       inherited_iterations=len(history),status='running',phase='plan',iterations=[],
                       latest_candidate_id=proof['candidate_id'],best_candidate_id=w['best_candidate_id'],
                       evaluation_id=proof['evaluation_id'],best_evaluation_id=w['best_evaluation_id'],
                       stop_reason=None,cancel_requested=False,events=[],created_at=time.time())
            if w.get('best_review'):child['best_review']=w['best_review']
            db.execute('INSERT INTO auto_runs VALUES (?,?,?)',(root,root,canonical(child).decode()))
            db.execute('INSERT INTO auto_continuations VALUES (?,?,?)',(rid,root,digest(canonical(authority))))
        return self.get(root)

    def resume_quality(self,rid):
        self.get(rid)  # validate identity before constructing a lock path
        with (self.g.root/('auto-'+rid+'.lock')).open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            return self._resume_quality_locked(rid)

    def _resume_quality_locked(self,rid):
        w=self.get(rid)
        if w.get('continuation',{}).get('mode')!='seed-registration-recovery':raise ValueError('not a recovery bootstrap')
        authority=self.adapter.quality_authorization(w['continuation']['parent_run_id'])
        if authority!=w['continuation']['authorization']:raise ValueError('recovery authorization drift')
        if w['status']!='awaiting_prerequisite':return w
        self.history(w);self.adapter.validate(w)
        if w['phase']!='review' or w['cancel_requested']:raise ValueError('cannot resume a paid intent or cancellation')
        blockers=self.adapter.recovery_prerequisites(w,w['iterations'][-1])
        if blockers:return w
        w.update(status='running',stop_reason=None,prerequisite_blockers=[])
        return self.save(w)

    def get(self,rid):
        with self.g.connect() as db:row=db.execute('SELECT record FROM auto_runs WHERE id=?',(rid,)).fetchone()
        if not row:raise ValueError('run not found')
        w=json.loads(row[0])
        contract=dict(frozen=w['frozen'],continuation=w['continuation']) if 'continuation' in w else w['frozen']
        if digest(canonical(contract))!=w['root']:raise ValueError('frozen contract drift')
        return w
    def save(self,w):
        with self.g.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current=json.loads(db.execute('SELECT record FROM auto_runs WHERE id=?',(w['id'],)).fetchone()[0])
            w['cancel_requested']=w['cancel_requested'] or current['cancel_requested']
            w['updated_at']=time.time()
            db.execute('UPDATE auto_runs SET record=? WHERE id=?',(canonical(w).decode(),w['id']))
        return self.get(w['id'])
    def cancel(self,rid):
        with self.g.connect() as db:
            db.execute('BEGIN IMMEDIATE');w=json.loads(db.execute('SELECT record FROM auto_runs WHERE id=?',(rid,)).fetchone()[0])
            # Terminal evidence may already be sealed into a successor's lineage.
            # Cancelling that successor requires its own ID, never a parent rewrite.
            if w['status'] not in ('running','awaiting_prerequisite'):return self.get(rid)
            if w['status']=='awaiting_prerequisite':
                w.update(status='cancelled',stop_reason='cancelled before any pending paid request; holds retained')
            w['cancel_requested']=True
            db.execute('UPDATE auto_runs SET record=? WHERE id=?',(canonical(w).decode(),rid))
        return self.get(rid)
    def resume(self,rid):
        # A terminal safety stop is not a new spending authorization.
        return self.get(rid)
    def stop(self,w,reason,status='needs_attention'):
        w.update(status=status,stop_reason=reason)
        w['events'].append(dict(at=time.time(),phase=w['phase'],reason=reason))
        if w['iterations']:w['iterations'][-1]['stop_reason']=reason
        return self.save(w)
    def history(self,w):
        # Historical attempts are referenced, never copied into successor attempts.
        if 'continuation' not in w:return list(w['iterations'])
        link=w['continuation'];parent=self.get(link['parent_run_id'])
        if digest(canonical(parent))!=link['parent_record_sha256']:
            raise ValueError('continuation parent evidence drift')
        history=self.history(parent)
        if len(history)!=w['inherited_iterations']:
            raise ValueError('continuation lifetime accounting drift')
        return history+list(w['iterations'])

    def correction_signature(self,w,plan):
        """Reconstruct adapter semantics without upgrading historical records."""
        findings=plan.get('findings')
        if isinstance(findings,list) and findings and all(
            isinstance(f,dict) and all(isinstance(f.get(k),str) and f[k].strip()
                                      for k in ('criterion','observation','correction'))
            for f in findings
        ):
            if 'control' in plan:
                c=plan['control']
                from constrained_provider import MaskedWaveSpeed
                if (not isinstance(c,dict) or set(c)!={'strategy','model','mask_sha256','source_sha256'}
                    or c['strategy']!='canonical-sidewalk-mask-v1' or c['model']!=MaskedWaveSpeed.model_id
                    or any(not isinstance(c[k],str) or len(c[k])!=64 or any(x not in '0123456789abcdef' for x in c[k]) for k in ('mask_sha256','source_sha256'))):
                    raise ValueError('unsupported or malformed correction control')
                return digest(canonical(dict(findings=sorted((f['criterion'],f['observation'],f['correction']) for f in findings),control=c)))
            return digest(canonical(sorted((f['criterion'],f['observation'],f['correction']) for f in findings)))
        # Transport-free engine fixtures have no real authorization binding.
        # Only their exact, explicitly MOCK-labelled legacy shape may use a
        # prompt-sensitive hash; real adapter plans must supply semantic evidence.
        if 'authorization_sha256' not in w['frozen']:
            unsigned={k:v for k,v in plan.items() if k!='correction_signature'}
            if (set(unsigned)=={'action','prompt','findings'} and unsigned['action']=='generate'
                and unsigned['findings']==['material']
                and isinstance(unsigned['prompt'],str) and unsigned['prompt'].startswith('MOCK change ')
                and unsigned['prompt'][len('MOCK change '):].isdigit()):
                return plan.get('correction_signature') or digest(canonical(unsigned))
            if set(unsigned)<= {'action','candidate'} and plan.get('correction_signature'):
                return plan['correction_signature']
        raise ValueError('correction semantics unavailable; no safe duplicate comparison')

    def tick(self,rid):
        with (self.g.root/('auto-'+rid+'.lock')).open('a') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return self.get(rid)
            w=self.get(rid)
            if w['status']!='running':return w
            if w['cancel_requested']:return self.stop(w,'cancelled; existing provider jobs and holds retained','cancelled')
            try:
                history=self.history(w)
                self.adapter.validate(w)
                quality=w.get('continuation',{}).get('mode')=='seed-registration-recovery'
                if quality and self.adapter.quality_authorization(w['continuation']['parent_run_id'])!=w['continuation']['authorization']:
                    raise ValueError('recovery authorization drift')
                phase=w['phase'];a=w['iterations'][-1] if w['iterations'] else None
                if phase=='plan':
                    if w.get('continuation',{}).get('mode')=='constrained-mask-recovery' and w['iterations']:
                        return self.stop(w,'constrained_one_attempt_complete')
                    if len(history)>=w['max_iterations']:return self.stop(w,'iteration_limit')
                    plan=self.adapter.plan(w)
                    if plan.get('approved'):return self.stop(w,'all_strict_criteria_pass','succeeded')
                    if not w.get('best_review'):w['best_review']=self.adapter.baseline(w)
                    a=dict(id=w['id']+':'+str(len(history)+1),number=len(history)+1,plan=plan,input_candidate_id=w['latest_candidate_id'],input_evaluation_id=w['evaluation_id'],created_at=time.time(),polls=0)
                    signature=self.correction_signature(w,plan)
                    if any(self.correction_signature(w,x['plan'])==signature for x in history):return self.stop(w,'identical_correction_plan')
                    w['iterations'].append(a);w['phase']='prepare' if plan['action']=='generate' else 'register'
                    if plan['action']!='generate':a['candidate_id']=w['latest_candidate_id']
                elif phase=='prepare':
                    q=self.adapter.prepare(w,a);a['quote_id']=q['id'];w['phase']='submit'
                elif phase=='submit':
                    # Durable BEFORE external effects. Crash here never blindly retries.
                    w['phase']='submitting';self.save(w)
                    if self.get(rid)['cancel_requested']:return self.stop(w,'cancelled before submission','cancelled')
                    j=self.adapter.submit(w,a);a['job_id']=j['id'];a['job_status']=j['status'];w['phase']='poll'
                elif phase=='submitting':
                    j=self.adapter.recover(w,a)
                    if not j:return self.stop(w,'unknown_submission')
                    a['job_id']=j['id'];a['job_status']=j['status'];w['phase']='poll'
                elif phase=='poll':
                    j=self.adapter.poll(w,a);a['job_status']=j['status'];a['polls']+=1
                    if j['status']=='candidate_ready':a['candidate_id']=j['candidate_id'];w['latest_candidate_id']=j['candidate_id'];w['phase']='register'
                    elif j['status'] in ('ambiguous','preparing','submitting','preparation_failed'):return self.stop(w,'unknown_submission')
                    elif j['status'] in ('failed','cancelled','deleted','timeout'):return self.stop(w,'provider_'+j['status'])
                    elif a['polls']>=120:return self.stop(w,'poll_limit; known prediction retained')
                elif phase=='register':
                    r=self.adapter.register(w,a);a['registration']=r
                    if r.get('blocker'):return self.stop(w,r['blocker'])
                    a['candidate_id']=r['candidate_id'];w['latest_candidate_id']=r['candidate_id'];w['phase']='review'
                elif phase=='review':
                    if quality:
                        blockers=self.adapter.recovery_prerequisites(w,a)
                        if blockers:
                            w['prerequisite_blockers']=blockers
                            return self.stop(w,'quality recovery prerequisites unresolved; no paid call','awaiting_prerequisite')
                        self.save(w)
                    result=self.adapter.review(w,a);a['review']=result;w['evaluation_id']=result['id'];w['phase']='assess'
                elif phase=='assess':
                    r=a['review'];best=w['best_review']
                    if r['source_sha256']==best['source_sha256'] and a['plan']['action']=='generate':return self.stop(w,'unchanged_source')
                    if not r['valid']:return self.stop(w,'invalid_review; no citation repair or retry')
                    if quality:
                        proof=self.adapter.continuation_seed({**w,'best_candidate_id':w['latest_candidate_id'],'best_evaluation_id':w['evaluation_id']})
                        a['seed_proof']=proof
                        if not proof.get('eligible'):return self.stop(w,'new registered/reviewed seed proof failed; no image purchase')
                    # Pareto dominance: never exchange one failed criterion for another.
                    improves=all(x>=y for x,y in zip(r['score'],best['score'])) and any(x>y for x,y in zip(r['score'],best['score']))
                    if improves or r['approved']:
                        w.update(best_review=r,best_candidate_id=a['candidate_id'],best_evaluation_id=r['id'])
                    a['promoted_to_best']=improves or r['approved']
                    if r['approved']:return self.stop(w,'all_strict_criteria_pass','succeeded')
                    if not improves:
                        count=sum(not x.get('promoted_to_best',True) for x in self.history(w)[-2:])
                        if count>=2:return self.stop(w,'stagnation; no strict criterion improvement in two attempts')
                    w['phase']='plan'
                else:return self.stop(w,'unknown_phase')
                w['events'].append(dict(at=time.time(),phase=w['phase'],iteration=len(w['iterations'])))
                return self.save(w)
            except Exception as exc:
                # Only locally authored ValueErrors are exposed; other errors are redacted.
                reason=str(exc) if isinstance(exc,ValueError) else 'operation_failed; inspect retained evidence; no automatic retry'
                return self.stop(w,reason)
    def launch(self,rid):
        def worker():
            while self.get(rid)['status']=='running':
                self.tick(rid);time.sleep(2)
        with self.worker_lock:
            old=self.workers.get(rid)
            if self.get(rid)['status']=='running' and not (old and old.is_alive()):
                thread=threading.Thread(target=worker,daemon=True,name='repair-'+rid[:8]);self.workers[rid]=thread;thread.start()
        return self.get(rid)
