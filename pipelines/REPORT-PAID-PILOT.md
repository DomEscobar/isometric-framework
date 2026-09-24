# Genuine paid terrain pilot — delivered candidate, not production approval

## Outcome

One real `meta/muse-image/edit` job ran through this service's HTTP **quote → confirm → poll → import** implementation. Its original is retained. After repairing explicit aspect-preserving registration, the actual generated terrain runs in the local browser, responds to real keyboard input over unchanged collision, and exports through a real browser download. This is no longer a technical-guide fixture.

**Technical: PASS. Semantic: needs_attention. Visual: real secondary-model PASS, parent/user still pending.** No final approval is asserted. The source is usable for a reviewed pilot, not yet an exact-shoreline production asset.

## Parent inspection — start here

All paths relative to `/root/services/layout-terrain-pipeline/`:

- **Clean native play screenshot:** `evidence/paid-pilot/browser/play-scale-clean.png`
- Exact canvas: `evidence/paid-pilot/browser/canvas-native.png`
- Guide versus registered output/boundaries: `evidence/paid-pilot/guide-vs-registered.png`
- Actual browser reservations/routes: `evidence/paid-pilot/browser/playable-diagnostics.png`
- Actual original/guide UI: `evidence/paid-pilot/browser/original-vs-guide.png`
- **Keyboard traversal:** `evidence/paid-pilot/browser/keyboard-traversal.mp4` — 768×408, 22 actual browser frames, 5 fps, 4.4 seconds. Discrete cardinal controller, not an animated production actor; no interpolated travel.
- **Actual downloaded ZIP:** `evidence/paid-pilot/browser/candidate-4ff0fb988114-d1.zip`
  - 4,285,528 bytes, 30 members; all 29 checksums and CRC checked.
  - SHA256 `ae3aa383b4868d1e345770c8326594ef5aec2cfdb9297fbe727406045679fc62`
- Extracted exact export PNG: `evidence/paid-pilot/terrain.png` (768×408)
  - SHA256 `b485c683fc7eeb173a6a9f50aaa41871c76afbf9404a2350dafaac85669db3df`
- `evidence/paid-pilot/manifest.json`, `terrain-provenance.json`, `verification-final.json`, `accounting-final.json`, `model-review.json`, `registered-local-checks.json`.

ZIP contains original PNG bytes, style-only PNG, canonical layout/guide/masks/collision, registered terrain, candidate manifest, processing transform, live quote/schema, exact request hash and request fields without transient remote URLs, durable prediction receipt and separately bound grounded review. Full exact provider request remains server-side in `data/generation.sqlite3`; reviewer request/receipt/metadata/actual image thumbnails are in `data/reviews/paid-pilot-02-verified-auth/`. No secret is exported.

## Immutable identities

- New layout: 16×14, seed `20260921`, logical tiles 48×24, density 1, square actor width 0.8. Pond northeast, west-east path, one house and three tree reservations.
- Layout revision: `e718e19530c6f09c40ab7eafecb4d95db057252426ec251e4f4a751eb6c0e144`
- Guide SHA256: `ed81dec2f5094ec40c0cb5415d0cc9403b316001408c756c0ae0060de27aec3d`
- Accepted style source, selected by Waldlicht's read-only `art/art-direction.json`: `/root/games/waldlicht/art/terrain-pilot/source-01.png`, SHA256 `3acd9a8f629bc77a4fc97d25331ea87a31a58ac00cc6ae5281b86e14157d05c7`. Uploaded strictly **style_only**; no old geometry imported.
- Service quote/job: `04293e4725b64001c21517dbe592a0fbd7df8dd74b6d4d9be9b67c5a42fdce8c`
- WaveSpeed prediction: `9e033c5172104cc08e2a302b7a1e5883`, completed, provider inference timing 19,054 ms.
- Exact provider request SHA256: `86d20cebd5d78e9020180cf43767e1d8c8c37d7a7e3068a8b0b74c489dd2601d`
- Original output: 2000×1040, SHA256 `e05893632e68b892f9bc00a0628e2dc93390353187225769f864e827dbc9c680`
- Original dimension-rejected candidate, preserved unchanged: `380bf2a20ebd58e6e9381fbc47fcfd12541463c8002b1b014253733ade67698d`
- Registered candidate: `4ff0fb98811433f2d9e8317d7046caf732701bceb02671cae5dcfc6c37b66f66`
- Final bound review: `c0747827f7c8c9c1c55d75adb3979415be3458d77b480cf56b0de771cd636bcd`

## Real defects repaired

1. **Provider dimensions:** source 2000×1040 versus canonical 768×408. A blind fit-to-frame would apply different X/Y scales and incorrectly register the painted diamond. Added operator-declared scalar+translation registration, immutable derived candidate, original-byte preservation and direct-original NEAREST inverse-affine processing per density. No mask, palette replacement, procedural repaint, collision change or anisotropic warp.
   - Forward source → canonical scale `0.42372881355932207`; translation `[-33.898305084745765,-22.45762711864407]`.
   - Equivalent original source coordinates ≈ canonical ×2.36 +(80,53); inspected landmark notes retained. This is a bounded operator calibration, not an automatic proof of exact alignment.
2. **Missing common review budget:** review reservations now join the generation SQLite transaction/ceiling. Tests reject generation that would exceed the shared ceiling after reviewer liabilities.
3. **Missing review/export evidence:** bounded actual secondary-image review with live metadata, exact request/image hashes, max output cap, original response/usage, no retry; unknown/truncated/wrong-model results never earn a pass. Candidate export includes verified request/quote/style/receipt and independently bound review.
4. **Misleading/obstructive UI:** live budget replaces stale zero-budget badge; separate technical/semantic/visual status; explicit diagnostics toggle gives a clean playable view without changing reservations or collision.
5. **Half-pixel CSS placement:** browser verification caught a 409-row screenshot of a 408-high canvas due to odd-height vertical centering. Repaired integer Y framing. Final canvas/CSS both 768×408, DPR1, position [512,296]. Every browser pixel equals the exported terrain except **512 pixels confined to the technical actor**. Earlier screenshots/review/ZIP are archived, not passed off as final: `pre-pixel-alignment-browser/` and candidate `reviews/`.

Each production behavior change had observed RED before GREEN. The Python suite now has **42 passing tests**, one pre-existing Starlette/httpx deprecation warning. Actual paid browser journey passes with zero JS page errors. It walks both required goals and individually blocks water, house and all three tree reservations. Original three-layout and technical-candidate browser harnesses both pass on a **separate disposable zero-budget server**, not by disabling the authorized project policy. Final fixture evidence is clearly segregated under `regression-fixtures-final/` and `candidate-fixtures-final/`.

## Grounded review and remaining limits

Live model metadata verified `google/gemini-3.8-flash`, image input and 1,048,576-token context. Input bounded to four images and maximum 1280×1280 aspect-preserving thumbnails; output capped at 2048 tokens. Actual final 768×408 terrain was reviewed at its full resolution, alongside canonical guide, route/water-boundary diagnostic and style-only source. Browser screenshots were inspected by this gpt-6-astra worker, not sent to the external reviewer.

Real review response `gen-1790015839-u3qZP2HL96YpIQEhyaXt`, actual model `google/gemini-3.8-flash`, finish `stop`: semantic/visual PASS, continuous path, framed diamond and no tall blockers. **This does not override local uncertainty:**

- Blue/cyan largest-component proxy has 6,075 pixels; 337 lie outside planned water. None crosses required-route masks; no planned dry cell centers are blue.
- A stricter subsequent footprint check found **26 proxy pixels inside five reachable stationary actor squares** ([9,2], [10,1], [11,0], [12,0], [13,0]). This stricter measurement postdates the secondary review. It is a color proxy, not material certainty, but blocks an honest exact-shoreline semantic PASS.
- Worker inspection: complete framed moss/ochre/petrol terrain, readable main path, low clustered ground decoration. Shoreline judgement remains with parent; collision was not moved to excuse the image. No paid image churn to hide this narrow issue.
- House/tree markers and actor are technical placeholders. No production props, animated actor, engine adapter or deployment is claimed. Clean mode hides reservation overlays, not their collision.
- Parent Astra must inspect clean play-scale screenshot and diagnostics; no parent/user approval has occurred.

## Accounting — one USD 10 ceiling, not a target

Baseline was zero jobs, zero queue and no policy file. `PAID_AUTHORIZATION.md` explicitly authorized the new project total. `data/generation-policy.json` is approved, total USD **10.00**, **max_attempts=1**. One generator call completed, zero remote generator jobs outstanding; additional generation is currently disabled by this pilot attempt cap. No automatic paid retries.

Fresh status and DB readback (`accounting-final.json`):

- Exact-input WaveSpeed quote/reservation **USD 0.011**. The prediction endpoint reports completion/timing, **not a reconciled billed charge**; do not describe this estimate as a settled invoice.
- Successful reviewer measured usage: 4,916 input +197 completion tokens, **USD 0.00442575**.
- Known reviewer charge + generator quote = **USD 0.01542575** (mixed actual/estimate, explicitly labelled).
- **Conservative total held: USD 1.599224, inclusive of known charges**, NOT an additional amount to add to them. Generation 0.011 + two reviewer reservations of 0.794112 each. Reviewer reserve uses full model context at live input price plus capped output, much larger than actual usage; reservations are not auto-released.
- First reviewer environment credential returned **HTTP401**, no model result. Liability remains held. A separate authorized active-pool credential was checked with free `/auth/key` HTTP200 before the second explicitly bounded attempt. No secret was printed/copied into artifacts, no blind retry.
- Remaining headroom under conservative holds **USD 8.400776**. Neither provider invoice reconciliation nor release of unused review holds is implemented.

## Local restart and reproduction

Child servers can terminate when delegation ends. Parent must restart current code, not trust old 8766/48493 processes:

```sh
cd /root/services/layout-terrain-pipeline
python3 -m uvicorn app:app --host 127.0.0.1 --port 33009
# Separate shell, read-only/replay checks (NO additional paid call):
curl -fsS http://127.0.0.1:33009/api/generation/status
node tests/paid-browser.mjs
python3 tools/verify_paid_pilot.py
python3 -m pytest tests -q
# Separate fixture server; never changes live policy:
python3 tools/isolated_test_server.py 33011
# Separate shell:
BASE_URL=http://127.0.0.1:33011 EVIDENCE=evidence/fixture-next node tests/browser.mjs
BASE_URL=http://127.0.0.1:33011 EVIDENCE=evidence/candidate-fixture-next node tests/candidate-browser.mjs
```

UI `http://127.0.0.1:33009/`, OpenAPI `/docs`. Generate seed `20260921` with defaults, paste registered candidate ID into saved-candidate control, load, select 1:1 and uncheck diagnostics for clean play. Relevant endpoints: `/api/generation/status`, `/api/generation/jobs/{job-id}`, `/api/terrain/{candidate-id}/review`, `/preview.png`, `/download?revision={revision}&density=1`. New local calibration endpoint: `POST /api/terrain/{original-candidate-id}/register` accepting scalar `scale`, two-value `translation`, explanatory `notes` only.

Do **not** rerun paid prepare/confirm/review scripts as smoke tests. Immutable paid intents prevent duplicate calls; reconcile original records if a stage is uncertain.

## Files changed

Updated `app.py`, `generation.py`, `terrain.py`, `static/index.html`, `static/workflows.js`, README/contract/report pointer. Added `review.py`, registration/shared-budget/review/export-evidence regression tests, `tests/paid-browser.mjs`, isolated fixture-server and pilot prepare/register/review/diagnostic/verification tools, policy, immutable data and evidence. Updated active default `layout-terrain-workbench` skill with reusable measured lessons. Repository directory has no Git metadata; no commit is claimed.

No animation-service/game files, service-manager, nginx/DNS, public deployment or historical budgets were modified.
