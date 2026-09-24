# Image-to-image material repair — PRODUCTION SUCCEEDED

## Outcome
Run **3c92b111114d479485d3aafe4991d441** (immutable child of reassessment
`b9a94348e6404358b353d3b3c5fd5f24`) finished **succeeded / production_approved=true**.
Owner wish quoted in `HYBRID_REASSESSMENT_REPAIR_AUTHORIZATION.md`:
„ich will das es jetzt funkruiniert und gut aussieht und das image to image immer
verwendet wird. auch bei merstufigem."

Exactly ONE image-to-image edit (Muse, role `image-3`) produced **source-3**
(`e8fe064516bb9745ed413cf5ceae80c2929c42e428030e0e66d0cb1b67053790`) from retained
source-1: finer flagstone pavers + richer coherent FLAT face-on stone for the stairs slot
(owner directive, explicitly NO treads/risers in the source; the renderer builds steps).
Correction evidence was strictly `review-material-actionable/1`: the cited scale finding
(crop-square) plus the labeled owner directive; the riser-demanding materials finding was
excluded as architecture-role conflict and the layout finding deferred to the renderer.

## What actually changed (all TDD, 355 isolated tests green)
1. `hybrid_sampling.py`: the sample geography now has a REAL stair transition
   (heights 0/8 along declared stair transitions, wall-material riser face) — the
   previous sample had `transitions: []` and no functional stairs ("auch bei mehrstufigem").
2. `hybrid_worker.py` review prompt: guide preview colors are technical placeholders,
   never material identity (the old `stairs` preview color is tan — the reviewer misread
   it as a path zone); the renderer builds tread/riser geometry; absence of treads/risers
   in the flat source is never a materials failure. The proven role contradiction is thus
   fixed at the review layer too, without touching any sealed verdict.
3. New `hybrid_reassessment_repair.py` + API `POST .../continue-repair` + worker dispatch:
   one bounded image-to-image repair continuation, lifetime counters carried (10→14/15
   calls, images 3→4/4 via explicit amendment; no further image possible — ledger-enforced).

## Results
- Fresh extraction on source-3: **5/5 PASS** (land/path/square/stairs/wall; stairs =
  flat face-on unlit stone, meeting the source contract).
- Sample review (`review_sample-3`): **7/7 PASS** — explicitly noting the two-step
  foreground transition, proportioned flagstones, seamless tiling.
- Final review (`review_final-3`): **7/7 PASS** — layout/elevations match the guide,
  all five materials cited, actor-scale correct.
- Worker verification: offline browser navigation **1152 graph edges, 24 moves, 0 errors**,
  diagnostic + production rebuild byte-identical. Independent re-verification of the
  served production ZIP (`evidence/hybrid-reassessment-repair/production-download.zip`,
  sha256 `300533601cca5cfc54f64eda499bae1198a3d65f0f9fd53ec03cea89ebf94761`, 11705957
  bytes): 63/63 checksums OK, extracted `source/rebuild.py` rebuild byte-identical,
  extracted offline HTML navigation 1152 edges/0 errors (`zip-verification.json`).

## Accounting (central ledger, nothing released)
- `image-3` call `ac70919ddd9342577262a5959d873d39e83eb131e690d0318fd78861b2528ab1`:
  quoted USD 0.011, held 11000µUSD (WaveSpeed; no independent billing return).
- `extraction-3` `fbe3218b884e0f773051ea081722302001afbee8b611f3fb051395ab5ad5d6e3` /
  `gen-1790091129-dvYOEeWJKNo7nUGpsaF1`: actual **USD 0.014613**, held 909312.
- `review_sample-3` `4d90c5c4cbbdf2889f5e9290e3877d64dcf3008e5f439dcc3df1741036b1d0dd` /
  `gen-1790091165-FLsAsvOmYWk9e20CmtjX`: actual **USD 0.0153435**, held 909312.
- `review_final-3` `37dd56b91e701d3c261841c261a9d245f0d8d513d8e5a716ec5f6ef61e10be97` /
  `gen-1790091214-NeK7uSLfdJ3SVLJNyoRo`: actual **USD 0.01386825**, held 909312.
- Held total now **15493816µUSD** of the USD20 project total; remaining **USD 4.506184**.
  Both legacy unknown holds remain fully reserved; acknowledgment
  `9179463bfe364b0df4433b3bcf01306b16753e5ec28a5a7c3096e729eda125a8` is not a settlement.

## Artifacts (prefix /root/services/layout-terrain-pipeline/)
- `evidence/hybrid-reassessment-repair/`: `production-download.zip`, `extracted/`, `rebuilt/`,
  `zip-verification.json`, `billing-summary.json`, `new-run.json`, `authorization.json`,
  `launch-readback.json`, `live-metadata.json`, `image-schema.json`,
  `offline-gameplay-native.png` (864×528 native canvas), `before-gameplay-native.png`,
  `after-gameplay-native.png`, `final-gameplay-native.png`, `final-status.png`, `final-ui.png`.
- Run data: `data/hybrid/3c92b111114d479485d3aafe4991d441/` (source-3.png, crop-decision-3.json,
  sample-3-0/, candidate-9/ — scene.png, world.json, index.html, diagnostic.zip).
- Verify: `python3 tools/test_hybrid_isolated.py` (355), `python3 tools/verify_production_zip.py`,
  `python3 tools/lookup_repair_billing.py`, `python3 tools/precheck_reassessment.py`.

## Honest boundaries
Model gate passed twice with valid citations; deterministic replay/rebuild/browser
navigation are proven. NOT proven: owner acceptance (user_acceptance remains pending), any
general style guarantee beyond this run, and WaveSpeed image billing (quote only). The
final review is a model verdict, not human QA. No public deployment; production export is
the service download endpoint only.
