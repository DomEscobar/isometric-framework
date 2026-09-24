"""Bounded, explicit secondary image review. Never grants production approval.
Caller supplies live metadata and authenticated POST transport. Secrets never persist.
Reservations share Generation's SQLite transaction and are never auto-released.
"""
import base64
import io
import json
import os
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from PIL import Image
from artifacts import canonical,digest


def verdict(content):
    try:
        parsed=json.loads(content)
        if not isinstance(parsed,dict): raise ValueError()
    except (ValueError,TypeError): parsed={}
    allowed={'pass','reject','needs_attention'}
    return dict(status='needs_attention',production_approved=False,
        semantic_verdict=parsed.get('semantic_verdict') if parsed.get('semantic_verdict') in allowed else 'needs_attention',
        visual_verdict=parsed.get('visual_verdict') if parsed.get('visual_verdict') in allowed else 'needs_attention',
        findings=parsed.get('findings',[]),note='Secondary model evidence only. Parent/user approval remains separate.')


def run_review(g,rid,images,prompt,metadata,post,max_tokens=2048,exact=False):
    if not 1 <= len(images) <= (20 if exact else 4) or not 1 <= max_tokens <= 4096 or len(prompt)>(50000 if exact else 12000):
        raise ValueError('review input bounds exceeded')
    if 'image' not in metadata['architecture']['input_modalities']: raise ValueError('model lacks image input')
    directory=g.root/'reviews'/rid
    directory.mkdir(parents=True,exist_ok=True)
    if (directory/'intent.json').exists(): raise ValueError('review already attempted; inspect receipt; no retries')
    inputs=[];content=[{'type':'text','text':prompt}]
    for path,role in images:
        raw=Path(path).read_bytes()
        if len(raw)>10_000_000: raise ValueError('review image exceeds input cap')
        im=Image.open(io.BytesIO(raw)).convert('RGB')
        if im.width*im.height>8_000_000:raise ValueError('review image pixel cap')
        original=list(im.size)
        if not exact:im.thumbnail((1280,1280),Image.Resampling.LANCZOS)
        stream=io.BytesIO();im.save(stream,format='PNG');review_raw=stream.getvalue()
        if exact:review_raw=raw
        index=len(inputs);(directory/f'input-{index}.png').write_bytes(review_raw)
        inputs.append(dict(role=role,sha256=digest(raw),source_size=original,review_sha256=digest(review_raw),review_size=list(im.size),processing='exact retained bytes; no resizing' if exact else 'bounded aspect-preserving LANCZOS thumbnail; source retained separately'))
        content.extend([{'type':'text','text':role},{'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(review_raw).decode()}}])
    pricing=metadata['pricing'];ctx=metadata['context_length']
    # Full context input liability + capped output: conservative, not an estimated token count.
    amount=Decimal(str(pricing['prompt']))*ctx+Decimal(str(pricing['completion']))*max_tokens
    reserve=int((amount*1000000).to_integral_value(rounding=ROUND_CEILING))
    body=dict(model=metadata['id'],messages=[{'role':'user','content':content}],max_tokens=max_tokens,temperature=0,response_format={'type':'json_object'},reasoning={'effort':'low'})
    if exact and 'reasoning' not in metadata.get('supported_parameters',[]):body.pop('reasoning')
    binding=dict(inputs=inputs,prompt_sha256=digest(prompt.encode()),request_sha256=digest(canonical(body)),model=metadata['id'],metadata_sha256=digest(canonical(metadata)),max_tokens=max_tokens,reservation_basis='full model context input price plus maximum output; retained conservatively')
    g.reserve_review(rid,reserve,binding)
    with (directory/'intent.json').open('xb') as f:
        f.write(canonical(binding));f.flush();os.fsync(f.fileno())
    (directory/'request.json').write_bytes(canonical(body))
    (directory/'metadata.json').write_bytes(canonical(metadata))
    response=post(body) # ONE call. Unknown failure retains reservation+intent and cannot retry.
    with (directory/'receipt.json').open('xb') as f:
        f.write(canonical(response));f.flush();os.fsync(f.fileno())
    choices=response.get('choices') or [{}]
    choice=choices[0]
    valid=response.get('model')==metadata['id'] and choice.get('finish_reason')=='stop' and not response.get('error')
    text=choice.get('message',{}).get('content','') if valid else ''
    result=dict(inputs=inputs,response=response,verdict=verdict(text),reserve_microusd=reserve,binding=binding)
    (directory/'review.json').write_bytes(canonical(result))
    return result
