# Current status

**Newest LIVE continuation: [REPORT-HYBRID-RECEIPT-CONTINUATION.md](REPORT-HYBRID-RECEIPT-CONTINUATION.md).** Receipt-bound child `d270dd95c2104370938199f8f91bcb55` automatically reused genuine planner, compiled normalized geometry, purchased one real image, then stopped on MAX_TOKENS truncated extraction. No complete crops/reviews/production ZIP.299 isolated tests pass. Free billing lookups confirm known costs; settlement and next image-preserving bounded continuation remain pending. Central heldUSD8.186320, all unknown holds and old rows unchanged.

**Newest LIVE execution: [REPORT-HYBRID-SCOPED-ATTEMPT.md](REPORT-HYBRID-SCOPED-ATTEMPT.md).** Scoped immutable liability acknowledgment implemented and one independent systemd LIVE run `72e30617e8294e1f8529ffccaee00286` actually executed. Upstream HTTP400 INVALID_ARGUMENT on planner; exact private response retained, sanitized evidence available. No image/ZIP/visual approval. All old rows unchanged; central heldUSD6.541016, actual new billed cost unknown.283 isolated tests pass. UI reload/native/mobile status verified. Historical statements below are superseded, not fresh authorization.

**Latest implementation: [REPORT-AUTONOMOUS-HYBRID.md](REPORT-AUTONOMOUS-HYBRID.md).** Independent loopback UI/API and systemd worker at `http://127.0.0.1:48765/`, real OpenRouter/WaveSpeed adapters, persisted bounded workflow,252 passing isolated tests and genuine retained-pixel replay/browser/offline-ZIP proof. **No fresh paid autonomous acceptance:** OpenRouter environment auth returns401; no new run authorization. Historical ledger unchanged atUSD4.906712; zero new hybrid paid calls. Separate small sample scene/local sampling correction and other listed acceptance gaps remain open. This is a bounded running prototype, not a claim that the entire plan has passed live acceptance.


**Latest: [REPORT-CONSTRAINED-RECOVERY.md](REPORT-CONSTRAINED-RECOVERY.md).** One real provider-side masked correction failed its exact-canvas contract: requested768×408, returned768×512 JPEG with road/beds replaced. Original retained unchanged; no import/final review/production ZIP. Lifetime4/15; shared holdsUSD4.873712; all paid controls closed.224 tests and real browser/HTTP/original-byte verification. This adapter now blocks before purchase because its live schema lacks an explicit PNG contract. Native before/after is diagnostic, not gameplay.

**Latest: [REPORT-QUALITY-RECOVERY.md](REPORT-QUALITY-RECOVERY.md).** Actual new urban registration + paid strict review + source-based paid correction executed. Broad slab scale improved; new source still fails frozen2.5px registration gate (worst3.3601px), no production approval. Historical401 transport reconciled append-only with full hold retained. Shared holdsUSD4.853712; all paid controls closed.215 tests and genuine browser/download/pixel verification; native comparison labels failed-fit after as NOT GAMEPLAY. Prior milestones below remain historical.

**Latest: [REPORT-STRICT-STYLE.md](REPORT-STRICT-STYLE.md).** Versioned external style API/UI and strict production gate implemented. 75 tests, actual browser diagnostic download and production denial verified. ONE new real review: layout PASS, materials FAIL, pixel style PASS, clearance FAIL. Original urban layout/candidate unchanged; no new terrain bought. Shared holds USD3.206128, remaining USD6.793872, generation cap still 2/2. Final parent/user acceptance pending. API examples: [STYLE_API.md](STYLE_API.md).

**Latest: [REPORT-URBAN-PILOT.md](REPORT-URBAN-PILOT.md).** Second genuine urban style pilot complete, technical browser/export/pixel checks pass; semantic fringe attention remains. Shared holds USD2.404336, parent/user approval pending. Forest report below remains its own historical pilot.

**First forest pilot: [REPORT-PAID-PILOT.md](REPORT-PAID-PILOT.md).** One genuine paid generation completed, native playable browser and downloaded ZIP verified, real secondary image review completed. Technical PASS; semantic needs_attention; parent/user approval pending. One shared USD10 ceiling includes reviewer liabilities. Milestone 2 below is historical zero-spend evidence, not current policy.

---

# Historical milestone 1 report — local layout/terrain service

## Outcome
Working local HTTP UI/API in `/root/services/layout-terrain-pipeline`, running at **http://127.0.0.1:8766/** (not publicly deployed). Server command: `python3 -m uvicorn app:app --host 127.0.0.1 --port 8766`; launched process PID 515712, tool session `proc_37b3764202b2`.

- New deterministic, bounded flat semantic generator; exact documented German clause parser plus explicit form/API parameters. Unknown text and conflicts rejected with 422, not ignored.
- Material partition, actor-width-aware swept-AABB cardinal navigation, immutable content-addressed layout revisions, object reservations and house approach; coordinate/density/origin manifest shared with renderer and raster exports.
- Technical blockout, clean guide/masks, reproducible ZIP; local PNG import retains original bytes and separate layout-bound record, never grants visual approval.

## Executed verification

- `python3 -m pytest tests -q` → **15 passed, 1 warning, 1.55s**. Full output: `evidence/tests-final.txt`.
- `EVIDENCE=evidence/browser-03 node tests/browser.mjs` → **PASS**, no page errors. Real headless browser form submission, key-driven journeys to all required pond-layout goals, blocked steps into water/all four reservations/map edge, clean guide/water view, unsupported brief error, three different layouts, local test PNG upload and readback, mobile touch input, no horizontal overflow, actual browser ZIP download.
- `python3 tools/verify_exports.py` → three materially distinct persisted/read-back layouts and downloads; ZIP CRC + every checksum, exact material/region-mask partition, every world cell covered once, no route-mask overlap with water/reservations, reproducible ZIP bytes, independently re-opened browser download. Report: `evidence/exports-final/verification.json`; command output: `evidence/exports-final.txt`.
- Negative suite includes disconnected full barrier, single-cell narrow corridor rejecting actor width 1.2 while accepting 0.8, overlapping reservations, unsupported schema/materials/endpoints/width, projection mismatch, unsupported German requests, bad house support/approach, import transform and decoded-size mismatch. Density/projection roundtrips tested.
- RED→GREEN exercised before generator, clearance validator, constrained composition, exports, API/import and UI implementation. Mobile overflow assertion failed on original screenshot width 492 at viewport 390; wrapping fix then passed at width 390. Schema and house-approach tests also failed before their implementations.

## Parent-review evidence (all paths relative to service root)

Use **browser-03**; browser-01, browser-02 and mobile-red are superseded development captures, preserved rather than relabelled.

- `evidence/browser-03/pond-blockout.png`
- `evidence/browser-03/meadow-blockout.png`
- `evidence/browser-03/plaza-blockout.png`
- `evidence/browser-03/clean-guide.png`
- `evidence/browser-03/water-mask.png`
- `evidence/browser-03/mobile.png`
- `evidence/browser-03/unsupported-brief.png`
- `evidence/browser-03/local-import-needs-attention.png`
- `evidence/browser-03/browser-report.json` — exact route/blocked/touch measurements and import record
- **Browser-downloaded ZIP:** `evidence/browser-03/layout-14ea7264a50a.zip` (33,303 bytes, 21 members; SHA256 `57ab6a6ddbf9d3ce47fb9cb84b57656decc1d0886f527ead244311dc561a29c0`)
- Three API examples: `evidence/exports-final/{meadow,pond,plaza}.zip`, request JSONs and clean guide PNGs.
- Screenshot/file hashes: `evidence/exports-final/verification.json`.

Current pond layout revision: `14ea7264a50ab36b6dd0eaca0789e563e3bf3d8cda191475ce9714edce4c7421`.

Worker image inspection by gpt-6-astra subagent (not main-session approval): desktop map and guide are framed and legible; clean guide contains no grid/actor/labels/reservation overlays; mobile overflow repaired. Mobile is a fitted overview and requires scrolling through parameter controls, not a game play-camera. Main-session/user visual review remains pending. No fake visual PASS. UI composition audit: operational console, no marketing hero/feature-tile grid, restrained palette, technical labels rather than artwork claims.

## Files / scope

Source: `layout_core.py`, `artifacts.py`, `app.py`, `static/index.html`; tests: `tests/test_core.py`, `test_validation.py`, `test_artifacts.py`, `test_api.py`, `browser.mjs`; export probe: `tools/verify_exports.py`; docs: `README.md`, `PROJECT_CONTRACT.md`, `requirements.txt`, this report and `PARENT_LESSONS.md`; saved local state under `data/revisions/` and `data/terrain/`.

No animation-service or existing-game changes; no artwork reused; no provider calls, paid generation, credential reads, deployment or external writes.

## Honest boundaries / issues

**Terrain provider integration is missing/disabled. Production terrain/props are not generated.** The parser supports only exact documented clauses. Seed varies placement, not an arbitrary generative composition model. Reservations are not artwork extents. Navigation is center-to-center cardinal square-AABB navigation, not continuous analog/diagonal game movement. Some parameter combinations are rejected as infeasible.

Import registration is a **declared-frame/dimension boundary**, not automatic landmark registration: actual image alignment remains `unverified`; local material compliance and visual quality remain `not_assessed`. The test upload was explicitly the technical guide, not fake provider output. No engine-specific adapter, authentication/quotas, public hosting, height/bridges or autotiling. Performance not assessed.

System browser failed before opening a tab. A discovered installed Playwright core and cached headless shell successfully ran the actual workflow. Optional pip installation required approval and was not pursued or bypassed. The existing Starlette/httpx test client emits one deprecation warning; documented, not hidden. No new package installation was needed for the delivered result.
