# Milestone 2 — provider adapter + real candidate workflow

## Working locally

- Explicit `style_only` PNG reference upload, original bytes and hash-addressed role record; independent immutable layout/guide binding.
- WaveSpeed adapter is wired end-to-end: live catalog/schema and price discovery, upload ticket/PUT, exact-input re-quote, one paid submission, durable prediction receipt, manual resume/poll, bounded output download, source-retaining candidate import. Credentials stay server-side. **Only free catalog/schema/price calls were executed live.** Upload/submission/poll/output behavior was exercised with labelled mocked transport, never claimed as real generated terrain.
- Transactional SQLite total-budget reservations in integer micro-USD; project attempt cap; no paid automatic retry. Repeated confirmation and refreshed quote for the same inputs return the same job. Sources, exact request/hash and prediction receipt persist. Recovery after receipt-before-state crash uses that exact receipt. Unknown submission without receipt blocks new submissions and requires provider reconciliation, never guessed reattachment.
- User PNG → candidate → playable canonical-map preview → original/guide diagnostics → exact downloaded ZIP works without a provider. Canonical graph, collisions, layout and reservations remain unchanged. Wrong dimensions or stale layout block candidate export. Legacy imports without a recorded guide hash remain readable; exporting them requires re-importing their retained original into a new record. Candidate/source/manifest integrity is checked on reads.
- Direct-original deterministic NEAREST density 1/2 export, original bytes, output projection, processing recipe, source/output hashes and candidate review record. No crop, automatic masking, chained resizes or invented details. Canonical layout/guide/masks retain source density; terrain has an explicit separate output projection.
- Actual image measurements: planned-region/route alpha coverage, opaque pixels outside guide, RGB mean/deviation inside each planned material region and exact guide-RGB fraction. These do **not** infer material identity, obstacle height or registration. Every import stays `needs_attention`/`rejected`; image alignment `unverified`, visual review `unreviewed`, production approval false in UI/package.
- UI has real free-quote and separate confirmation stages, auth/budget reasons, saved-job recovery, candidate reload, mobile hash wrapping and corrected draft-template selector. New revisions invalidate candidate/quote UI state.

## Live access and spend

Live `meta/muse-image/edit` remains available. Required fields: `prompt`, `image_urls`; PNG output supported. No invented historical schema was used. Free live quote returned **0.011 USD**, explicitly an estimate. Exact evidence: `evidence/milestone-2-verification/live-schema-price.json`.

**Project budget 0 USD, attempts 0, reservations 0, paid calls 0.** No provider media uploads. Existing environment credential successfully accessed free metadata; no credential value was printed or stored in evidence. No approval-policy file was created. Current server denies confirmation before upload/submission. Historical game/animation budgets were not reused.

The budget is a conservative estimated-reservation guard, not a guarantee against provider billing variance. Failed/unknown attempts retain reservations; automatic release/refund reconciliation is not implemented.

## Executed verification

- `python3 -m pytest tests -q` → **35 passed**, one existing Starlette/httpx deprecation warning. `evidence/tests-milestone-2.txt`.
- `EVIDENCE=evidence/candidate-browser-final node tests/candidate-browser.mjs` → **PASS**, no page errors. Real browser style upload, candidate upload, keyboard movement, original/guide comparison, density selection, downloaded exact candidate ZIP, live free quote, blocked confirmation, stale-candidate invalidation and mobile width check. Technical guide explicitly labelled **TECHNICAL-FIXTURE-NOT-ART**; not production-art substitution.
- `BASE_URL=http://127.0.0.1:48493 EVIDENCE=evidence/regression-browser-final node tests/browser.mjs` → **PASS**, no page errors. Preserved all three layout cases and original navigation/blocker probes.
- `python3 tools/verify_candidates.py` → verified exact browser ZIP CRC/all checksums, original-byte identity, direct-original pixel replay, every cell's unchanged logical projection, three layouts, unchanged original pond-layout ZIP SHA256 and zero-spend readback. `evidence/milestone-2-verification/verification.json` and `evidence/verify-candidates-final.txt`.
- RED failures were observed before candidate binding/export, provider adapter, durable workflow, style API/UI, manifest/prediction/source drift protection, receipt recovery and refreshed-quote deduplication. Additional regression negatives cover missing auth/budget, wrong dimensions, stale revision, insufficient total budget, invalid/increased exact quote, live-schema drift, wrong prediction response and ambiguous submit without implicit retry. Browser RED also exposed mobile hash overflow and a blank comparison stage; both repaired and rerun.

## Exact artifacts for parent review

Root: `/root/services/layout-terrain-pipeline/`

**Browser-downloaded ZIP:**
`evidence/candidate-browser-final/candidate-82c9fdba95f4-d2.zip`

- 45,308 bytes, 25 members, terrain 1536×816.
- SHA256 `57410133482d973b3b884c503c1af0315a79c4681dab621c8aa91582471adc96`.
- This is a technical-fixture candidate export, **not generated production terrain**.

Screenshots:
- `evidence/candidate-browser-final/playable-detail-TECHNICAL-FIXTURE.png`
- `evidence/candidate-browser-final/comparison-detail-TECHNICAL-FIXTURE.png`
- `evidence/candidate-browser-final/candidate-playable-TECHNICAL-FIXTURE.png`
- `evidence/candidate-browser-final/candidate-guide-diagnostics-TECHNICAL-FIXTURE.png`
- `evidence/candidate-browser-final/free-quote-budget-blocked.png`
- `evidence/candidate-browser-final/mobile-controls.png`
- `evidence/candidate-browser-final/mobile-current-revision.png`

Worker gpt-6-astra inspected images natively: entire guide diamond, pond, path and reserved footprint overlays are framed; test actor and route visible. Comparison labels distinguish original from guide and explicitly disclaim automatic registration. Mobile custom-draft label matches edited plaza brief without horizontal overflow. The workflow remains a long scrolling console; mobile play view is a fitted overview. This is **worker inspection**, not main-session Astra/user art approval. Parent should load final detail captures independently. Hashes are in verification.json.

## Remaining true blockers

1. No new project paid budget authorized; live generation/upload/output handling cannot be claimed tested. No actual owner style/terrain reference or accepted production terrain was supplied this run.
2. Provider model does not promise exact requested dimensions/geography. Nonmatching outputs are retained and rejected; automatic registration, aspect-safe calibration, material recognition and visual acceptance remain open. Neither equal metadata nor alpha coverage proves alignment.
3. Unknown submission without a durable receipt needs manual provider reconciliation. No arbitrary reattach or automatic retry path is offered. Provider billing reconciliation is not implemented.
4. No engine-specific adapter, production props/depth artwork, heights/bridges/tilesets, public authentication/deployment or performance acceptance. Existing local-host/origin safeguards do not make this a production multi-user service.

## Source changes / restart

Added `provider.py`, `generation.py`, `generation_api.py`, `terrain.py`, `static/workflows.js`, candidate/provider/image/prediction tests, `tests/candidate-browser.mjs`, `tools/verify_candidates.py`, this report. Updated `app.py`, `static/index.html`, regression browser base-URL override, README/contract and current-report pointer. Core generator/three layout geometries remain unchanged. Recorded reusable procedure in active-profile skill `layout-terrain-workbench`.

A fresh child server was used on separate discovered loopback port **48493**; parent port 8766 was left alone and may still serve stale in-memory modules. **Child server will terminate at delegation end.** Restart for verification:

```sh
cd /root/services/layout-terrain-pipeline
python3 -m uvicorn app:app --host 127.0.0.1 --port 48493
# separate shell:
curl -fsS http://127.0.0.1:48493/api/generation/status
python3 -m pytest tests -q
```

No deployment, service-manager, animation-service, isoani or existing-game changes.
