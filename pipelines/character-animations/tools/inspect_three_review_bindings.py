#!/usr/bin/env python3
import json, sqlite3
from pathlib import Path
ROOT = Path('/root/services/animation-pipeline')
ids = ['59b60dc6ff9f4016bd9a0a8a1c23efb9','65fb86b0719c4aa0bba4eb23572d0384','4b03c8eda59040938b2e7b41d2f21bdd']
con = sqlite3.connect(ROOT / 'var/jobs.sqlite3')
con.row_factory = sqlite3.Row
out = []
for sid in ids:
    row = con.execute('SELECT id,stage_job_id,job_id,status,record_json,created_at FROM automatic_reviews WHERE stage_job_id=?',(sid,)).fetchone()
    stage = con.execute('SELECT id,job_id,stage,state,error,created_at,claimed_at,finished_at FROM stage_jobs WHERE id=?',(sid,)).fetchone()
    item = {'stage': dict(stage) if stage else None, 'review': None, 'result_artifact': None}
    if row:
        saved = dict(row)
        record = json.loads(saved.pop('record_json'))
        saved['record_keys'] = sorted(record)
        saved['record'] = {k: record.get(k) for k in ('id','stage_job_id','server_request_binding','status','reason','response_id','provider','budget','source_sha256','source_revision','selected_candidate','selected_sampling')}
        item['review'] = saved
        result = ROOT / 'var' / row['job_id'] / 'automatic-review-result.json'
        if result.is_file():
            parsed = json.loads(result.read_text())
            item['result_artifact'] = {k: parsed.get(k) for k in ('status','approved','response_id','provider','budget','server_request_binding','selected_candidate','selected_sampling')}
    out.append(item)
print(json.dumps(out, indent=2))
