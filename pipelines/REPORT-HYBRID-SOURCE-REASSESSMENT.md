# Retained-source reassessment — live re-evaluation of archived source-1, honest sample-gate stop

## Outcome
Service-owned run **b9a94348e6404358b353d3b3c5fd5f24** (immutable child of sealed archive
**a3d4ce60a6db4bc7a2702217d62ce2db**) re-evaluated archived **source-1** with the corrected
extractor, with **zero image purchases** (images stayed **3/3**, lifetime calls **10/12**).

1. Fresh full-board extraction (model `google/gemini-3.8-flash`, 32768 max_tokens, reasoning
   medium) now **PASSES all five materials** on source-1 (`aaf9cbce…00511b6`), including
   stairs: *"Flat face-on unlit stone surface interior without steps, risers, perspective, or
   cast shadows, meeting the source contract."* The proven architecture/material role
   contradiction is fixed at extraction level.
2. The independent sample review then **FAILED** with real findings: `layout_fidelity: fail`
   (bottom-left segment carries the grey stairs band where the guide shows a tan path zone;
   no functional stairs connect the heights to the elevated terrace), `materials: fail`
   (stairs surface judged against the planner's "broad stone stair treads with visible
   risers" spec), `scale: fail` (square flagstones oversized vs the 64px actor). PASS:
   pixel_style, repetition, lighting, walkable_clearance. `local_sampling: null`.
3. With reassessment scope (`no_new_images`, `no_local_retries`, `followup_call_limit=3`) the
   worker stopped terminally: **needs_attention**, stop reason
   `Fresh review rejected retained-source assembly; no extra review or image authorized: layout_fidelity: fail, materials: fail, scale: fail`.
   No sample PASS, no final render, no final review, **no production/diagnostic export
   reached the production gate** (the sample's `diagnostic.zip` is unapproved sample evidence).

## Service-owned selection rule (no operator hand-picking)
`hybrid_reassessment.py` selects the **newest archived whole source whose sole rejection is the
documented contradiction class** (`flat-material-role/2`): affirmative flat-stone observation
followed by missing architecture, matching the proven prompt/validator contradiction. On real
data only attempt 1 qualifies (attempt 2's wall FAIL is a real material defect and is skipped).
The original FAIL verdict and receipt bytes remain immutable; the invalidation is a **new
versioned validator event** (`original_decision_sha256=aad148a7…39f33a2`,
`original_verdict_preserved=true`, `production_approved=false`) — never rewritten into a PASS.
Fresh extraction output is stored separately (`crop-decision-1.json` vs
`historical-crop-decision-1.json`). Wrong hash, wrong binding, tampered request/decision,
stale/foreign parent, and image-role reservations all fail closed (tests
`test_archived_binding_detects_drift`, `test_selector_rejects_invalid_or_mixed_failure`,
`test_api_reassessment_whole_source_at_image_cap_immutable_parent`).

## Exact accounting (central ledger `data/generation.sqlite3`, no second budget)
- Held before: **10936256** microUSD; two new reservations **909312** each (full-context +
  32768 completion conservative); **held total 12754880 = USD 12.754880**. Remaining under the
  USD 20 project total: **USD 7.245120**. **Zero releases, zero settlements**; both legacy
  unknown receipt-less planner holds (817152 each) remain fully reserved and unsettled.
- Extraction-1: call `11634cdccddf46d67b5cced12a95b69080fc29fb8ee346b68b2e61d1751affc1`,
  generation `gen-1790088457-hfS8etfuJKq3KyeEmxcr`, held 0.909312, actual (receipt usage =
  authenticated billing GET) **USD 0.0150075**; prompt 1585, completion 854, reasoning 2768,
  native STOP; backend `google/gemini-3.8-flash-20260902`.
- Review-sample-1: call `0fdf6e2b4603ab9a5e6c0f9fa5d7877d5d71d8802f52e0ae28a205584fb824dc`,
  generation `gen-1790088493-6p7pvCDp8Fnc1EhVSUUB`, held 0.909312, actual **USD 0.03168525**;
  prompt 3394, completion 2662, reasoning 5718, native STOP; same backend.
- Actual billed sum **USD 0.04669275**, contained in the holds, not added. Budget for the
  bounded reassessment: 2727936 microUSD (3 conservative follow-ups); only 2 were used.
  Acknowledgment `3ab18207e7e8d8635f84743d908873a0bfce87863fc9cc02976dc44762da3739`
  binds the two legacy unknown liabilities — an acknowledgment, **not** settlement.

## Tests and verification
- `python3 tools/test_hybrid_isolated.py` → **341 passed** (330 previous + 11 reassessment
  tests, RED→GREEN completed from the interrupted worker's files; no test weakened).
- `python3 tools/verify_reassessment.py` → all checks green: historical rows field-for-field
  unchanged, exactly 2 new known-receipt calls, ledger/request-hash bindings, immutable
  parent verdict, versioned invalidation, images 3/3, terminal state.
- `python3 tools/precheck_reassessment.py` (read-only archive validation/selection replay),
  `python3 tools/lookup_reassessment_billing.py` (free authenticated billing GETs).
- Honest visual check of the real sample scene (this subagent, model `xiaomi/mimo-v2.6-pro`,
  via `vision_analyze`, not Astra): flat grey stairs band bottom-left, oversized flagstones,
  terrace edge without rendered stair geometry — consistent with the three FAIL findings.

## Artifacts (prefix /root/services/layout-terrain-pipeline/)
- `evidence/hybrid-source-reassessment/{new-run,authorization,launch-readback,live-metadata,billing-summary}.json`
  and `gen-1790088457-…-billing.json`, `gen-1790088493-…-billing.json`.
- `data/hybrid/b9a94348e6404358b353d3b3c5fd5f24/`: `source-reassessment.json` (binding +
  invalidation), `crop-decision-1.json` (fresh 5/5 pass), `historical-crop-decision-1.json`
  (preserved FAIL), `review_sample-1.json` (real review), `source-1.png`, `sample-1-0/`
  (scene/crops/guide/diagnostic.zip — unapproved sample evidence).
- `data/hybrid-source-reassessment-before.json` (0600 private pre-run snapshot),
  `HYBRID_SOURCE_REASSESSMENT_AUTHORIZATION.md`, this report.

## Remaining boundary (what is NOT proven)
No production ZIP, no playable deliverable: the sample gate honestly failed. The review's
`materials` criterion again judged the flat stairs source against the planner's final-scene
"treads/risers" descriptor — a role-descriptor ambiguity at the **review** layer, documented
but not overruled here; the independent `scale` and `layout_fidelity` failures alone block any
"sole contradiction" reassessment claim, so no second reassessment is authorized or possible
(one child per parent). No image was bought, no crop/source hand-picked, no citation invented,
no hold released, nothing deployed publicly. Mock suites prove behavior, not visual quality.
