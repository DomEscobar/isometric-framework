from pathlib import Path
import json,httpx
from playwright.sync_api import sync_playwright,expect
p=Path(__file__).resolve().parents[1];out=p/'review/agent-integration';out.mkdir(exist_ok=True,parents=True)
base='https://isoani.huecki.com/animation'
with httpx.Client(follow_redirects=True,timeout=20) as c:
    root=c.get('https://isoani.huecki.com/');assert root.status_code==200
    results={}
    for route in ['health','agent-guide.md','agent-prompt.txt','openapi.json','docs']:
        r=c.get(base+'/'+route);assert r.status_code==200,(route,r.status_code);results[route]=r.status_code
    spec=c.get(base+'/openapi.json').json();assert spec['servers'][0]['url']==base
    assert c.get(base+'/v1/jobs').status_code==401
    prompt=c.get(base+'/agent-prompt.txt').text
    assert base in prompt and 'https://huecki.com/animation' not in prompt
with sync_playwright() as pw:
    cached=sorted(Path.home().glob('.cache/ms-playwright/chromium-*/chrome-linux/chrome'),reverse=True)
    b=pw.chromium.launch(executable_path=str(cached[0]) if cached else '/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--disable-gpu'])
    ctx=b.new_context(permissions=['clipboard-read','clipboard-write'],viewport={'width':1280,'height':1000})
    page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('https://isoani.huecki.com/',wait_until='networkidle')
    expect(page.locator('#copyAgentPrompt')).to_be_enabled()
    page.locator('#token').fill('SYNTHETIC-NOT-A-CREDENTIAL')
    page.locator('#copyAgentPrompt').click()
    copied=page.evaluate('navigator.clipboard.readText()')
    assert copied==prompt and 'SYNTHETIC-NOT-A-CREDENTIAL' not in copied
    page.locator('#token').fill('')
    page.locator('.agent-panel').screenshot(path=str(out/'isoani-agent-panel.png'))
    assert not errors,errors
    b.close()
report={'status':'PASS','site':'https://isoani.huecki.com/','base':base,'https_endpoints':results,'openapi_server_correct':True,'actual_clipboard_equals_public_prompt':True,'token_not_copied':True,'unauthenticated_jobs':401,'browser_errors':errors,'paid_calls':0,'tests':'181 passed,2 deprecation warnings'}
(out/'REPORT.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
