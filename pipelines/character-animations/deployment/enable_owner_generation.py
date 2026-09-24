from pathlib import Path
import os,sys,shlex,sqlite3,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from real_cold_e2e import load_keys
key,ws=load_keys()
p=Path('/etc/animation-pipeline.env')
old=p.read_text();env={}
for line in old.splitlines():
    if '=' in line and not line.startswith('#'):
        k,v=line.split('=',1);env[k]=shlex.split(v)[0] if v else ''
assert env.get('ANIMATION_API_TOKEN')
root=Path(__file__).resolve().parents[1]
backup=root/'var/paid-enable-env.backup';fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.write(fd,old.encode());os.close(fd)
env.update(ANIMATION_PAID_ENABLED='1',ANIMATION_MAX_STAGE_USD='0.50',ANIMATION_REVIEW_ENABLED='1',ANIMATION_REVIEW_MAX_USD='0.05',ANIMATION_REVIEW_MAX_INPUT_TOKENS='50000',ANIMATION_REVIEW_MAX_OUTPUT_TOKENS='1200',ANIMATION_REVIEW_MODEL_METADATA_FILE=str(root/'var/reviewer-model-metadata.json'),ANIMATION_REMOVAL_MAX_INFLIGHT='5',OPENROUTER_API_KEY=key,WAVESPEED_API_KEY=ws)
assert all('\n' not in v and '\r' not in v for v in env.values())
content=''.join(k+'='+json.dumps(v)+'\n' for k,v in env.items())
fd=os.open(p,os.O_WRONLY|os.O_TRUNC,0o600);os.fchmod(fd,0o600);os.write(fd,content.encode());os.close(fd)
print('Owner token retained; provider credentials configured without disclosure; stage cap0.50 USD,review cap0.05 USD. No paid requests.')
