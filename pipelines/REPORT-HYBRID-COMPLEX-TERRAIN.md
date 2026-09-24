# Complex multi-level terrain — PRODUCTION SUCCEEDED (chain v1→v2→v3→sampling-repair)

Owner request 2026-09-22: „Ok jetzt mal komplexere terrain". Delivered: 24×20 isometric
village terrain with **three elevation levels (0/8/16), two real stair transitions, a
water pond (level 0), curved paths, a paved plaza and an elevated terrace plaza**.

## Run chain (each immutable and fail-closed)
1. `d275ba20f25d4aec930a092110c339cd` — planner truncated at the historical 8192 default
   (`finish_reason: length`, 7861/8192 reasoning tokens; content cut mid-array). Honest
   stop, no image bought. Retained receipt settled later against raw billing
   (actual USD 0.03276975, `4c36445aed…`).
2. `4fa30c195c8f41ae8e403cfe1ade0acd` — planner re-run with the proven 32768/medium token
   policy (new `token_policy` field, TDD): complete valid plan (6 semantics incl. water,
   heights 0/8/16, 4 stair transitions). Stopped only because the planner wrote `walls`
   (plural). Principled fix: `walls` alias normalized like the existing `cliff_wall` alias
   (ambiguous/missing semantics still fail closed). Receipt settled (actual USD 0.0233445).
3. `1be76cabfa584293be43c418653d9a40` — receipt-bound continuation reusing the v2 planner
   call (`d26dd05f5d…`) with NO new planner POST. One image-to-image board edit
   (image-0, water included) → extraction 7/7 PASS → sample review 7/7 PASS (stepped
   terraces + water basin explicitly noted) → final review 6/7 (scale-only fail with a
   valid hash-bound local_sampling plan) — stopped because the run froze
   `max_local_corrections=0`. No image spent beyond the one.
4. `bf0775b583fc44d689907e042b29f96c` — bounded sampling-repair child (new
   `hybrid_sampling_repair.py`, TDD 5 tests): deterministic re-sampling of square+water
   32→64 px/unit (reviewer's own plan, factor ≤2, crops unchanged), then the two mandatory
   re-reviews: **both 7/7 PASS**. `succeeded`, `production_approved=true`.

## Verification of the served production ZIP (`evidence/hybrid-sampling-repair/`)
- `production-download.zip` sha256 `2b5081cdc419d0cb39f6e9a2f920c3b0255a30e13c6d841bf055f2f279609679`,
  10922950 bytes; 67/67 checksums OK; extracted `source/rebuild.py` rebuild **byte-identical**;
  extracted offline HTML navigation over the height/transition graph: **1920 edges,
  33 moves, 0 errors** (`zip-verification.json`).
- Native captures (Playwright, DPR 1): `offline-gameplay-native.png` (1104×656 canvas),
  `before-gameplay-native.png` (candidate-0), `after-gameplay-native.png` (candidate-1),
  `sample-after-gameplay-native.png`, `final-status.png`, `final-ui.png` (incl. reload proof).

## Calls and billing (central ledger, holds retained)
| call | generation | held µUSD | actual USD |
|---|---|---|---|
| v1 planner `4c36445aed…` | gen-1790093769-5SPq8e67c2ZizysN51tV | 817152 | 0.03276975 (settled) |
| v2 planner `d26dd05f5d…` | gen-1790094080-qw6666wFKk0sLfDqgFtP | 909312 | 0.0233445 (settled) |
| v3 image-0 `8a94c88d8a…` | (WaveSpeed edit) | 11000 | quote 0.011 |
| v3 extraction-0 `38c6a3dd0c…` | gen-1790094777-CAM97lwb1nGgQQKuTnbg | 909312 | 0.0190275 |
| v3 review_sample-0 `aabdc6d57a…` | gen-1790094813-xuauxoiyaKEozVS0EguK | 909312 | 0.01925475 |
| v3 review_final-0 `af108e162b…` | gen-1790094889-0OlqgNRE8wdg2oZ8SFaV | 909312 | 0.0204105 |
| child review_sample-0-local-1 `6427aba604…` | gen-1790096856-0IgNsIx07yPdl7XYpopd | 909312 | 0.02409675 |
| child review_final-0-local-1 `f80ae53ede…` | gen-1790096944-NlZ1eTxs8Y4fjT0OGpgl | 909312 | 0.0133485 |

Earlier evidence-backed settlements (raw-hash bound) released 3442279µUSD surplus from 4
known receipts. **Effective held now 18335561µUSD of the USD20 project total; remaining
USD 1.664439.** The 2 legacy receipt-less unknowns remain fully reserved and untouched.

## Test/verify commands
```
python3 tools/test_hybrid_isolated.py                      # 362 passed
python3 tools/verify_production_zip.py bf0775b583fc44d689907e042b29f96c evidence/hybrid-sampling-repair
python3 tools/lookup_sampling_repair_billing.py
python3 tools/settle_planner_receipts.py                    # read-only re-validation of settlements
curl -s http://127.0.0.1:48765/api/hybrid-runs/bf0775b583fc44d689907e042b29f96c
```

## Honest boundaries
Model gates (sample + final, twice) passed with valid citations; deterministic replay,
byte-identical rebuild and offline navigation are proven. NOT proven: owner acceptance
(user_acceptance pending), general style transfer, WaveSpeed image billing (quote only).
Reviews are model verdicts. No public deployment; production export is the service
download endpoint only.
