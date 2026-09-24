#!/usr/bin/env python3
import json, hashlib
from datetime import datetime
from pathlib import Path

root=Path(__file__).resolve().parents[1]
out=root/'review/real-cold-e2e-01'
report=json.loads((out/'REPORT.json').read_text())
receipt=json.loads((out/'source-request-receipt.json').read_text())
analysis=json.loads((out/'local-candidate-analysis.json').read_text())
ledger=json.loads((out/'cost-ledger.json').read_text())
parse=lambda value: datetime.fromisoformat(value.replace('Z','+00:00'))
submit_start=receipt['timings'][1]['started_utc']
stop=report['ended_at_utc']
submit_to_stop=(parse(stop)-parse(submit_start)).total_seconds()
download=next(x for x in receipt['timings'] if x['phase']=='download')
provider_generation=(parse(download['started_utc'])-parse(receipt['timings'][1]['finished_utc'])).total_seconds()
timings={
  'schema':'real-cold-e2e-timings-v1','cold_timing_start':'actual source submission start','started_at_utc':submit_start,
  'ended_at_utc':stop,'total_seconds':round(submit_to_stop,6),'artifact_ready':False,'ci_included':False,
  'stages':[
    {'stage':'source_upload_before_timed_window','duration_seconds':receipt['timings'][0]['duration_seconds']},
    {'stage':'source_submit','duration_seconds':receipt['timings'][1]['duration_seconds']},
    {'stage':'source_queue_generation_poll_wait','duration_seconds':round(provider_generation,6)},
    {'stage':'source_download','duration_seconds':download['duration_seconds']},
    next(x for x in report['stages'] if x['stage']=='automatic_local_candidate_analysis'),
    {'stage':'openrouter_reviewer','status':'not_run_local_hard_rejection','duration_seconds':0},
    {'stage':'selected_frame_extraction','status':'not_run','duration_seconds':0},
    {'stage':'background_removal','status':'not_run','duration_seconds':0},
    {'stage':'normalize_pack_verify','status':'not_run','duration_seconds':0},
    {'stage':'api_download_zip','status':'not_run','duration_seconds':0},
  ],
  'interventions':[{'reason':'preflight report-key implementation defect before any paid call','duration_excluded_from_cold_timing':True,'evidence_dir':'preflight-failure-01'}],
}
(out/'timings.json').write_text(json.dumps(timings,indent=2,sort_keys=True)+'\n')
report.update({
  'status':'failed_source_rejected_before_reviewer','failure_stage':'automatic_local_candidate_analysis',
  'failure_reason':'no_complete_orientation_stable_loop_candidate','artifact_ready':False,
  'cold_source_submission_to_rejection_seconds':round(submit_to_stop,6),
  'reviewer_calls':0,'remover_calls':0,'selected_indices':None,'final_atlas':None,'api_completion':False,'api_download_zip':False,
  'diagnostic':{
    'candidate_count':0,'rejected_candidate_count':len(analysis['rejected_candidates']),
    'all_bounded_shortlist_rejections':'orientation_drift',
    'top_rejected_bounds_native':[analysis['rejected_candidates'][0]['start_source_frame_index'],analysis['rejected_candidates'][0]['end_source_frame_index']],
    'top_head_skin_horizontal_centroid_range':analysis['rejected_candidates'][0]['source_pose_orientation']['head_skin_horizontal_centroid_range'],
    'observed_ranges_across_rejected_shortlist':{
      'head_skin_horizontal_centroid_range_min':min(x['source_pose_orientation']['head_skin_horizontal_centroid_range'] for x in analysis['rejected_candidates']),
      'head_skin_horizontal_centroid_range_max':max(x['source_pose_orientation']['head_skin_horizontal_centroid_range'] for x in analysis['rejected_candidates']),
    },
    'manual_contact_sheet_observation':'No clipping or gross identity loss was visible; the sampled contact sheet appears broadly NE-stable, so the exact blocking signal may be over-sensitive to head-skin centroid movement. The gate was not weakened and no candidate was forced through.',
  },
  'retained_evidence':{'source_video':'source-video.mp4','source_contact_sheet':'source-contact-sheet.png','source_3loops':'source-3loops.mp4','analysis':'local-candidate-analysis.json','immutable_request_receipt':'source-request-receipt.json'},
  'source_media_probe':{'width':768,'height':768,'video_fps':24.0,'frame_count':124,'duration_seconds':5.167},
  'tests':{'command':'.venv/bin/python -m pytest tests -q','passed':108,'failed':0,'warnings':2,'pytest_seconds':200.60},
  'cost_summary':{'source_discounted_quote_usd':0.2,'source_undiscounted_quote_usd':0.4,'source_actual_charge_known':False,'incremental_known_billed_usd':ledger['known_billed_usd'],'incremental_open_liability_usd':ledger['open_liability_usd'],'incremental_maximum_accounted_usd':ledger['maximum_accounted_usd'],'prior_maximum_accounted_usd':ledger['prior_reconciliation']['maximum_accounted_usd'],'cumulative_maximum_accounted_usd':round(ledger['prior_reconciliation']['maximum_accounted_usd']+ledger['maximum_accounted_usd'],9),'cumulative_ceiling_usd':ledger['cumulative_ceiling_usd']},
  'parent_visual_inspection':'Fresh source contact sheet inspected. No final cutout/atlas visual inspection exists because the mandatory local source gate stopped the run.',
  'visual_quality_certified':False,'perfect_claimed':False,
})
(out/'REPORT.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
lines=[
'# Real cold end-to-end run 01','',
'Status: FAILED AT SOURCE GATE — no final atlas or ZIP was manufactured.','',
'## Measured result','',
f'- Fresh MiniMax H3 prediction: `{receipt["prediction_id"]}`.',
f'- Source request: 5 s / 768p / seed `{receipt["request"]["seed"]}`; downloaded file: 768×768, 24 FPS, 124 video frames, 5.167 s, SHA-256 `{receipt["output"]["sha256"]}`.',
f'- Actual source submission start → local rejection: {submit_to_stop:.6f} s.',
f'- Source stage invocation (upload + submit + provider wait/polls + download): {next(x for x in report["stages"] if x["stage"]=="source_queue_generation_download")["duration_seconds"]:.6f} s.',
f'- Local automatic analysis: {next(x for x in report["stages"] if x["stage"]=="automatic_local_candidate_analysis")["duration_seconds"]:.6f} s.',
'- Reviewer, extraction, removals, cache ingest, spatial export, final visual loop and API ZIP download: not run because the source gate rejected first.','',
'## Exact blocker','',
'- Hard failure: `no_complete_orientation_stable_loop_candidate`.','- Selectable candidates: 0; retained rejected shortlist: 50; every retained candidate failed `orientation_drift`. ',
f'- Top rejected interval: native [{analysis["rejected_candidates"][0]["start_source_frame_index"]},{analysis["rejected_candidates"][0]["end_source_frame_index"]}); head-skin horizontal-centroid range {analysis["rejected_candidates"][0]["source_pose_orientation"]["head_skin_horizontal_centroid_range"]:.6f}.',
f'- Across the retained shortlist that diagnostic ranged {report["diagnostic"]["observed_ranges_across_rejected_shortlist"]["head_skin_horizontal_centroid_range_min"]:.6f}–{report["diagnostic"]["observed_ranges_across_rejected_shortlist"]["head_skin_horizontal_centroid_range_max"]:.6f}.',
'- Contact-sheet inspection found no clipping or gross identity loss and looked broadly NE-stable. This makes the head-skin-centroid gate a plausible false-positive source, but it was not weakened and no candidate was manually forced through.','',
'## Cost','',
'- Fresh source quote: USD 0.20 discounted / USD 0.40 undiscounted; authoritative charge not returned.',
'- Incremental known billed: USD 0.000000000.',
'- Incremental open liability retained: USD 0.500000000 (source cap reservation).',
'- Reviewer/remover reservation released before calls: reviewer calls 0, remover calls 0.',
f'- Prior reconciled maximum: USD {ledger["prior_reconciliation"]["maximum_accounted_usd"]:.9f}; cumulative maximum now USD {report["cost_summary"]["cumulative_maximum_accounted_usd"]:.9f} of fresh FX ceiling USD {ledger["cumulative_ceiling_usd"]:.4f}.','',
'## Evidence','',
'- `source-request-receipt.json` (mode 0444)', '- `source-video.mp4`', '- `source-contact-sheet.png`', '- `source-3loops.mp4`', '- `local-candidate-analysis.json`', '- `redacted-trace.jsonl`', '- `timings.json`', '- `cost-ledger.json`','',
'## Verification','',
'- Targeted bridge tests passed before the run.', '- Final full suite after code changes: 108 passed, 2 dependency warnings, 0 failures in 200.60 s.', '- Public paid policy, game and deployment unchanged.', '- No retry, fallback, manually chosen interval, human-review stand-in, final atlas, API completion, or perfection claim.',''
]
(out/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({'report':str(out/'REPORT.md'),'status':report['status'],'submit_to_rejection_seconds':submit_to_stop},indent=2))
