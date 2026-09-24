#!/usr/bin/env python3
"""One frozen optimized cold acceptance run; never overwrite a prior attempt."""
import hashlib
import json
from pathlib import Path
import real_cold_e2e as harness

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'review/compact8-cold-01'
FILES = ['animation_review.py', 'pipeline.py', 'provider.py', 'quality_gates.py', 'runner.py', 'spatial_export.py', 'store.py', 'app.py', 'tools/real_cold_e2e.py', 'tools/latency_final_cold_run.py']

def prior():
    base = json.loads((ROOT / 'review/cadence-uninterrupted/phase2-fresh-uninterrupted/cost-ledger.json').read_text())
    probe = json.loads((ROOT / 'review/latency-step2/cost-ledger.json').read_text())
    # The probe ledger records its baseline and six new jobs. Retain all liabilities.
    return {'maximum_accounted_usd': 3.523446, 'sources': ['review/cadence-uninterrupted/phase2-fresh-uninterrupted/cost-ledger.json', 'review/latency-step2/cost-ledger.json', 'review/latency-final-cold/cost-ledger.json'], 'basis': 'deduplicated prior conservative total with all known charges and unresolved liabilities retained'}

def main():
    if OUT.exists():
        raise RuntimeError('Existing attempt: inspect receipts; no resubmission')
    hashes = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in FILES}
    frozen = {'files': hashes, 'frame_policy': '8', 'maximum_inflight': 5, 'incremental_cap_usd': 1.5, 'prior_conservative_usd': 3.523446, 'source_count_max': 1, 'review_count_max': 1, 'removal_count_max': 8, 'note': 'one new source, one review, eight fresh removals; public service unchanged'}
    freeze = ROOT / 'review/compact8-cold-01-freeze.json'
    freeze.write_text(json.dumps(frozen, indent=2)+'\n')
    harness.OUT = OUT
    harness.INCREMENTAL_CAP = 1.5
    harness.MAX_REMOVALS = 8
    harness.MAX_INFLIGHT = 5
    harness.PORT = 4418
    harness.BASE = 'http://127.0.0.1:4418'
    harness.prior_reconciliation = prior
    result = harness.run()
    if OUT.exists():
        (OUT/'FROZEN_RUN_CONFIG.json').write_bytes(freeze.read_bytes())
        unchanged = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == value for name,value in hashes.items()}
        (OUT/'freeze-verification.json').write_text(json.dumps(unchanged, indent=2)+'\n')
    return result

if __name__ == '__main__':
    raise SystemExit(main())
