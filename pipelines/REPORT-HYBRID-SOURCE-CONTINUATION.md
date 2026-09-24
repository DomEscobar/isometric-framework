# Actual 32,768-token continuation — complete extraction, genuine stairs FAIL

## Outcome

LIVE API successor **8b8ad09078db49c4b90724487bc208a6** consumed the unchanged plan and provider original from sealed **d270dd95c2104370938199f8f91bcb55**, without a planner POST, another image, manual crops or source transformation. Independent systemd worker entered queued→extracting→needs_attention. It did not reach sample/final because the real model explicitly rejected the stairs material. No playable/export ZIP exists; both actual diagnostic/production download endpoints return409. This is **not** completed terrain production.

The output-exhaustion bug is resolved for this real call: actual outgoing request **max_tokens32768, reasoning.effort medium**, metadata maximum65536. Response **finish_reason stop / native STOP**, complete locally parsed JSON. Usage prompt3942, completion15496, reasoning15067. No synthetic JSON closure or citation repair.

Four crop decisions PASS (land/path/square/wall). **stairs FAIL**: “Depicts a 2.5D stepped architectural object with risers and treads rather than a flat orthographic material surface.” Original visibly contains highlighted tread bands and shaded risers, not merely a flat stone texture. The strict gate correctly rejects this. Full decision: `data/hybrid/8b8ad09078db49c4b90724487bc208a6/crop-decision-0.json`.

## Authority and exact accounting

Latest user quotes **„warte nein erhöhe das budget verdopple?“** and **„ja dann viell höhres Antwort-/Tokenlimit man“** supersede previous10USD/low-reasoning instructions. `HYBRID_SOURCE_CONTINUATION_AUTHORIZATION.md` records **USD20 PROJECT TOTAL INCLUDING all historical costs/holds**, not20additional. Only `total_usd` changed in `data/generation-policy.json` to20.00; approved=false, attempts, scope and all other fields remained unchanged. Actual `/api/hybrid/config` readback confirms20.00 and closed public controls.

Frozen child max6 lifetime calls / max1 inherited image / max0 local corrections. Before3calls; now4calls,1image. New scoped allowance2727936microUSD covers extraction+two reviews at909312 each using live full-context +32768completion pricing, not an artificially reduced reservation. Extraction reserve transaction checks headroom for both remaining reviews. Exact child acknowledgment **dc5300a6b44ea2fab7f2f53aea1b85c24a05809fcea56d0926478ee691583bcc** binds both historical unknown calls and full holds.

- New extraction call: **edf2f6c5e7c7b8ab7685bd83b7302065daadd92abc7743532e6c46e7f1f2f25a**
- Provider generation: **gen-1790084858-7FxgMqe4RhBRN8yneJc9**
- Actual receipt AND independent authenticated GET billing: **USD0.0610665** (ceiling61067microUSD).
- New retained hold: **909312microUSD**, actual cost is contained within this, not added to it.
- Central held total before8186320; after **9095632microUSD**. Remaining under20USD **10904368microUSD**.
- **No settlement applied, zero holds released.** All original unknown holds retained. Every historical row compared field-for-field unchanged:10jobs,11reviews,10runs,5calls,58events,3acknowledgments.

An append-only settlement helper and shared effective-budget reads were implemented/tested before the user reprioritized live execution, but no live settlement row was inserted. Launch did not wait for settlement or depend on releasing anything.

## Verification and evidence

- Full isolated regression **318passed /162existing warnings** before live start, `evidence/hybrid-source-continuation/tests-full.txt`. Targeted essential tests42pass; additional lifetime6/image1 closure assertions5pass after launch.
- TDD observed failures for missing source continuation, old8192 outgoing limit, and hardcoded10USD boundary. New tests prove exact inheritance, source/guide/receipt/ledger drift closure, invalid token policy rejected before purchase, inherited count3→6 without reset, no second image/planner, single successor, settlement double-count prevention/concurrency/bad hashes/mismatches.
- Both own services restarted and live readiness verified. A first immediate readiness GET raced startup and returned connection refused; the subsequent live API start succeeded. No public/game/animation service touched.
- Native UI screenshots while extracting and after rejection: `evidence/hybrid-source-continuation/phase-*.png`, `status-*.png`.
- `source-native-browser.png` equals unchanged original1920×1280 RGB pixel-for-pixel; SHA256 original **77c53d47f7b43f1d0a2484f8aaea9549fc52ebfb86d72c90ee40774bf0359cf4**, prediction **55eaaa11559b4a53a56b96c18e825122**.
- `cap-readback.json`, `outgoing-extraction-policy.json`, `live-metadata.json`, `launch-readback.json`, `terminal-run.json`, `verification.json`, and `gen-1790084858-7FxgMqe4RhBRN8yneJc9-billing.json` retain actual evidence. `tools/verify_source_continuation.py` rechecks exact previous rows, source bytes, real billing, failure verdict, actual HTTP denial and native pixel equality.

## Actual remaining boundary

This is now a **material-source rejection, not insufficient tokens or money**. Retrying the same prompt/source cannot turn the failure into a pass. No source-replacement purchase is allowed by current max1image scope. A new targeted model crop extraction would need three additional calls including both mandatory reviews, but onlytwo remain under the finite max6 amendment. Do not silently increase caps, substitute paving for stairs, manually choose tread interiors, or promote the failed extraction. The current source cannot proceed through the implemented strict contract as-is. No unnecessary sample/final review was bought.

## Files

New: `billing_settlement.py`, `hybrid_source_recovery.py`, `tests/test_billing_settlement.py`, `tests/test_hybrid_source_continuation.py`, `tests/test_hybrid_token_policy.py`, `tools/start_source_continuation_once.py` (one-use PAID start, not regression), `tools/source_continuation_readback.mjs`, `tools/verify_source_continuation.py`, authorization/report above.
Modified: `generation.py`, `hybrid_store.py`, `hybrid_models.py`, `hybrid_recovery.py`, `hybrid_worker.py`, `hybrid_api.py`; `data/generation-policy.json` only cap. Historical run/call/receipt/config amounts untouched. Private pre-change snapshot `data/hybrid-source-continuation-before.json`0600.
