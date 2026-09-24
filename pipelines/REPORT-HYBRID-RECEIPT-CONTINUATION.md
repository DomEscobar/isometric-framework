# Receipt continuation: real image, truncated extraction; NOT completed production

## Actual service execution

`POST /api/hybrid-runs/a8d71015aaa64977af1bf73fc3240004/continue` created LIVE child **d270dd95c2104370938199f8f91bcb55**. Independent systemd worker executed queued → planning (receipt consumption only) → layout_preview → generating → polling → extracting → needs_attention. No new planner POST, no operator plan/crop handoff. Exact original planner JSON retained unchanged in both directories; parent rows remain unchanged. Runtime pinned to new compiler/recovery/worker hashes. Max lifetime1image/5calls/0local inherited, counters now1image/3calls.

Automatic compiler normalization retains input six transitions and hashes, canonical three undirected edges and hash; all original height/footprint/connectivity gates remain. Revision exactly `d6664a4ba7579eb40e86a07f08606d98225c05c24d1d64dd3a3570d4f9f3730a`. Current transition schema has no semantic attributes: dictionaries/extra fields are rejected, never silently stripped. Separate material alias `cliff_wall`→`wall` preserves exact supplied description, rejects ambiguity/extra materials, and records original/canonical hashes. Raw model Plan remains untouched.

## Exact calls and costs

| Role | Call ID | Provider ID | Hold microUSD | Reported actual USD |
|---|---|---|---:|---:|
| inherited planner | 2e5a86a4c2534f4dd035facd5adfb3715c3fa5e4ab96af3e3b10077f41e94955 | gen-1790081788-rtA2eCqsJFNoXBzFMPqd |817152|0.022728|
| new image | d341a4d307ced8b9e14fbb3d1f0b4d1940bc421bbd8d18bd7130eaa341f01608 |55eaaa11559b4a53a56b96c18e825122|11000|not separately reported; USD0.011 exact quote|
| new extraction |34edc0bf3e53c472eccd70e1bf912744fdd2d58bc5cfc1beb06970aeb67f87b9|gen-1790083043-1CWqF1BmU0rWdmKXjH3n|817152|0.03364875|

Extraction model identity is correct. `finish_reason=length`, `native_finish_reason=MAX_TOKENS`; completion8185, reasoning7863, only977 characters of **truncated invalid JSON**, ending at square.xywh. No usable complete CropMap; no fabricated closure/crops. No sample/final review, latest=null/best=null. Diagnostic and production ZIP both HTTP409, verified through actual endpoint; no offline playable ZIP exists for this run.

Provider original: `data/hybrid/d270dd95c2104370938199f8f91bcb55/source-0.png`,1920×1280 PNG, SHA256 `77c53d47f7b43f1d0a2484f8aaea9549fc52ebfb86d72c90ee40774bf0359cf4`. Visible board has grass, sandy path, paving, explicitly drawn stair treads, masonry wall. Inspection is not crop acceptance or production approval. Exact native browser screenshot equals source RGB pixel-for-pixel.

## Financial/call boundary and next actionable work

Actual central held8186320microUSD, remaining1813680. All prior rows verified field-for-field unchanged:10jobs,9reviews,9runs,3calls,46events. Both unknown historical planner holds remain fully reserved. New scoped immutable acknowledgment `f5e54fc61a227f8c03d69751dd4c0dc2fbda601130d58a3b954905c9e6bcef8f`. Child authorization file removed after terminal readback; terminal Resume remains sealed.

**Do not treat current full-context holds as proven final billing.** FREE authenticated `/generation?id=...` lookup now confirms BOTH known actual costs above. Evidence stored as `<generation-id>-billing.json`; provider reports actual backend model `google/gemini-3.8-flash-20260902` versus routed request/receipt model `google/gemini-3.8-flash`. Verified settlement with ceiling rounding would release1577927microUSD, yielding3391607 available WITHOUT touching unknown holds. Settlement is **not implemented/applied**; current ledger remains conservative8186320.

Free live metadata `model-current.json` explicitly supports `reasoning`, `reasoning_effort`, supported_efforts high/medium/low, mandatory=true; max_completion_tokens65536. Documented next transport should use `reasoning:{effort:"low"}` rather than disabling mandatory reasoning, with tested sufficient JSON output allowance and exact updated conservative reserve. It has **not** been changed/purchased in this run.

Next recovery must implement receipt/source-bound immutable continuation from this sealed child, inheriting planner/normalization/material intent and image receipt/source, with no second image and no manual crops. It must not reuse the truncated extraction as a complete result. New extraction + sample + final needs THREE more calls; existing bound max5 has onlyTWO remaining. Settlement alone fixes potential money headroom but does not authorize silently resetting/increasing this cap. Resolve any continuation scope explicitly/append-only under the owner's standing instruction before purchase. This is a precise outstanding authorization/implementation boundary, NOT successful end-to-end delivery.

## Verification

TDD RED observed for duplicate transitions, missing continuation, worker trying paid planner, missing endpoint, known-image metadata-before-receipt bug, missing material alias. Final isolated suite **299passed/162 existing warnings**, `evidence/hybrid-receipt-continuation/tests-full.txt`. Concurrency test proves one successor per parent and inherited calls cap; stale worker/new planner/changed hashes/ledger/input/parent/unknown holds remain fail-closed.

Independent `/tmp/hybrid_review_recovery_repro.py` now prints `phase: polling receipt_known: True prediction_id_saved: True` during metadata outage. Its final assertion intentionally expects OLD failure and now fails; repository regression asserts corrected polling behavior and passes. Recovery checks stored exact image request/call identity/ledger receipt before discover/quote.

Actual UI phase screenshots: `phase-extracting.png`, `phase-needs_attention.png`, native `status-*.png`; `source-native-browser.png` is real1920×1280 source-only view, not gameplay. Browser tool Chrome failed startup; installed Playwright headless shell worked. No public/game/animation deployment touched.

## Changed files

Production: `hybrid_layout.py`, `hybrid_recovery.py` (new), `hybrid_store.py`, `hybrid_worker.py`, `hybrid_api.py`. Tests: `tests/test_hybrid_normalization.py`, `tests/test_hybrid_continuation.py`. Tools: `tools/start_receipt_continuation_once.py` (one-use paid start, NOT regression), `tools/receipt_continuation_readback.mjs`, `tools/verify_receipt_continuation.py`, `tools/lookup_continuation_billing.py` (GET-only). Evidence directory `evidence/hybrid-receipt-continuation/`; private pre-run snapshot `data/hybrid-continuation-before.json`0600.
