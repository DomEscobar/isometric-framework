"""Refresh public exact-model metadata without paid inference."""
import json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from animation_review import fetch_openrouter_model_metadata
p=Path(__file__).resolve().parents[1]/'var/reviewer-model-metadata.json'
m=fetch_openrouter_model_metadata()
tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(m,indent=2));tmp.chmod(0o600);os.replace(tmp,p)
print('Exact reviewer metadata refreshed; no inference request.')
