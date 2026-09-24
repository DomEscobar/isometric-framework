"""Explicit OpenRouter JSON-vision adapter. No secret returned, persisted, or retried."""
import json
import os
from pathlib import Path
from decimal import Decimal
from typing import Literal
import httpx
from pydantic import Field
from style_specs import Strict
from evaluations import validate_model

class ReviewerConfig(Strict):
    adapter: Literal['openrouter-json-vision-v1']='openrouter-json-vision-v1'
    model: str=Field(default='google/gemini-3.8-flash',min_length=3,max_length=150)
    auth: Literal['environment','hermes_pool']='environment'
    auth_label: str | None=None
    enabled: bool=False

class Reviewer:
    def __init__(self,root,request=None):
        path=Path(root)/'reviewer-config.json'
        self.config=ReviewerConfig.model_validate(json.loads(path.read_bytes()) if path.exists() else {})
        self.transport=request;self._key=None
    def key(self):
        if self._key:return self._key
        if self.config.auth=='environment':key=os.environ.get('OPENROUTER_API_KEY','')
        else:
            if not self.config.auth_label:raise ValueError('explicit credential label required')
            path=Path(os.environ.get('HERMES_HOME') or '/root/.hermes')/'auth.json'
            pool=json.loads(path.read_bytes()).get('credential_pool',{}).get('openrouter',[])
            entries=[e for e in pool if isinstance(e,dict) and e.get('label')==self.config.auth_label and e.get('access_token') and (e.get('base_url') or 'https://openrouter.ai/api/v1').rstrip('/')=='https://openrouter.ai/api/v1']
            if len(entries)!=1:raise ValueError('selected credential unavailable')
            key=entries[0]['access_token']
        if not key:raise ValueError('review authentication missing')
        self._key=key;return key
    def request(self,method,path,body=None):
        if self.transport:return self.transport(method,path,body)
        try:
            with httpx.Client(timeout=180,follow_redirects=False) as c:
                r=c.request(method,'https://openrouter.ai/api/v1'+path,headers={'Authorization':'Bearer '+self.key()},json=body)
                if r.status_code!=200:raise ValueError('provider request failed')
                return r.json()
        except Exception:raise ValueError('Review provider request failed; no automatic retry; retain any reservation.') from None
    def preflight(self):
        self.request('GET','/auth/key') # free authenticated probe BEFORE metadata and any paid POST
        models=self.request('GET','/models')['data']
        meta=next((m for m in models if m['id']==self.config.model),None)
        if not meta:raise ValueError('configured review model absent from live catalog')
        validate_model(meta)
        return meta
    def post(self,body):
        if not self.config.enabled or body.get('model')!=self.config.model:raise ValueError('review disabled or model mismatch')
        return self.request('POST','/chat/completions',body)
