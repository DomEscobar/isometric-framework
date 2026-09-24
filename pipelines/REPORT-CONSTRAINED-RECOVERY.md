# Constrained urban recovery — real masked attempt rejected

## Outcome

**A genuinely different provider-side masked edit was implemented and exercised once. It failed badly; no good terrain, new playable candidate, final review, or production ZIP was produced.**

Z-Image Turbo Inpaint received the exact registered **768×408** original and a real canonical sidewalk `mask_image`. It returned a **768×512 JPEG**, replaced the central road and all four planting beds with paving, added upright greenery, and changed the surround. The provider reports `completed`; the service correctly rejected its output before import/review. No output pixels were painted, warped, cropped, resized or composited back into the source to disguise the failure.

![Native before / unchanged rejected provider output](evidence/constrained-recovery/before-after-native.png)

Both panels are **1:1 pixels**, not fitted to equal boxes. The larger right frame is the provider's actual incompatible output, not a gameplay after-image. The exact original JPEG is [provider-original.jpg](evidence/constrained-recovery/provider-original.jpg). Main-parent visual inspection remains separate from this subagent's inspection.

## Important preflight mistake and correction

Free live schema/auth/price discovery and a local mask spike preceded the purchase. They proved real mask-input support, but **did not establish lossless PNG output or exact native-size preservation**. The live Z-Image schema had no `output_format`; its `size` string was hidden in UI metadata. I treated that uncertainty as a testable USD0.02 experiment instead of making positive output-contract evidence mandatory. That was insufficient preflight for this project's exact-preservation contract.

The parent's message identifying that gap arrived **after** the single paid call had completed and controls had already been closed. There was no second purchase. A tested `require_output_contract()` now blocks the service before quote/upload/reservation/submission for this model: live readback returns **“constrained model has no supported lossless PNG output contract; no purchase.”** A future schema change also cannot silently reactivate the adapter; native-size behavior must be investigated anew. This Z-Image route is retired, not recommended for another reroll.

The actual immutable paid prompt also retained a road-recolor finding despite a clear preamble excluding road edits. It is preserved honestly as submitted. Future plan construction now selects only sidewalk and planting-edge findings and records road findings as `deferred_findings`. Neither the historical prompt, intended style spec, review, nor gate was rewritten.

## Free discovery and local spike

Authenticated WaveSpeed catalog metadata is retained under `evidence/constrained-recovery/`:

| Actual live model | Supported relevant fields | Free price evidence | Limitation |
|---|---|---:|---|
| `wavespeed-ai/z-image/turbo-inpaint` | `prompt`, `image`, `mask_image`, `size` | USD0.020; exact uploaded inputs re-quoted at same amount | No output-format selector. Actual native-frame/black-mask preservation failed. |
| `wavespeed-ai/flux-fill-dev` | `image`, `mask_image`, `prompt`, `size`, steps, seed, guidance, count, LoRAs | USD0.035 estimated for one 768×408 image | No explicit PNG field; docs discuss dimensions but do not prove this exact output contract. Not purchased. |
| `openai/gpt-image-1.5/edit` | `images`, `input_fidelity`, `output_format`, fixed size enum | Live catalog base USD0.10, not an exact request quote | Deployed schema has **no mask field**; size enum cannot request 768×408. Not purchased. |

Documentation checked:
- https://wavespeed.ai/docs/docs-api/wavespeed-ai/z-image-turbo-inpaint
- https://wavespeed.ai/docs/docs-api/wavespeed-ai/flux-fill-dev

The no-paid spike validated the original seed's registration, genuine valid FAIL review and receipt bindings. Its exact final-density input hash is `a6763bfdba7c8f54cc9c893680dc7817b13465680e45d9bc57f0a2f1d0cfeb33`.

Canonical mask: **66,824 editable pixels; 246,520 protected pixels; zero road-mask overlap**, fixed 3px outer-frame inset. Mask hash: `d368a5f1664f88d0ef75ceba2b72d9b668095e3f1d38ac8f804ac5737863017f`. The model has no separate style-reference/guide-image field. Its actual image is the registered source; the guide determines the real input mask; immutable style text and lineage remain bound. No unsupported reference fields were invented.

After the failure, **both provider input URLs were downloaded and byte/hash-compared** against retained source and mask. Both matched. The input roles were not accidentally swapped or uploaded incorrectly. Free prediction readback confirms the correct model, prediction and completed output. Its returned output bytes exactly match the retained original.

## Durable identities and budget

| Identity | Value |
|---|---|
| Sealed parent run | `3c932cbd0832cc4707bc8281f828eb837930c89b9dd399ca90223df0f3c697da` |
| New constrained run | `fa4dc8b6ce4169b697edf707653a10655fa5003defdab5717ca5dabe0d7c9606` |
| Selected registered original | `6caa5a1bfa96eddce1ed0c3c337e4791698d156b825d1ee844de70f409353ac9` |
| Genuine seed review, unchanged | `0012a0ba2f020447d6a4969cea7d3150556e9e883545e59f164b2b0b31dc6d6d` |
| Shared-ledger quote/job | `ca3f6781b023e4b9847c26770944b2a151d7c2f5a70edafc6f1d182d856accd4` |
| Real provider prediction | `fa76c587a9164fe0a8d6b9459b9867c0` |
| Exact request SHA256 | `7017853e055176184f6828527b341fc780a03e1bb8ad4897ed1fe47e562b0e66` |
| Exact original JPEG SHA256 | `e72e4ebc51094cdc1e7a9ef6e2abb539439094bd38822830e69a35feb23f4162` |

**Lifetime 4/15**, including the inherited three attempts. This successor has an additional hard limit of **one** new image attempt. It selects a real reviewed registration from the parent's immutable history, not an arbitrary manually imported candidate. Best remains the old unapproved best; Latest remains the input because the rejected provider image was never admitted as a candidate.

| Accounting | USD |
|---|---:|
| Starting central holds | 4.853712 |
| One new masked image quote/reservation | 0.020000 |
| New review purchases | 0 |
| **Final total holds** | **4.873712** |
| All image holds, seven jobs | 0.086000 |
| All review holds, six reservations | 4.787712 |
| Remaining within original USD10 ceiling | 5.126288 |

The conservative USD0.801792 final-review headroom was checked before the image, but **not reserved or spent**, because the output failed the input/output contract first. Quotes are not final invoices. Every previous liability remains included; historical HTTP401 reconciliation was neither repeated nor released. Generation, review, quality-recovery and constrained-recovery controls are all closed, with global image cap7/7.

## Verification and implementation

- **224 pytest passed**,159 existing framework deprecation warnings; full output `evidence/constrained-recovery/tests-final.txt`. Before the purchase:221 passed. RED→GREEN tests cover provider template/central ledger reuse, legacy model isolation, closed start, unique successor/history selection, one-attempt lifetime accounting, control signatures, canonical mask and protected-pixel rejection, exact-original download tampering, missing lossless contract and mask-applicable prompt filtering. Provider mocks are explicitly not live-art evidence.
- Real fresh-server HTTP: original download200 and exact hash; closed masked start409; closed generation403; seed production download409; terminal status/resume leaves holds/records unchanged.
- Real headless browser: native original natural/display sizes both768×512, exact browser-downloaded JPEG bytes, actual workflow status showing4/15, no page errors, unchanged accounting and production409. `browser-report.json`, `browser-original-native.png`, `browser-run-status.png`.
- UI now explains **“Providerbild erhalten, lokal verworfen”**, identifies 768×408→768×512 JPEG, states that Latest is still the old input, and links the retained original. The old `provider_failed` terminal code is retained rather than rewriting sealed evidence; it represents local rejection, **not a remote transport failure**.
- Production gate unchanged; no new candidate/evaluation or production ZIP. No registration threshold relaxation or new fitted transform. No public deployment, game/animation edits, or new project budget.

New implementation: `constrained_provider.py`, `constrained_adapter.py`; extensions to `generation.py`, `auto_repair.py`, `auto_adapter.py`, `static/workflows.js`. New tests: `tests/test_constrained.py`, `tests/constrained-browser.mjs`. Tools: `constrained_discovery.py`, `constrained_spike.py`, `live_constrained_recovery.py`, `verify_constrained_recovery.py`. Spike notes: `spikes/001-constrained-recovery/README.md`. Historical inputs/requests/parent records remain unchanged. The paid harness is **not** a regression command.

Raw provider bytes and full provider readback stay server-side at `data/constrained-outputs/<job-id>/`; signed input/output URLs are not exposed in public endpoint responses. Exact browser download: `evidence/constrained-recovery/browser-downloaded-original.jpg` (JPEG, not ZIP).

## Parent inspection / fresh local server

Read first:
1. `evidence/constrained-recovery/before-after-native.png`
2. `evidence/constrained-recovery/provider-original.jpg`
3. `evidence/constrained-recovery/verification.json`
4. `evidence/constrained-recovery/browser-run-status.png`

Fresh local viewer used: `http://127.0.0.1:45567/`. The parent-owned38363 server was not touched. Restart from latest code if needed:

```sh
cd /root/services/layout-terrain-pipeline
python3 -m uvicorn app:app --host 127.0.0.1 --port 45567 --no-access-log
python3 tools/verify_constrained_recovery.py
node tests/constrained-browser.mjs
```

Original endpoint: `/api/generation/jobs/ca3f6781b023e4b9847c26770944b2a151d7c2f5a70edafc6f1d182d856accd4/constrained-original`.

**Remaining blocker:** no demonstrated provider route satisfying supported mask **and** exact native lossless canvas/protected-pixel preservation. Do not purchase Flux or reroll Z solely because they advertise inpainting. The deliverable is a real rejected experiment, preserved evidence and a tested fail-closed integration—not finally good terrain.
