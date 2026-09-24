"""Free retained-run accounting/evidence verification; no paid POST."""
import os,sys,json,shlex,io
from pathlib import Path
import httpx
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from artifacts import canonical,digest
from hybrid_worker import default_store,immutable
from billing_settlement import totals
s=default_store();out=ROOT/'evidence/hybrid-material-repair';rid=json.loads((out/'new-run.json').read_bytes())['id'];r=s.get(rid);d=ROOT/'data/hybrid'/rid
before=json.loads((ROOT/'data/hybrid-material-repair-before.json').read_bytes())
with s.g.connect() as db:
    for table,rows in before['tables'].items():
        now=[dict(x) for x in db.execute('SELECT * FROM '+table+' ORDER BY rowid')]
        assert now[:len(rows)]==rows,table
    account=totals(db);calls=[dict(x) for x in db.execute('SELECT * FROM hybrid_calls WHERE run=? ORDER BY rowid',(rid,))]
assert s.g.policy==before['policy'] and not s.g.policy['approved']
assert r['call_count']==8 and r['image_count']==3 and r['phase']=='needs_attention' and not r['production_approved']
assert account['released_microusd']==0
assert (d/'source-0.png').read_bytes()==(ROOT/'data/hybrid/d270dd95c2104370938199f8f91bcb55/source-0.png').read_bytes()
for line in Path('/root/.config/layout-terrain-hybrid/environment').read_text().splitlines():
    if line.startswith('OPENROUTER_API_KEY='):os.environ['OPENROUTER_API_KEY']=shlex.split(line.split('=',1)[1])[0]
summary=[]
with httpx.Client(timeout=90) as c:
    for call in calls:
        req=json.loads(call['request']);receipt=json.loads(call['receipt']);item={k:call[k] for k in ['id','role','amount']};item.update(provider_id=receipt['id'],request_sha256=digest(call['request'].encode()),receipt_sha256=digest(call['receipt'].encode()))
        if call['role'].startswith('image'):
            item['provider_quoted_usd']=req['quote']['price'];item['actual_billed_usd']=None
            assert req['inputs'][0]['id']=='reference' and req['inputs'][1]['id']=='guide' and req['inputs'][2]['id']=='correction_target'
        else:
            assert req['body']['max_tokens']==32768 and req['body']['reasoning']=={'effort':'medium'}
            item['usage']=receipt.get('usage');item['finish_reason']=receipt['choices'][0]['finish_reason']
            billing=c.get('https://openrouter.ai/api/v1/generation',params={'id':receipt['id']},headers={'Authorization':'Bearer '+os.environ['OPENROUTER_API_KEY']});billing.raise_for_status();bill=billing.json()
            immutable(out/(receipt['id']+'-billing.json'),canonical(bill));item['billing']=bill['data'];item['actual_billed_usd']=bill['data']['total_cost']
        summary.append(item)
    status=c.get('http://127.0.0.1:48765/api/hybrid-runs/'+rid);status.raise_for_status();immutable(out/'verified-run.json',canonical(status.json()))
    denials={mode:c.get('http://127.0.0.1:48765/api/hybrid-runs/'+rid+'/download',params={'mode':mode}).status_code for mode in ['diagnostic','production']}
    assert set(denials.values())=={409}
images=[Image.open(d/f'source-{i}.png').convert('RGB') for i in range(3)]
board=Image.new('RGB',(sum(im.width for im in images)+32,images[0].height+64),'#17261f');draw=ImageDraw.Draw(board);x=0
for i,im in enumerate(images):
    draw.text((x+10,10),['ORIGINAL: stairs architectural FAIL','EDIT1: flat stone; extractor contract contradiction','EDIT2: wall replaced by stairs; REJECTED'][i],fill='white');draw.text((x+10,30),'NATIVE SOURCE PIXELS - NOT GAMEPLAY / NOT APPROVED',fill='white');board.paste(im,(x,64));x+=im.width+16
board.save(out/'three-source-native-comparison.png')
for i,im in enumerate(images):
    # Diagnostic only, never a crop input/binding supplied to worker.
    im.save(out/f'source-{i}-native.png')
result=dict(run_id=rid,phase=r['phase'],stop_reason=r['stop_reason'],lifetime_calls=r['call_count'],lifetime_images=r['image_count'],accounting=account,remaining_microusd=20000000-account['effective_microusd'],all_prior_rows_unchanged=True,original_source_preserved=True,export_http=denials,calls=summary,sources=[dict(file=f'source-{i}.png',sha256=digest((d/f'source-{i}.png').read_bytes())) for i in range(3)],sample_or_scene_created=bool(r.get('sample_directory') or r.get('latest')))
immutable(out/'verification.json',canonical(result));print(json.dumps(result,indent=2))
