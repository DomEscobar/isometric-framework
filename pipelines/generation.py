"""Durable single-submission state machine; no background or paid retries.
Reservations remain charged conservatively even on failure/unknown outcome.
A quote is not approval. Policy is server-side and defaults to zero.
"""
import json
import os
import sqlite3
import time
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from artifacts import canonical,digest
from provider import MODEL
from billing_settlement import totals

DEFAULT_POLICY={'approved':False,'total_usd':'0','max_attempts':0}
PROMPT=('Image 1 is the immutable layout/geometry authority. Image 2 is style and palette authority ONLY, not a layout. '
        'Preserve the full image frame, ground diamond, water boundaries and path positions from image 1. '
        'Paint ground only. No upright trees, buildings, characters, labels or grid. Do not crop or change projection. ')


class Generation:
    def __init__(self,root,provider,policy=None):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
        self.provider=provider; self.policy=policy or DEFAULT_POLICY.copy()
        self.db=self.root/'generation.sqlite3'
        with self.connect() as db:
            db.executescript('CREATE TABLE IF NOT EXISTS quotes (id TEXT PRIMARY KEY, record TEXT NOT NULL);'
                             'CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, quote_id TEXT UNIQUE, reserve INTEGER NOT NULL, record TEXT NOT NULL);'
                             'CREATE TABLE IF NOT EXISTS reviews (id TEXT PRIMARY KEY, reserve INTEGER NOT NULL, record TEXT NOT NULL);')

    def connect(self):
        db=sqlite3.connect(self.db,timeout=30); db.row_factory=sqlite3.Row
        db.execute('PRAGMA synchronous=FULL'); return db

    def reserve_review(self, rid, amount, binding):
        if type(amount) is not int or amount <= 0 or not self.policy.get('approved'):
            raise ValueError('review budget unapproved or invalid reservation')
        record=dict(id=rid,reserve_microusd=amount,binding=binding,status='reserved_unknown_until_receipt')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT record FROM reviews WHERE id=?',(rid,)).fetchone()
            if old:
                if json.loads(old[0]) != record: raise ValueError('review binding drift')
                return record
            spent=totals(db)['effective_microusd']
            if spent+amount > int(Decimal(str(self.policy.get('total_usd','0')))*1000000):
                raise ValueError('total budget insufficient including review liability')
            db.execute('INSERT INTO reviews VALUES (?,?,?)',(rid,amount,canonical(record).decode()))
        return record

    def status(self):
        with self.connect() as db:
            row=db.execute('SELECT COALESCE(SUM(reserve),0),COUNT(*) FROM jobs').fetchone()
            reviews=db.execute('SELECT COALESCE(SUM(reserve),0),COUNT(*) FROM reviews').fetchone()
            accounting=totals(db)
        reasons=[]
        if not self.provider.authenticated: reasons.append('provider authentication missing')
        if not self.policy.get('approved'):
            reasons.append('project paid controls closed; existing budget and holds retained; no generation allowed')
        elif Decimal(str(self.policy.get('total_usd','0'))) <= 0:
            reasons.append('project paid budget is zero; no generation allowed')
        if row[1] >= self.policy.get('max_attempts',0): reasons.append('project attempt limit reached or unapproved')
        return dict(authenticated=self.provider.authenticated,enabled=not reasons,reasons=reasons,
                    total_budget_usd=str(self.policy.get('total_usd','0')),reserved_usd=str(Decimal(accounting['effective_microusd'])/1000000),billing=accounting,
                    generation_reserved_usd=str(Decimal(row[0])/1000000),review_reserved_usd=str(Decimal(accounting['reviews_microusd'])/1000000),review_attempts=reviews[1],
                    attempts=row[1],max_attempts=self.policy.get('max_attempts',0),
                    retry_policy='0 automatic paid retries; 1 submission per quote; explicit new quote for another attempt; unknown outcomes block all new submissions',
                    pricing_caveat='Provider estimates are not a billing guarantee; reservations use undiscounted price and never auto-release.')

    def quote(self,binding):
        schema=self.provider.discover()
        # No upload at quote stage. URLs are placeholders; exact uploaded inputs are re-quoted before any paid POST.
        inputs={'prompt':PROMPT+binding['prompt'],'image_urls':['https://example.invalid/guide.png','https://example.invalid/style.png'],'output_format':'png'}
        if binding.get('style_references'):
            inputs['image_urls']=['https://example.invalid/guide.png']+[f'https://example.invalid/reference-{i}.png' for i in range(len(binding['style_references']))]
            inputs['prompt']='Image 1 is immutable geometry authority. Ground only; no upright props. Preserve frame, projection, material boundaries and collisions. Following images have ONLY their declared reference roles in order. '+binding['prompt']
        if hasattr(self.provider,'input_template'):inputs=self.provider.input_template(binding)
        price=self.provider.quote(inputs)
        amount=Decimal(str(price['price']))
        if price.get('currency') != 'USD' or not amount.is_finite() or amount <= 0: raise ValueError('invalid USD price')
        record=dict(binding=binding,model=getattr(self.provider,'model_id',MODEL),schema=schema,schema_sha256=digest(canonical(schema)),
                    quote=price,inputs_template=inputs,reserve_microusd=int((amount*1000000).to_integral_value(rounding=ROUND_CEILING)),
                    created_at=int(time.time()),expires_at=int(time.time())+900,max_submissions=1,
                    roles=['immutable geometry guide','style only'],estimate=True)
        if binding.get('style_references'):record['roles']=['immutable geometry guide']+[r['role']+(' '+r['material'] if r['material'] else '') for r in binding['style_references']]
        qid=digest(canonical(record)); record['id']=qid
        with self.connect() as db: db.execute('INSERT OR IGNORE INTO quotes VALUES (?,?)',(qid,canonical(record).decode()))
        return self.get_quote(qid)

    def get_quote(self,qid):
        with self.connect() as db: row=db.execute('SELECT record FROM quotes WHERE id=?',(qid,)).fetchone()
        if not row: raise ValueError('quote not found')
        q=json.loads(row[0])
        if digest(canonical({k:v for k,v in q.items() if k!='id'})) != qid: raise ValueError('quote integrity failure')
        return q

    def get(self,jid):
        with self.connect() as db: row=db.execute('SELECT record FROM jobs WHERE id=?',(jid,)).fetchone()
        if not row: raise ValueError('job not found')
        j=json.loads(row[0]); q=self.get_quote(j['quote_id'])
        if j['id'] != jid or j['binding'] != q['binding'] or j['reserved_microusd'] != q['reserve_microusd']:
            raise ValueError('job binding integrity failure')
        if j.get('request') and digest(canonical(j['request'])) != j.get('request_sha256'):
            raise ValueError('request integrity failure')
        if j.get('request'):
            for sha in (q['binding']['guide_sha256'],q['binding']['style_sha256'],*[r['input_sha256'] for r in q['binding'].get('style_references',[])]):
                try: raw=(self.root/'generation-sources'/(sha+'.png')).read_bytes()
                except FileNotFoundError: raise ValueError('input source missing') from None
                if digest(raw)!=sha: raise ValueError('input source integrity failure')
        if j.get('prediction_id'):
            try:
                receipt=json.loads((self.root/(jid+'.receipt.json')).read_bytes())
            except (FileNotFoundError,ValueError):
                raise ValueError('prediction receipt missing or corrupt') from None
            expected=dict(job_id=jid,quote_id=j['quote_id'],request_sha256=j['request_sha256'],prediction_id=j['prediction_id'])
            if receipt != expected: raise ValueError('prediction binding integrity failure')
        return j

    def save(self,j):
        with self.connect() as db: db.execute('UPDATE jobs SET record=? WHERE id=?',(canonical(j).decode(),j['id']))
        return self.get(j['id'])

    def confirm(self,qid,revision,guide,style,extra_styles=None):
        q=self.get_quote(qid); b=q['binding']
        if q['model']!=getattr(self.provider,'model_id',MODEL):raise ValueError('provider model mismatch')
        extra_styles=extra_styles or []
        if b.get('style_references') and [digest(x) for x in [style,*extra_styles]] != [r['input_sha256'] for r in b['style_references']]: raise ValueError('reference hash drift')
        if b['layout_revision'] != revision: raise ValueError('stale layout revision')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT id FROM jobs WHERE quote_id=?',(qid,)).fetchone()
            if old: return self.get(old[0])
            # Refreshed quotes cannot duplicate an identical semantic request.
            for row in db.execute('SELECT id,record FROM jobs').fetchall():
                if json.loads(row['record'])['binding'] == b:
                    return self.get(row['id'])
            if not self.policy.get('approved'): raise ValueError('project budget unapproved')
            if not self.provider.authenticated: raise ValueError('provider authentication missing')
            if q['expires_at'] < time.time(): raise ValueError('quote expired; request free fresh quote')
            if digest(guide)!=b['guide_sha256'] or digest(style)!=b['style_sha256']: raise ValueError('source hash drift')
            rows=db.execute('SELECT reserve,record FROM jobs').fetchall()
            if any(json.loads(r['record'])['status'] in ('preparing','submitting','ambiguous') for r in rows):
                raise ValueError('unresolved submission; reconcile original, never resubmit')
            if len(rows)>=self.policy.get('max_attempts',0): raise ValueError('project attempt limit reached')
            total=int(Decimal(str(self.policy.get('total_usd','0')))*1000000)
            if totals(db)['effective_microusd']+q['reserve_microusd']>total: raise ValueError('total budget insufficient')
            j=dict(id=qid,quote_id=qid,binding=b,status='preparing',prediction_id=None,reserved_microusd=q['reserve_microusd'],
                   request=None,request_sha256=None,automatic_paid_retries=0)
            db.execute('INSERT INTO jobs VALUES (?,?,?,?)',(qid,qid,q['reserve_microusd'],canonical(j).decode()))
        try:
            sources=self.root/'generation-sources';sources.mkdir(exist_ok=True)
            for raw in (guide,style,*extra_styles):
                path=sources/(digest(raw)+'.png')
                try:
                    with path.open('xb') as f:
                        f.write(raw);f.flush();os.fsync(f.fileno())
                except FileExistsError:
                    if path.read_bytes()!=raw: raise ValueError('immutable input source conflict')
                if path.read_bytes()!=raw: raise ValueError('input source readback mismatch')
            if digest(canonical(self.provider.discover()))!=q['schema_sha256']: raise ValueError('live schema drift')
            urls=[self.provider.upload(guide,'guide.png'),self.provider.upload(style,'style.png')]
            urls += [self.provider.upload(raw,f'material-{i}.png') for i,raw in enumerate(extra_styles)]
            request=(self.provider.bind_inputs(q['inputs_template'],urls) if hasattr(self.provider,'bind_inputs')
                     else {**q['inputs_template'],'image_urls':urls})
            exact=self.provider.quote(request)
            exact_amount=Decimal(str(exact['price']))
            if exact.get('currency')!='USD' or not exact_amount.is_finite() or exact_amount<=0 or exact_amount>Decimal(q['reserve_microusd'])/1000000:
                raise ValueError('price changed above reservation; new confirmation required')
            j.update(request=request,request_sha256=digest(canonical(request)),exact_quote=exact,status='submitting')
            self.save(j)  # durable intent BEFORE network; crash can never produce automatic resubmission
            result=self.provider.submit(request)
            pid=result.get('id')
            if not isinstance(pid,str) or not pid: raise ValueError('no prediction id returned')
            receipt=canonical(dict(job_id=qid,quote_id=qid,request_sha256=j['request_sha256'],prediction_id=pid))
            with (self.root/(qid+'.receipt.json')).open('xb') as f:
                f.write(receipt);f.flush();os.fsync(f.fileno())
            j.update(prediction_id=pid,status='submitted')
        except Exception:
            j['status']='ambiguous' if j['status']=='submitting' else 'preparation_failed'
            j['error']='No automatic retry. Resume known prediction only; unknown submission needs provider reconciliation.'
        return self.save(j)

    def resume(self,jid):
        j=self.get(jid)
        if not j.get('prediction_id'):
            receipt_path=self.root/(jid+'.receipt.json')
            if not receipt_path.exists(): return j
            receipt=json.loads(receipt_path.read_bytes())
            if any(receipt.get(k)!=v for k,v in dict(job_id=jid,quote_id=j['quote_id'],request_sha256=j['request_sha256']).items()) or not receipt.get('prediction_id'):
                raise ValueError('prediction receipt binding mismatch')
            j.update(prediction_id=receipt['prediction_id'],status='submitted')
            j=self.save(j)
        if j['status'] in ('candidate_ready','failed','cancelled','deleted'): return j
        try:
            result=self.provider.poll(j['prediction_id'])
            if result.get('id') != j['prediction_id']: raise ValueError('prediction binding mismatch')
            status=result.get('status')
            if status=='completed':
                outputs=result.get('outputs')
                if not isinstance(outputs,list) or len(outputs)!=1 or not isinstance(outputs[0],str):
                    raise ValueError('unexpected output count')
                j.update(status='completed',output_url=outputs[0])
            elif status in ('failed','cancelled','deleted','timeout'): j['status']=status
            else: j['status']='processing'
            j.pop('poll_error',None)
        except Exception:
            j['poll_error']='Poll failed or prediction binding mismatch; original prediction retained; no resubmission.'
        return self.save(j)

    def public(self,j):
        # Omit signed remote output/input URLs. Exact request stays server-side in SQLite.
        return {k:v for k,v in j.items() if k not in ('request','output_url','exact_quote')}
