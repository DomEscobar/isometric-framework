"""Append-only migration in Generation's database; independent cancellation and fencing."""
import json,time,uuid
from artifacts import canonical,digest
from billing_settlement import totals
TERMINAL={'succeeded','needs_attention','cancelled'}
class Store:
    def __init__(self,g):
        self.g=g
        with g.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS hybrid_runs(
            id TEXT PRIMARY KEY, idem TEXT UNIQUE NOT NULL, config TEXT NOT NULL,
            record TEXT NOT NULL, phase TEXT NOT NULL, fence INTEGER NOT NULL DEFAULT 0,
            lease REAL NOT NULL DEFAULT 0, cancel INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS hybrid_events(seq INTEGER PRIMARY KEY AUTOINCREMENT,run TEXT NOT NULL,record TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS hybrid_calls(id TEXT PRIMARY KEY,run TEXT NOT NULL,role TEXT NOT NULL,request TEXT NOT NULL,receipt TEXT,amount INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS hybrid_liability_authorizations(id TEXT PRIMARY KEY,run TEXT UNIQUE NOT NULL,record TEXT NOT NULL);
            CREATE TRIGGER IF NOT EXISTS hybrid_ack_no_update BEFORE UPDATE ON hybrid_liability_authorizations BEGIN SELECT RAISE(ABORT,'immutable acknowledgment'); END;
            CREATE TRIGGER IF NOT EXISTS hybrid_ack_no_delete BEFORE DELETE ON hybrid_liability_authorizations BEGIN SELECT RAISE(ABORT,'immutable acknowledgment'); END;
            CREATE TABLE IF NOT EXISTS hybrid_migrations(version INTEGER PRIMARY KEY);
            INSERT OR IGNORE INTO hybrid_migrations VALUES(1);''')
    def get(self,rid):
        with self.g.connect() as db:r=db.execute('SELECT * FROM hybrid_runs WHERE id=?',(rid,)).fetchone()
        if not r:raise ValueError('Lauf nicht gefunden')
        out=json.loads(r['record']);out.update(id=rid,config=json.loads(r['config']),phase=r['phase'],fence=r['fence'],lease=r['lease'],cancel_requested=bool(r['cancel']))
        return out
    def create(self,idem,config):
        if not isinstance(idem,str) or not 1<=len(idem)<=100:raise ValueError('Idempotency-Key fehlt')
        raw=canonical(config).decode();rid=uuid.uuid4().hex
        with self.g.connect() as db:
            db.execute('BEGIN IMMEDIATE');old=db.execute('SELECT id,config FROM hybrid_runs WHERE idem=?',(idem,)).fetchone()
            if old:
                if old['config']!=raw:raise ValueError('Idempotency-Key mit anderem Auftrag')
                rid=old['id']
            else:
                inherited=config.get('continuation',{})
                if inherited:
                    from hybrid_recovery import validated_parent
                    validated_parent(self,inherited,db=db)
                    for existing in db.execute('SELECT config FROM hybrid_runs'):
                        if json.loads(existing[0]).get('continuation',{}).get('parent_id')==inherited['parent_id']:raise ValueError('Parent bereits fortgesetzt')
                record=dict(created=time.time(),image_count=inherited.get('inherited_images',0),call_count=inherited.get('inherited_calls',0),local_count=inherited.get('inherited_local',0),production_approved=False,latest=None,best=None,stop_reason=None)
                db.execute('INSERT INTO hybrid_runs(id,idem,config,record,phase) VALUES(?,?,?,?,?)',(rid,idem,raw,canonical(record).decode(),'queued'))
                self.event(db,rid,{'phase':'queued'})
        return self.get(rid)
    def event(self,db,rid,event):db.execute('INSERT INTO hybrid_events(run,record) VALUES(?,?)',(rid,canonical({'at':time.time(),**event}).decode()))
    def events(self,rid):
        with self.g.connect() as db:return [json.loads(r[0]) for r in db.execute('SELECT record FROM hybrid_events WHERE run=? ORDER BY seq',(rid,))]
    def list(self):
        with self.g.connect() as db:ids=[r[0] for r in db.execute('SELECT id FROM hybrid_runs ORDER BY rowid DESC LIMIT 100')]
        return [self.get(i) for i in ids]
    def claim(self):
        with self.g.connect() as db:
            db.execute('BEGIN IMMEDIATE');r=db.execute("SELECT id FROM hybrid_runs WHERE phase NOT IN ('succeeded','needs_attention','cancelled','layout_preview','await_authorization') AND lease<? ORDER BY rowid LIMIT 1",(time.time(),)).fetchone()
            if not r:return None
            db.execute('UPDATE hybrid_runs SET lease=?,fence=fence+1 WHERE id=?',(time.time()+600,r[0]))
        return self.get(r[0])
    def save(self,claim,**changes):
        with self.g.connect() as db:
            db.execute('BEGIN IMMEDIATE');r=db.execute('SELECT * FROM hybrid_runs WHERE id=?',(claim['id'],)).fetchone()
            if r['fence']!=claim['fence'] or r['lease']<time.time():raise ValueError('Staler Worker abgewiesen')
            if r['phase'] in TERMINAL:raise ValueError('Terminaler Lauf unveränderlich')
            phase=changes.pop('phase',r['phase']);record=json.loads(r['record']);record.update(changes)
            db.execute('UPDATE hybrid_runs SET record=?,phase=?,lease=? WHERE id=?',(canonical(record).decode(),phase,time.time()+600,claim['id']))
            self.event(db,claim['id'],{'phase':phase,'changes':changes})
        return self.get(claim['id'])
    def release(self,claim):
        with self.g.connect() as db:db.execute('UPDATE hybrid_runs SET lease=0 WHERE id=? AND fence=?',(claim['id'],claim['fence']))
    def cancel(self,rid):
        with self.g.connect() as db:
            db.execute('BEGIN IMMEDIATE');r=db.execute('SELECT phase,lease FROM hybrid_runs WHERE id=?',(rid,)).fetchone()
            if not r:raise ValueError('Lauf fehlt')
            if r['phase'] not in TERMINAL:
                db.execute('UPDATE hybrid_runs SET cancel=1 WHERE id=?',(rid,));self.event(db,rid,{'cancel_requested':True})
                if r['lease']<time.time():db.execute("UPDATE hybrid_runs SET phase='cancelled' WHERE id=?",(rid,))
        return self.get(rid)
    def _check_ack(self,db,r,scope,auth):
        from decimal import Decimal
        if scope.get('run_id')!=r['id'] or scope.get('config_sha256')!=digest(r['config'].encode()) or scope.get('expires',0)<=time.time():raise ValueError('Liability-Freigabe falsch/abgelaufen')
        cfg=json.loads(r['config'])
        for key in ['budget_microusd','max_calls','max_images']:
            if type(scope.get(key))!=int or scope[key]<=0 or scope[key]!=cfg.get(key) or scope[key]!=auth.get(key):raise ValueError('Liability-Limits verändert')
        if scope['max_calls']>64 or scope['max_images']>15:raise ValueError('Liability-Limits ungültig')
        cap=scope.get('project_cap_microusd')
        if type(cap)!=int or not 0<cap<=int(Decimal(str(self.g.policy.get('total_usd','0')))*1_000_000):raise ValueError('Projektdeckel ungültig')
        if not isinstance(scope.get('approval_text'),str) or not scope['approval_text'].strip():raise ValueError('Explizite Zustimmung fehlt')
        liabilities=scope.get('liabilities',[])
        if not liabilities or len({x['call_id'] for x in liabilities})!=len(liabilities):raise ValueError('Haftungsliste fehlt/doppelt')
        for item in liabilities:
            old=db.execute('SELECT * FROM hybrid_calls WHERE id=?',(item['call_id'],)).fetchone()
            ledger=db.execute('SELECT * FROM reviews WHERE id=?',(item['call_id'],)).fetchone()
            if not old or old['run']==r['id'] or old['receipt'] is not None or digest(old['request'].encode())!=item['request_sha256'] or old['amount']!=item['amount'] or not ledger or ledger['reserve']!=item['amount']:raise ValueError('Althaftung verändert')
            binding=json.loads(ledger['record']).get('binding',{})
            if binding.get('request_sha256')!=item['request_sha256']:raise ValueError('Ledgerbindung verändert')
        unknown={x[0] for x in db.execute('SELECT id FROM hybrid_calls WHERE receipt IS NULL')}
        if unknown!={x['call_id'] for x in liabilities}:raise ValueError('Weitere unbekannte Haftung; kein Kauf')
        return cap
    def acknowledge_liabilities(self,scope):
        # Operator-only, append-only acknowledgment, never billing reconciliation.
        raw=canonical(scope).decode();aid=digest(raw.encode())
        with self.g.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            r=db.execute('SELECT * FROM hybrid_runs WHERE id=?',(scope.get('run_id'),)).fetchone()
            if not r or r['phase'] in TERMINAL or r['cancel'] or db.execute('SELECT 1 FROM hybrid_calls WHERE run=?',(r['id'],)).fetchone():raise ValueError('Nur frischer separater Lauf')
            cap=self._check_ack(db,r,scope,scope)
            total=totals(db)['effective_microusd']
            if total+scope['budget_microusd']>cap:raise ValueError('Headroom für gesamte neue Freigabe fehlt')
            db.execute('INSERT INTO hybrid_liability_authorizations VALUES(?,?,?)',(aid,r['id'],raw))
            self.event(db,r['id'],{'acknowledged_unresolved_liability':aid,'billing':'unsettled_full_holds_retained'})
        return aid
    def reserve_call(self,claim,role,request,amount,auth,headroom=0):
        from decimal import Decimal
        rid=claim['id'];raw=canonical(request).decode();cid=digest(canonical([rid,role,request]))
        with self.g.connect() as db:
            db.execute('BEGIN IMMEDIATE');r=db.execute('SELECT * FROM hybrid_runs WHERE id=?',(rid,)).fetchone()
            if r['fence']!=claim['fence'] or r['lease']<time.time() or r['cancel'] or r['phase'] in TERMINAL:raise ValueError('Worker/Abbruch-Grenze')
            inherited=json.loads(r['config']).get('continuation',{})
            if inherited:
                from hybrid_recovery import validated_parent
                validated_parent(self,inherited,db=db)
                if role=='planner':raise ValueError('Kein neuer Planner in Continuation')
            cfg=json.loads(r['config'])
            if cfg.get('no_new_images') and role.startswith('image'):raise ValueError('Reassessment forbids new images')
            old=db.execute('SELECT receipt FROM hybrid_calls WHERE id=?',(cid,)).fetchone()
            if old:return dict(id=cid,new=False,receipt=json.loads(old[0]) if old[0] else None)
            if db.execute('SELECT 1 FROM hybrid_calls WHERE run=? AND role=?',(rid,role)).fetchone():raise ValueError('Phase bereits versucht; Request-Drift, kein neuer Kauf')
            if auth.get('config_sha256')!=digest(r['config'].encode()) or auth.get('expires',0)<time.time():raise ValueError('Neue laufgebundene Freigabe fehlt/abgelaufen')
            if type(amount)!=int or amount<=0 or type(headroom)!=int or headroom<0:raise ValueError('Ungültige Reservierung')
            scoped_cap=int(Decimal(str(self.g.policy.get('total_usd','0')))*1_000_000)
            if auth.get('liability_authorization'):
                ack=db.execute('SELECT record FROM hybrid_liability_authorizations WHERE id=? AND run=?',(auth['liability_authorization'],rid)).fetchone()
                if not ack or digest(ack[0].encode())!=auth['liability_authorization']:raise ValueError('Liability-Freigabe fehlt/verändert')
                scoped_cap=self._check_ack(db,r,json.loads(ack[0]),auth)
            elif db.execute('SELECT 1 FROM hybrid_calls WHERE receipt IS NULL').fetchone():raise ValueError('Unbekannter bezahlter Request; kein Wiederholen')
            total=totals(db)['effective_microusd']
            ceiling=min(scoped_cap,int(Decimal(str(self.g.policy.get('total_usd','0')))*1_000_000))
            rows=db.execute('SELECT amount,role FROM hybrid_calls WHERE run=?',(rid,)).fetchall()
            if total+amount+headroom>ceiling or sum(x['amount'] for x in rows)+amount+headroom>auth.get('budget_microusd',0):raise ValueError('Zentrales/Lauf-Budget einschließlich Holds erschöpft')
            if cfg.get('followup_call_limit') is not None and len(rows)>=cfg['followup_call_limit']:raise ValueError('Followup call limit reached')
            if len(rows)+inherited.get('inherited_calls',0)>=min(auth.get('max_calls',0),64):raise ValueError('Aufruflimit erreicht')
            if role.startswith('image') and sum(x['role'].startswith('image') for x in rows)+inherited.get('inherited_images',0)>=min(auth.get('max_images',0),15):raise ValueError('Bildlimit erreicht')
            binding=dict(workflow='hybrid-terrain/1',run=rid,role=role,request_sha256=digest(raw.encode()),authorization_sha256=digest(canonical(auth)))
            ledger=dict(id=cid,reserve_microusd=amount,binding=binding,status='reserved_unknown_until_receipt')
            db.execute('INSERT INTO reviews VALUES(?,?,?)',(cid,amount,canonical(ledger).decode()))
            db.execute('INSERT INTO hybrid_calls VALUES(?,?,?,?,NULL,?)',(cid,rid,role,raw,amount))
            record=json.loads(r['record']);record.update(call_count=len(rows)+1+inherited.get('inherited_calls',0),image_count=sum(x['role'].startswith('image') for x in rows)+int(role.startswith('image'))+inherited.get('inherited_images',0))
            db.execute('UPDATE hybrid_runs SET record=? WHERE id=?',(canonical(record).decode(),rid))
            self.event(db,rid,{'call_id':cid,'role':role,'reserved_microusd':amount})
        return dict(id=cid,new=True,receipt=None)
    def receipt(self,cid,receipt):
        # Receipt remains recordable after cancellation/fence loss; immutable identity only.
        raw=canonical(receipt).decode()
        with self.g.connect() as db:
            db.execute('BEGIN IMMEDIATE');r=db.execute('SELECT receipt FROM hybrid_calls WHERE id=?',(cid,)).fetchone()
            if not r:raise ValueError('Unbekannte Request-ID')
            if r[0] and r[0]!=raw:raise ValueError('Receipt-Drift')
            db.execute('UPDATE hybrid_calls SET receipt=? WHERE id=?',(raw,cid))
        return receipt
    def calls(self,rid):
        with self.g.connect() as db:return [dict(id=r['id'],role=r['role'],amount=r['amount'],receipt_known=r['receipt'] is not None) for r in db.execute('SELECT * FROM hybrid_calls WHERE run=?',(rid,))]
    def resume(self,rid):
        # Recovery is worker-owned; HTTP never steals a live lease or reopens terminals.
        return self.get(rid)
