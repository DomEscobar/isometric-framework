from pathlib import Path
import json, hashlib, subprocess, zipfile, sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import spatial_export
import threading
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'review/action-timing-01'
r=json.loads((p/'REPORT.json').read_text())
for size in (80,160):
    spatial_export._encode_preview(p,size,8/1.625,8,loop=False,frame_durations_seconds=r['selection']['frame_durations_seconds'])
name=r['outputs']['after']['file']
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(p/name)]))
assert float(probe['format']['duration'])==4.875
r['outputs']['after']['encoded_duration_seconds']=4.875
r['outputs']['after']['sha256']=hashlib.sha256((p/name).read_bytes()).hexdigest()
# Refresh package's existing members, preserving exact master-derived atlases.
zip_path=p/'action-timing-export.zip'
with zipfile.ZipFile(zip_path) as z:
    names=z.namelist()
with zipfile.ZipFile(p/'parent-package.tmp.zip','w',zipfile.ZIP_DEFLATED) as z:
    for member in names:
        z.write(p/member,member)
    if 'BEFORE-punch-untrimmed-uniform.mp4' not in names:
        z.write(p/'BEFORE-punch-untrimmed-uniform.mp4','BEFORE-punch-untrimmed-uniform.mp4')
(p/'parent-package.tmp.zip').replace(zip_path)
with zipfile.ZipFile(zip_path) as z: assert z.testzip() is None
r['outputs']['zip']['sha256']=hashlib.sha256(zip_path.read_bytes()).hexdigest()
(p/'REPORT.json').write_text(json.dumps(r,indent=2))
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass
server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(p)))
threading.Thread(target=server.serve_forever,daemon=True).start()
base=f'http://127.0.0.1:{server.server_port}'
with sync_playwright() as pw:
    cached=sorted(Path.home().glob('.cache/ms-playwright/chromium-*/chrome-linux/chrome'),reverse=True)
    browser=pw.chromium.launch(executable_path=str(cached[0]) if cached else '/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--disable-gpu'])
    page=browser.new_page(viewport={'width':900,'height':450})
    errors=[]
    page.on('pageerror',lambda error: errors.append(str(error)))
    page.goto(base + '/preview.html')
    page.wait_for_function('window.__animationVerification?.loaded')
    samples=[]
    for i in range(20):
        samples.append(page.evaluate("({state:{...window.__animationVerification},canvas:document.querySelector('canvas').toDataURL()})"))
        page.wait_for_timeout(100)
    state=page.evaluate('window.__animationVerification')
    assert state['loaded'] and state['textureDecoded'] and state['rectanglesInBounds'] and not state['errors'] and not errors
    assert state['frameAdvanceCount']==8
    distinct=len(set(s['canvas'] for s in samples))
    assert distinct>=6
    page.screenshot(path=str(p/'parent-manifest-player.png'))
    page.goto(base + '/comparison.html')
    page.wait_for_timeout(2000)
    video_state=page.evaluate("[...document.querySelectorAll('video')].map(v=>({src:v.getAttribute('src'),readyState:v.readyState,error:v.error?{code:v.error.code,message:v.error.message}:null,h264:v.canPlayType('video/mp4; codecs=\"avc1.64001F\"')}))")
    # This test Chromium has no H.264 decoder; exercise the same decoded
    # preview content via VP9 without mislabelling unsupported MP4 as PASS.
    page.evaluate("document.querySelectorAll('video').forEach((v,i)=>{v.src=i?'after.webm':'before.webm';v.load();v.play()})")
    page.wait_for_function("[...document.querySelectorAll('video')].every(v=>v.readyState>=2&&v.currentTime>0)")
    vp9_state=page.evaluate("[...document.querySelectorAll('video')].map(v=>({readyState:v.readyState,currentTime:v.currentTime,error:v.error}))")
    page.screenshot(path=str(p/'parent-comparison.png'))
    browser.close()
receipt={'status':'MANIFEST_PLAYER_PASS','comparison_video_state':video_state,'vp9_browser_playback':vp9_state,'browser_state':state,'sampled_distinct_poses':distinct,'page_errors':errors,'encoded_after_seconds':4.875,'zip_crc':'PASS','after_sha256':r['outputs']['after']['sha256'],'zip_sha256':r['outputs']['zip']['sha256'],'paid_calls':0}
(p/'PARENT-VERIFICATION.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt,indent=2))
