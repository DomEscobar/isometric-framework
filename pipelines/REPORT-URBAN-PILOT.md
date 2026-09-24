# Second paid pilot — urban promenade (not the forest pilot)

## Outcome
Genuine generated urban ground completed and exercised through the local service and browser. A new original 16×14-cell promenade has distinct **street / sidewalk / planting** materials, warm paving, gray asphalt and four planted pockets. The user attachment is **STYLE ONLY**, not the street arrangement. No production props were generated or baked in; bench and kiosk spaces are semantic reservations, and the moving marker is a technical test actor.

**Technical PASS. Semantic needs_attention. Secondary visual pass, parent/user approval pending.** The secondary model passed both image gates, but this report deliberately retains semantic attention for green fringes and gray curb pixels outside canonical material masks. No collision was moved to accommodate the picture. The earlier forest pilot and its shoreline caveat remain separate and unchanged.

## Actual delivery files
All paths relative to `/root/services/layout-terrain-pipeline`:
- Clean native game-scale screenshot: `evidence/urban-pilot/browser-final/canvas-native.png` (768×408, CSS/backing 1:1, DPR1).
- Framed clean gameplay: `evidence/urban-pilot/browser-final/play-scale-clean.png`.
- Guide comparison with independent boundaries: `evidence/urban-pilot/guide-vs-registered.png`.
- Exact final PNG: `evidence/urban-pilot/terrain.png`.
- Browser-downloaded ZIP: `evidence/urban-pilot/browser-final/candidate-f3bdc310f809-d1.zip`.
- Real-input demonstration: `evidence/urban-pilot/actual-input-traversal.mp4` (22 actual keyboard-step captures, encoded at 5 fps, 768×408; a discrete controller demonstration, not continuous motion or a production character).
- Retained provider source: `evidence/urban-pilot/original.png` (2000×1040).
- Retained user JPEG: `evidence/urban-pilot/style-original.jpg`; normalized PNG: `style-only.png`; lineage: `style-lineage.json` in the same directory. JPEG SHA256 `cdc8f985f94fc17503ebdc23b99094cf098652c8b39166b0602e2117c63bf3e7`. PNG is a lossless encoding of identical once-decoded RGB, no resize or repaint. The ZIP embeds the uploaded PNG plus lineage in its review; the original JPEG remains beside the deliverable, not inside this ZIP.
- Machine verification: `evidence/urban-pilot/verification-final.json`; complete accounting: `accounting-final.json`.

## Exact bindings
- Layout: `057137d51849cde09c0d12565f3232267e1b1dee239c14e8de64bb6b6c49ffb1`
- Original dimension-mismatch candidate retained: `15d94cb1157357f59b0fe7b7ee7c78a2b6e94baa879bb0ddbba9a09a61947e69`
- Registered candidate: `f3bdc310f809cf7a6b95015cc16af343e337a192e1865432ac530eb2b02fa96a`
- WaveSpeed prediction: `b644104cbba2417b939d1578458730d3`
- Job/quote: `c9ba30c473e3d396a5a73a043b94de15c8b1daa38f1d97b50c46caf98e705f36`
- Source SHA256: `706474479cf17c3db5ec95175b45c183f6bb2bdfdde0bf9f9acde0b901309c2c`
- Final terrain SHA256: `c8619f78c9a2c8356c7791d763400e884e537ee6e8d51616b7e2716b554df211`
- ZIP SHA256: `e2a96da209a9f4b04d7fb1cf53176c0c4c622a56a189685a80f4b0a0303a0923`
- Exact request SHA256: `3f6bf2d8c40dd61c497c29a0b0e7a75fbba2a8cb7f54d099e553e33931f364d1`
- Bound review: `3cb81fa8d19ab97201301b71bed3cb2ebdba3382ef2909af9587784caeded3f7`

Live schema and exact-input price were fetched before the single paid Muse edit submission. Style upload → quote → confirmation → known-prediction polling/import were actual service calls. No paid retry or candidate churn. Provider transient URLs and credentials are not exported. Source dimensions were correctly rejected before explicit registration; original and rejected record are preserved.

## Layout and navigation decisions
- Canonical cells 48×24 pixels, density1; unchanged coordinate authority. Default preset is compact 16×14. `kind=urban` is an explicit preset, not arbitrary natural language. Clear the default pond brief before selecting it. Seed is retained, not advertised as random urban street topology.
- Three-cell road with broad paved sidewalk areas. Protected green pockets blocked; two solid bench/kiosk reservations on paved outer edges. Future visual object extents remain unknown.
- Required pedestrian goal route is entirely on the north sidewalk, from [1,4] to [14,4], never across the road. Actor width 0.8, swept square cardinal movement.
- **Road is explicitly walkable by the technical player**, to test this empty ground map. There are no vehicles, traffic rules, crossings, traffic safety claims or simulation. Real-world pedestrian crossing safety is outside scope.
- Urban path/tree/house overrides are rejected; preset owns its street and reservations. Original meadow/plaza/pond generator behavior and immutable forest revision remain unchanged.

## Registration and material assessment
One scalar source→canonical `0.3856984384333134` with translation `[-1.3127399948800569, 3.629661233893713]`; four independently observed outer corners, source brightness separation against black surround, recorded in `registration-evidence.json`. Frame residual is below 2 canonical pixels per coordinate. No per-axis warp, repaint, mask correction or collision changes. Both export densities are rendered directly from the retained original, not chained.

Urban color proxies are independent from the forest water test: green-first planting, neutral gray street and warm light paving. They are supporting measurements, not automatic material truth:
- Planned planting agreement: 98.03%; 2283 green-proxy pixels outside its plan.
- Planned street agreement: 97.97%; 4414 gray-proxy pixels outside street (includes curb/border evidence, not all asserted to be roadway).
- Planned sidewalk warm-paving agreement: 88.54%; unclassified dark seams/curbs are not automatically obstacles.
- Required route: 6288/6288 pixels warm paving; zero green or gray proxy hits.
- Broader clearance check: 27 otherwise-safe sidewalk actor footprints intersect 490 green-proxy pixels total, max 42 in one footprint. Slight organic foliage protrusions remain a material/layer judgement, not a reason to change collision.
- Source and actual native browser images were inspected. Warm light palette, gray road and fine paving/foliage read distinctly urban; no forbidden tall objects, vehicles or people were seen. Object detail in the reference is intentionally absent from this ground-only pilot.

Gemini `google/gemini-3.8-flash` reviewed canonical guide, exact final resolution image, retained source through its declared aspect-preserving review thumbnail, and style-only reference. Free `/auth/key` HTTP200 assertion ran before ONE paid call with the authorized pool credential. Real response retained in `model-review.json`; semantic/visual secondary PASS explicitly notes fringe overlaps. It is not parent/user approval.

## Verified execution
- TDD: urban behavior test first failed `unsupported kind/path`, then passed. UI material-option regression first failed, then passed.
- `python3 -m pytest tests -q`: **45 passed**, one pre-existing Starlette/httpx deprecation warning.
- `tests/urban-browser.mjs`: PASS. Actual keyboard goal journey, planting collision, both reserved-object collisions, world edge collision, explicit empty-road traversal, three material-mask views, real candidate ZIP download; no page errors.
- Final ZIP: 36 members, 35 verified hashes, CRC passes. Original/style PNG bytes retained, layout binding, request/receipt and review verified by readback. Density1 AND density2 direct-original replay passed.
- Browser pixels: 512 differences, all confined to the separately rendered technical actor. Compare exported RGBA after compositing over browser-read CSS background rgb(16,25,30); 5376 transparent pixels lie outside the map, **zero inside canonical terrain**. No hidden source/density/CSS stretch.
- Original three-layout browser harness rerun on an isolated zero-budget fixture server: PASS; `evidence/urban-pilot/legacy-regression/browser-report.json`. Old paid forest guide bytes unchanged; earlier evidence not overwritten.

## Shared accounting — fresh SQLite and API readback
USD10 project total unchanged. Generation attempt cap minimally raised **1→2**, now exhausted; provider generation is disabled for further attempts. Before run: USD1.599224 conservative holds. After run:
- This urban generation quote/hold USD0.011; actual provider invoice not exposed.
- This secondary review reported usage cost USD0.005445; conservative hold USD0.794112.
- Combined project holds **USD2.404336**, inclusive of known charges (do NOT add actual charges again).
- Remaining headroom under holds **USD7.595664**; this does not authorize another attempt.
- Two generation records and three review liabilities retained, including the earlier HTTP401 attempt. Prior ledger rows unchanged. No automatic release/reconciliation and no secret exports.

## Parent restart / no-spend reproduction
Child servers terminate on worker completion. Restart fresh code; old ports may run stale modules:
```sh
cd /root/services/layout-terrain-pipeline
python3 -m uvicorn app:app --host 127.0.0.1 --port 53047
# separate shell:
curl -fsS http://127.0.0.1:53047/api/generation/status
BASE_URL=http://127.0.0.1:53047 EVIDENCE=evidence/urban-pilot/browser-recheck node tests/urban-browser.mjs
BASE_URL=http://127.0.0.1:53047 BROWSER_EVIDENCE=evidence/urban-pilot/browser-recheck python3 tools/verify_urban_pilot.py
python3 -m pytest tests -q
```
Browser `EVIDENCE` selects its output directory; optional `CANDIDATE_RECORD` changes the bound candidate record file. Verifier `EVIDENCE` selects pilot root, `BROWSER_EVIDENCE` selects browser evidence. Do not rerun `urban_pilot.py confirm` or `review_urban.py` as tests. Registration and generation tools are scoped pilot operator tools, not automatic all-layout registration/classification.

## Changes and scope
Modified `layout_core.py`, `artifacts.py`, `static/index.html`, authorization/policy and report pointers; added `tests/test_urban.py`, `tests/urban-browser.mjs`, five `tools/*urban*.py` workflow/review/verification tools, report and immutable data/evidence. Shared workbench skill updated with material-specific and RGBA replay lessons. No Git metadata exists, no commit claimed. No animation-service, existing game, public deployment, DNS/nginx or service-manager changes.
