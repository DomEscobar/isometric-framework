# Autonomous material-source repair — live cap stop, NOT successful terrain

## Outcome

Actual service-owned run **a3d4ce60a6db4bc7a2702217d62ce2db** inherited sealed **8b8ad09078db49c4b90724487bc208a6** with4calls/1image and unchanged planner/layout/material intent/source. The local API started the real systemd worker. It automatically generated, polled, extracted, generated one further correction, polled and extracted again. Final **needs_attention, images3/3, calls8/12**, reason `Bildlimit erreicht; Materialdefekt bleibt erhalten`. **No sample, scene64px, final review, diagnostic or production ZIP exists.** Actual download endpoints both409. Do not present this as completed autonomous repair.

### What went wrong (implementation responsibility)

1. First new Muse edit **ccb56c83db3745d2b5f4b7dd038fc764** genuinely replaced the architectural staircase with a flat stone material and visibly preserved the other four materials. Original source SHA77c53d47f7b43f1d0a2484f8aaea9549fc52ebfb86d72c90ee40774bf0359cf4 remained unchanged.
2. The extractor rejected the corrected stairs because it had **no treads/risers**. Its request still included the frozen planner's final-scene phrase “Broad cut stone stair treads with visible risers” without explicitly overriding architecture for material extraction. The generation prompt distinguished these, but the extraction prompt did not. Thus this was a **source-contract contradiction**, not evidence that another image was necessary. The initial classifier accepted any concrete cited FAIL and automatically bought the next image; this was an unnecessary second edit caused by that implementation gap.
3. Second new Muse edit **17306f4401294fdb99fd2b3044b4bba1** preserved the flat lower-left slab but replaced the prior lower-right wall with a staircase. The extractor now assigned that staircase to stairsPASS and flat slab to wallFAIL (no masonry). No PASS was promoted; the whole material gate blocked and the image cap stopped further buying.
4. Free RED→GREEN regression fixes now explicitly separate FINAL SCENE architecture from SOURCE material in the extraction prompt, require absence of treads/risers, and conservatively veto cited failures demanding missing architecture as `contract conflict`, never invented PASS/crop or image authorization. These fixes were implemented **after** the sealed live outcome; they have330test PASS but no new paid validation. They do not rewrite requests, verdicts or earlier purchases. Both local services restarted with fixes; no public policy opened. No fourth image or repeated unchanged-board extraction was attempted.

## Scope and audit

`HYBRID_MATERIAL_REPAIR_AUTHORIZATION.md` records the explicit amendment reason `pipeline livefix`: max_calls6→12, max_images1→3, max_local_corrections0→2; inherited counts4/1/0 not reset. USD20 PROJECT TOTAL remains inclusive of all old holds. Scoped new allowance8000000microUSD fits remaining headroom and is not another project budget. Lifetime normal default3 unchanged.

Append-only content-hash-bound server acknowledgment **2603338442a8d9d1121ff9d5a963afe9ba2c0504fa6d554e56f63dbe9df6147f** includes exact old/new limits, config hash, approval text, both unknown call IDs/request hashes/full amounts and expiry. It is a hash-bound audit record, not a billing settlement or cryptographic signature. Public approved=false remains unchanged. All prior database rows verified field-for-field unchanged. Zero holds released.

Actual exact image requests include ordered role hashes **reference / guide / correction_target**, all three actual image uploads, provider schema, prompt, exact quote and request receipt. jsonschema checked actual body against live Muse schema. Worker reserves extraction plus both32768/medium reviews as downstream headroom before image POST. Extraction reserves both reviews. Full calls use central ledger only; no direct paid tool purchases.

## Exact accounting

- Held before9095632microUSD; new1840624microUSD; **held total10936256 = USD10.936256**.
- Remaining under20: **USD9.063744**. All historical unknown holds remain. Remaining money does not override exhausted3image cap.
- New image quoted costs USD0.011 each, **USD0.022 quoted total**; actual image billing not independently returned.
- Extraction1 **gen-1790086362-WempTfgokQLFpkk1dM31**: actual receipt and authenticated billing GET **USD0.014595**; prompt3940, completion3104, reasoning2693, STOP.
- Extraction2 **gen-1790086443-2uW8ler6oeqzUSVuL9ny**: actual **USD0.030258**; prompt3944, completion7280, reasoning6866, STOP.
- Both requests max_tokens32768 / reasoning medium; reserve909312microUSD each. Actual extraction billing sum **USD0.044853**, contained within holds, not added again. Routed google/gemini-3.8-flash, billing backend google/gemini-3.8-flash-20260902. Router recorded upstream504 then AIStudio200 internally; application made one request per immutable central call, no application retry.
- Exact call IDs, request/receipt hashes, source hashes, full billing and unchanged-row proof: `evidence/hybrid-material-repair/verification.json`.

## Verification and artifacts (absolute prefix /root/services/layout-terrain-pipeline/)

- `HYBRID_TEST_LOG=.../evidence/hybrid-material-repair/tests-final.txt python3 tools/test_hybrid_isolated.py` → **330passed**,162existing warnings. Pre-live328passed. RED tests observed for continuation, conflict classifier and UI/API source readback. An earlier regression expected purchase before an insufficient call cap; updated it to assert the new safer pre-image stop.
- `python3 tools/verify_material_repair.py` verified all historical rows, unchanged original, policy, actual billed IDs, outgoing token settings and both HTTP409 exports.
- `node tools/material_repair_readback.mjs` captured real auto phase progress, not mocks.
- `node tools/material_repair_native.mjs` captured actual API-served sources at native1920×1280 and terminal UI reload. All three native browser screenshots equal their original RGB pixel-for-pixel.
- Parent visual inspection: `evidence/hybrid-material-repair/source-1-native-browser.png` (flat stone corrected source, NOT approved), `source-2-native-browser.png` (wall regression), `source-0-native-browser.png` (original); `three-source-native-comparison.png` (all actual-size sources, wide); `final-correction.png` shows3/3images8/12calls; `final-ui.png`; `phase-*.png`.
- Actual crop decisions: `data/hybrid/a3d4ce60a6db4bc7a2702217d62ce2db/crop-decision-{1,2}.json`. All retained source/request/correction histories remain there, no fabricated crop fallback.
- Private historical snapshot `data/hybrid-material-repair-before.json`0600.

## Files changed

New `hybrid_material_repair.py`, `tests/test_hybrid_material_repair.py`, `tools/start_material_repair_once.py` (one-use PAID launcher; never a regression), `tools/material_repair_readback.mjs`, `tools/material_repair_native.mjs`, `tools/verify_material_repair.py`, authorization/report above. Modified `hybrid_worker.py`, `hybrid_recovery.py`, `hybrid_models.py`, `hybrid_api.py`, `static/hybrid.html`, `tests/test_hybrid_full_mock.py`. Workbench skill updated with the actual contradictory-extraction lesson. Existing live parent/history/config/source files were not rewritten.

## Remaining boundary

Automatic orchestration is real, but visual production goal remains unmet. A corrected first edit exists, and its failure was the old extraction contract; it has not been re-extracted or manually accepted. Current last edit lacks wall masonry. The bounded image allowance is exhausted, so no further image is authorized by these caps. No successful scene/export verification can be claimed. Services are systemd-owned and remain on127.0.0.1:48765; no subagent background browser remains.
