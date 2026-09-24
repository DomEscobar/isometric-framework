"""WaveSpeed REST adapter. Secrets never enter request records or error messages.
No automatic retries. Only discover/quote are free metadata operations.
"""
import os
import re
import socket
import ipaddress
from urllib.parse import urlparse
import httpx

MODEL = 'bytedance/seedream-v5.0-lite/edit'


def public_url(url):
    p=urlparse(url)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None,443):
        raise ValueError('provider media URL must be public HTTPS')
    addresses=socket.getaddrinfo(p.hostname,443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('private media address rejected')
    return url


class WaveSpeed:
    requires_size=True
    def __init__(self,key=None,transport=None):
        self.key=key if key is not None else os.environ.get('WAVESPEED_API_KEY','')
        self.transport=transport

    @property
    def authenticated(self):
        return bool(self.key)

    def request(self,method,path,body=None):
        if not self.authenticated:
            raise ValueError('provider authentication missing')
        if self.transport:
            return self.transport(method,path,body)
        try:
            with httpx.Client(timeout=45,follow_redirects=False) as c:
                r=c.request(method,'https://api.wavespeed.ai/api/v3'+path,
                            headers={'Authorization':'Bearer '+self.key},json=body)
                r.raise_for_status()
                value=r.json()
                if value.get('code') != 200: raise ValueError('provider response not successful')
                return value['data']
        except Exception:
            # Raw exception/body can contain signed URLs, headers or credentials.
            raise ValueError('provider request failed; no automatic retry') from None

    def discover(self):
        model_id=getattr(self,'model_id',MODEL)
        models=self.request('GET','/models')
        model=next((m for m in models if m['model_id']==model_id),None)
        if not model: raise ValueError('configured model is absent from live catalog')
        schema=next(s['request_schema'] for s in model['api_schema']['api_schemas'] if s['type']=='model_run')
        props=schema.get('properties',{})
        input_key='image_urls' if 'image_urls' in props else 'images' if 'images' in props else None
        if not {'prompt','output_format'} <= props.keys() or not input_key:raise ValueError('live schema incompatible; adapter review required')
        if set(schema.get('required',[]))-{'prompt','image_urls','images','output_format','size'}:
            raise ValueError('live schema incompatible; adapter review required')
        if 'png' not in props['output_format'].get('enum',[]):
            raise ValueError('lossless PNG output unavailable')
        if getattr(self,'requires_size',True) and 'size' not in props:
            raise ValueError('explicit pixel size contract missing')
        return schema

    def quote(self,inputs):
        return self.request('POST','/model/price',{'model_id':getattr(self,'model_id',MODEL),'inputs':inputs})

    def submit(self,inputs):
        return self.request('POST','/'+getattr(self,'model_id',MODEL),inputs)

    def poll(self,prediction_id):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,150}',prediction_id): raise ValueError('invalid prediction id')
        return self.request('GET','/predictions/'+prediction_id+'/result')

    def upload(self,raw,name):
        ticket=self.request('POST','/media/uploads',{'filename':name,'size':len(raw),'content_type':'image/png'})
        up=ticket['upload']
        if up['method'] != 'PUT': raise ValueError('unsupported upload method')
        url=public_url(up['url'])
        # Never forward provider bearer to storage/CDN. No redirects or retries.
        headers=up.get('headers',{})
        if any(k.lower() not in ('content-type','if-none-match','x-amz-acl') for k in headers):
            raise ValueError('unexpected storage headers; review required')
        try:
            r=httpx.put(url,content=raw,headers=headers,timeout=60,follow_redirects=False)
            r.raise_for_status()
        except Exception:
            raise ValueError('media upload failed; no generation submitted') from None
        return public_url(ticket['download_url'])

    def download(self,url):
        url=public_url(url)
        try:
            with httpx.stream('GET',url,timeout=60,follow_redirects=False) as r:
                r.raise_for_status(); parts=[]; size=0
                for chunk in r.iter_bytes():
                    size += len(chunk)
                    if size > 8_000_000: raise ValueError('output exceeds 8 MB')
                    parts.append(chunk)
                return b''.join(parts)
        except Exception:
            raise ValueError('output download failed; resume same prediction, never regenerate') from None
