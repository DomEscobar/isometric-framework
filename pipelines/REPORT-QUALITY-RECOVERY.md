# Urban quality recovery — actual paid correction, not production success

## Outcome

**A real new correction now draws broad, readable cream/beige slabs instead of the old dense irregular pavers. It is still NOT safely aligned or production-approved.** The existing service executed the whole bounded sequence: append-only historical transport reconciliation → new conservative registration of retained source → new exact-density paid review → finding-derived paid image correction → automatic import → unchanged registration gate → terminal safety stop.

The corrected source's worst frozen frame residual is **3.3601157586376864 canonical pixels**, above **2.5px**. Grass tufts and serrated bed edges remain visible. There is no new approved gameplay after-image and no approved production ZIP. The comparison explicitly labels the new source **FAILED-FIT DIAGNOSTIC / NOT GAMEPLAY**. Do not report this as finally good terrain or replace the urban result with Warm.

![Actual same-scale before / corrected source, failed-fit diagnostic](evidence/quality-recovery/before-after-native-diagnostic.png)

- Left: retained old best, 768×408 native frame, 48×24 logical tiles.
- Right: real new provider pixels rendered with the failed measured **single scalar + translation**, only in the diagnostic tool. Not imported as an operator-supplied candidate; not fed back into the run. No axis warp, masks, repaint, collision edits, density change or gate relaxation.
- Broad slab scale improved visibly. The road also shifted warmer because the **real new reviewer** specifically requested it; this was not an invented hard-coded asphalt finding. Parent's visual assessment had considered the existing road relatively calm, so this disagreement is preserved rather than disguised as consensus.
- Material crops remain the original immutable specification. Actual sidewalk crop is plain tan/beige slab faces, not the full-scene decorative/gray cobbles. Street crop contains adjoining curb/paving and remains somewhat ambiguous; no fabricated replacement reference or silent style change was made.

## Exact identities

| Artifact | ID |
|---|---|
| Immutable original parent run | `8e96cc6e6289256aead3f64d8ea86bfc132d7c47dee27898749bf43428cc1577` |
| New recovery run | `3c932cbd0832cc4707bc8281f828eb837930c89b9dd399ca90223df0f3c697da` |
| Retained best, still unapproved | `f3bdc310f809cf7a6b95015cc16af343e337a192e1865432ac530eb2b02fa96a` |
| New conservative registration of original source | `6caa5a1bfa96eddce1ed0c3c337e4791698d156b825d1ee844de70f409353ac9` |
| New exact-density review | `0012a0ba2f020447d6a4969cea7d3150556e9e883545e59f164b2b0b31dc6d6d` |
| New correction job / quote | `d7f1537d46b93ed64dd458611649b72737c7d8ffd4351fc891734de72a8ac44c` |
| Real WaveSpeed prediction | `057128a6f6394a3690199123ac0aaee5` |
| Latest rejected/unregistered source | `d017f8e38008178c65e512172a8e3e8b0ad158a6606cf8750fa45540098e4659` |
| Unchanged layout | `057137d51849cde09c0d12565f3232267e1b1dee239c14e8de64bb6b6c49ffb1` |
| Unchanged intended style | `d02eb595824e1632a68c50e3b201e7b27bada67f93b20bc1df0bbe60813419f5` |

**3/15 lifetime repair attempts conservatively counted:** prior image correction + new free source-registration attempt + new paid image correction. This phase made exactly **one new reviewer call and one new image call**, not fifteen. Prior parent history and best/latest identities are unchanged; the child references the sealed parent record.

The new registration uses scale `0.38420665330556414`, translation `[-0.5724466522585623, 3.654643607759436]`. Its final source pixels were genuinely reviewed: **layout PASS, materials FAIL, pixel style FAIL, walkable clearance FAIL**, with valid applicable citations. The previous invalid materials citation was never edited. Full new response/observations: `evidence/quality-recovery/new-review.json` and `registered-reviewed-navigation/strict-review-native.png`.

## Independent check and stop rationale

The automatic correction preserved the four beds and road arrangement but repeated the earlier full-frame registration failure. An additional **free**, non-production `registration_diagnostic.py` run investigated estimator bias without replacing the gate:

- Robust outer-contour intersection residuals: 2.5118275622354607px at threshold60, 2.4808276305197534px at80, 2.495297333423144px at100. Selecting only a passing threshold would hide the failing one.
- Withheld planting target-to-source contour proxy: p95 **3.616043895287792px**, max4.787410369344828px.
- Refined longest-run street curb proxies: p95 **3.2383996998723723px / 4.2947049784622084px**, maxima3.9250565701549753px / 5.152459473190724px.
- Original long-band street extraction also latched onto unrelated neutral features; its invalid-looking large residuals are retained and are **not** presented as genuine curb displacement. All color contours remain uncertain proxies, not semantic ground truth.

These withheld checks do not support turning the threshold failure into a safe transform. Two actual urban image corrections across the lineage have now preserved edge/projection defects despite improved paving. The service uses Muse's supported `prompt`, `image_urls`, `output_format`; no invented mask/strength control was added. Another identical prompt reroll is not justified merely because budget remains. A genuinely different constrained generation/control approach would need new evidence and integration, not a relaxed gate. Paid controls were closed instead.

## Historical transport reconciliation, not billing settlement

The independent read-only audit is retained untouched under `evidence/quality-recovery/reconciliation/`. Original `paid-pilot-01` returned HTTP401 according to a request-bound contemporaneous terminal traceback and retained failure artifact. Its absence of model receipt was previously incorrectly equated with unknown HTTP acceptance.

`transport_reconciliation.py` now verifies pinned audit manifest, exact original central record/request/metadata/input hashes, retained failure artifact and the actual history message field on **every use**. One append-only event was inserted into the original central SQLite ledger; original `reviews` row, original failure artifacts and full **USD0.794112** hold remain untouched. No model receipt, verdict, zero-charge assertion, release or retry was invented.

Event: `54adeff79b2477060a9671f05e1f90cf5c5c3c508a0571e30b5f666821fdef5c`.

`execution_receipt_state=no_model_receipt`, `billing_state=unverified_full_hold_retained`, `settled_cost_usd=null`, `released_microusd=0`, `retry_authorized=false`. HTTP POST result was verified through GET readback. This resolves only transport uncertainty; provider-specific billing settlement is still missing.

## Costs and controls

| Quantity | USD |
|---|---:|
| Starting central holds, all prior work included | 4.040920 |
| New image exact quote / held reservation | 0.011000 |
| New reviewer conservative reservation | 0.801792 |
| Additional holds this phase | 0.812792 |
| **Final central holds** | **4.853712** |
| Image holds, six all-time jobs | 0.066000 |
| Review holds, six all-time reservations | 4.787712 |
| New reviewer reported usage, already inside holds | 0.018192 |
| All receipts' reported reviewer usage, already inside holds | 0.05860800 |
| Remaining under unchanged USD10 ceiling | 5.146288 |

Quotes are not invoices. Reported usage is **contained in**, not added to, holds. Historical rejected-auth hold remains included. No new final-density review was bought for the unregistrable corrected source.

Free authenticated reviewer preflight was performed before the review. The automatic image phase performs free live schema/auth/price discovery and re-quotes exact uploaded inputs before one POST. Exact request SHA256 `0b5d0867e87d88ffee771f3a1d8e740bca3969db24f788432fbe2e3a5ce82a3d`; durable generation receipt SHA256 `0fa4feaf2dbceeffdec0feed8a9115b93faefd26729bcbd453f1d8952f6c0dc4`. Full exact provider request is retained server-side in central SQLite; signed URLs are not copied into public evidence.

Fresh ECB XML dated2026-09-21: EUR1 = USD1.1490. USD10 corresponds to approximatelyEUR8.70322 at that reference, not a promised card billing rate. Retained conservative budget assumption remains EUR1.25/USD plusEUR2.50 buffer = EUR15 total; **USD10 was not increased**. `ecb-reference.xml` and `budget-preflight.json` retain the evidence/calculation.

Final HTTP readback confirms generation disabled, reviewer disabled, recovery policy disabled; global image cap closed at6/6. Paid generation/review POSTs return403. Terminal resume does not alter state or spend.

## Genuine verification and artifacts

- **215 pytest passed**,155 framework deprecation warnings. `evidence/quality-recovery/tests-final.txt` (full pre-run suite also retained as `tests-full.txt`). New tests cover document-bound authorization, free bootstrap with unknown holds, separate new review identity, exact seed proof, cancellation, worker/resume locking, all paid boundaries, append-only rejection reconciliation, primary-evidence tampering, and numbered material roles. MOCK tests are not billed attempts.
- Actual HTTP/browser start and resume, persisted phase snapshots, reload/mobile status, best/latest controls and no page errors: `browser/` and `verification/`.
- Actual new-registration keyboard navigation to all goals, planting/object/world blocking and technical empty-road traversal: `registered-reviewed-navigation/browser-report.json`.
- Native browser canvas/CSS **768×408**, DPR1; direct-original export replay matches browser RGB outside the separately drawn technical actor: **zero non-actor differing pixels**. No transparency inside canonical terrain. The free registration is technically playable but visually unapproved.
- Latest original bytes downloaded via browser are retained in `verification/latest-original.png`; latest diagnostic export denied422. Best and new-registration production exports denied409.
- New strict review screenshot shows every criterion, observation and evaluation identity without clipped status height.

Exact browser-downloaded ZIPs, CRC, every checksum, original bytes, unchanged layout and direct-original native pixel replay verified:

1. Old best **diagnostic only**: `verification/diagnostic-candidate-f3bdc310f809-d1.zip`,57 members, SHA256 `160071fcc5c05e3e683773759ef4dc02df8af97a92afe0952ca426776c85a876`.
2. New registered original + actual new strict evaluation, **diagnostic only**: `registered-reviewed-navigation/diagnostic-candidate-6caa5a1bfa96-d1.zip`,56 members, SHA256 `2fbf3618321ee86943a9d5fcd6778a8cd52d5c8cc75d014a530df77cb0a717b9`.

The earlier `registered-navigation/` download is retained as an explicitly unbound diagnostic. An initial reviewed-harness attempt selected density after preparing the evaluation, invalidating the UI binding; the corrected harness selects density first and the final verifier asserts exact evaluation identity in the downloaded ZIP. No paid retry occurred.

Best inspection files:
- `evidence/quality-recovery/before-after-native-diagnostic.png`
- `evidence/quality-recovery/latest-native-diagnostic.png`
- `evidence/quality-recovery/registered-reviewed-navigation/canvas-native.png`
- `evidence/quality-recovery/registered-reviewed-navigation/strict-review-native.png`
- `evidence/quality-recovery/independent-registration/diagnosis.json`
- `evidence/quality-recovery/verification.json`

## Implementation / local restart

Modified: `auto_repair.py`, `auto_adapter.py`, `tests/auto-browser.mjs`, `tests/urban-browser.mjs`; project-local policy files opened only for the explicitly authorized work and closed again. Added: `transport_reconciliation.py`, three focused Python test files, `tools/live_quality_recovery.mjs`, `tools/verify_quality_recovery.py`, this report and phase evidence. Authorization file was authored by the parent before execution; its exact hash is bound server-side. Updated reusable workbench skill with the verified lessons.

New endpoints: `POST /api/auto-repair/{parent}/reconcile-transport`, GET same; `POST /api/auto-repair/{parent}/recover-seed`; `POST /api/auto-repair/{child}/recover-seed/resume`. POST body only `{confirm_paid:true}`; browser-supplied arbitrary authorization hashes/status assertions are rejected. Closed policy now prevents new recovery starts. Existing GET/status and terminal non-buying resume remain available.

Fresh local viewer: `http://127.0.0.1:38363/`. Restart if needed:

```sh
cd /root/services/layout-terrain-pipeline
python3 -m uvicorn app:app --host 127.0.0.1 --port 38363 --no-access-log
BASE_URL=http://127.0.0.1:38363 python3 tools/verify_quality_recovery.py
```

**Do not rerun `tools/live_quality_recovery.mjs` as regression:** it is an explicitly authorized start/resume harness, not the verifier. No public deploy, no games/animation/profile modifications. Main-parent/user visual acceptance remains absent; the requested final good terrain outcome is **not achieved**.
