#!/usr/bin/env python3
import sqlite3
from pathlib import Path
path = Path('/root/services/animation-pipeline/var/jobs.sqlite3')
con = sqlite3.connect(path)
active = con.execute("SELECT id,job_id,stage,state FROM stage_jobs WHERE state IN ('queued','running') ORDER BY created_at").fetchall()
print(f'active_stage_count={len(active)}')
for row in active:
    print(' '.join(str(value) for value in row))
raise SystemExit(1 if active else 0)
