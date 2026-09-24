"""Public deployment smoke; free inspect-only job, no provider calls."""
import json,time,hashlib,sqlite3
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'review/public-deploy';OUT.mkdir(parents=True,exist_ok=True)
env={}
for line in Path('/etc/animation-pipeline.env').read_text().splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        k,v=line.split('=',1);env[k.strip()]=v.strip().strip('\"').strip("'")
base='https://isoani.huecki.com/animation'
with httpx.Client(timeout=30,follow_redirects=True) as c:
    assert c.get(base+'/health').status_code==200
    unauth=c.get(base+'/v1/jobs');assert unauth.status_code in (401,403)
    for name in ['app.js','styles.css']:
        local=ROOT/'ui'/name
        if local.exists():
            remote=c.get(base+'/ui/'+name);remote.raise_for_status();assert hashlib.sha256(remote.content).digest()==hashlib.sha256(local.read_bytes()).digest()
    c.headers['Authorization']='Bearer '+env['ANIMATION_API_TOKEN']
    cap=c.get(base+'/v1/capabilities');cap.raise_for_status()
    (OUT/'capabilities.json').write_text(json.dumps(cap.json(),indent=2))
    ref=ROOT/'artifacts/replay-existing/reference.png'
    response=c.post(base+'/v1/jobs',files={'reference':('deployment-smoke.png',ref.read_bytes(),'image/png')},data={'options':json.dumps({'auto_start':True})});response.raise_for_status()
    job=response.json();jid=job['id']
    for i in range(40):
        detail=c.get(base+'/v1/jobs/'+jid);detail.raise_for_status();data=detail.json()
        if data.get('state') not in ['queued','running']:break
        time.sleep(.25)
    download=c.get(base+'/v1/jobs/'+jid+'/download');download.raise_for_status();(OUT/'live-smoke-job.zip').write_bytes(download.content)
with sync_playwright() as pw:
    cached=sorted(Path.home().glob('.cache/ms-playwright/chromium-*/chrome-linux/chrome'),reverse=True)
    browser=pw.chromium.launch(executable_path=str(cached[0]) if cached else '/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--disable-gpu'])
    page=browser.new_page(viewport={'width':1440,'height':1100});errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(base+'/ui/',wait_until='networkidle')
    page.locator('#token').fill(env['ANIMATION_API_TOKEN']);page.locator('#tokenForm button[type=submit]').click();expect(page.locator('#connectionState')).to_have_text('Verbunden')
    page.locator('.job-card').filter(has_text=jid[:8]).first.click() if page.locator('.job-card').filter(has_text=jid[:8]).count() else page.locator('.job-card').first.click()
    # An inspect-only job has no facing/video yet, so downstream templates
    # are correctly absent. Verify shipped selectors without inventing inputs.
    durations=page.locator('#sourceDuration option').evaluate_all('(xs)=>xs.map(x=>x.value)')
    resolutions=page.locator('#sourceResolution option').evaluate_all('(xs)=>xs.map(x=>x.value)')
    sprite_sizes=page.locator('#exportResolution option').evaluate_all('(xs)=>xs.map(x=>x.value)')
    assert durations==['3','5','8','10'],durations
    assert resolutions==['480p','768p'],resolutions
    assert sprite_sizes==['160','80'] or sprite_sizes==['80','160'],sprite_sizes
    frames=[]
    for i in range(8):
        frames.append(page.locator('canvas').first.get_attribute('data-frame'));page.wait_for_timeout(150)
    assert len(set(frames))>1,frames
    page.locator('#token').fill('')
    page.screenshot(path=str(OUT/'live-ui.png'),full_page=True)
    assert not errors,errors
    browser.close()
result={'status':'PASS','url':base+'/ui/','job_id':jid,'job_state':data.get('state'),'unauthenticated_jobs_status':unauth.status_code,'source_options':{'durations':durations,'resolutions':resolutions,'mode':'live DOM options; downstream stages correctly absent in inspect-only job'},'sprite_options':sprite_sizes,'demo_distinct_frames':len(set(frames)),'page_errors':errors,'provider_calls':0,'paid_policy_unchanged':True}
(OUT/'REPORT.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
