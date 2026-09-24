# Pipeline worker contract

This module implements `pipeline.run_stage(stage: str, workdir: pathlib.Path, params: dict) -> dict`.

Every result is JSON-safe and has exactly these top-level fields:

- `status`: `completed`, `needs_review`, or `needs_attention`.
- `artifacts`: job-directory-relative safe paths created or reused by the stage.
- `details`: hashes, dimensions, provider IDs, quote/charge distinction, and derivation labels.

All input names are relative to `workdir`. Absolute paths, `..`, symlinks, URLs supplied by clients, unsupported extensions, and files outside the job directory are rejected. Provider source URLs are obtained only by authenticated upload of a job-owned file. Provider output URLs are accepted only from the authenticated prediction response.

Stage calls are idempotent by a canonical request identity that includes params and input SHA-256 values. Paid stages write their state atomically before submission. An identical call reuses the completed result or polls the recorded prediction ID. A different call cannot reuse that state. A submission whose acceptance is ambiguous returns `needs_attention`; it is never submitted again automatically.

## inspect_reference

Params: `{"input":"reference.png"}`.

Accepts PNG/JPEG/WebP. Returns `completed`, writes `inspect-reference.json`, and reports format, mode, dimensions, byte count, SHA-256, alpha extrema/histogram summary, visible alpha bounds, and whether usable non-opaque alpha exists. Inspection is numeric, not visual approval.

## generate_facing (paid)

Params:

```json
{
  "input": "reference.png",
  "preset": "waldlicht-facing-v1",
  "prompt": "non-empty edit instruction",
  "aspect_ratio": "1:1",
  "output_format": "png",
  "budget": {"authorized": true, "max_usd": 0.011}
}
```

Uses configured preset `waldlicht-facing-v1` and recorded WaveSpeed schema `meta/muse-image/edit`: required `prompt`, `image_urls`; one job-owned input is authenticated-uploaded and its server-supplied URL is inserted by the adapter. `preset` may be omitted to select this server default; unknown or capability-mismatched presets are rejected. `aspect_ratio` is optional; `output_format` defaults to `png`. Recorded estimate is USD 0.011/run and is always labelled an estimate. Success downloads `facing-output.png` and returns `needs_review`.

## generate_video (paid)

Params:

```json
{
  "input": "facing-output.png",
  "preset": "waldlicht-video-v1",
  "prompt": "motion instruction",
  "negative_prompt": "optional exclusions",
  "duration": 5,
  "seed": -1,
  "budget": {"authorized": true, "max_usd": 0.10}
}
```

Uses configured preset `waldlicht-video-v1` and recorded WaveSpeed schema `wavespeed-ai/wan-2.2/i2v-720p-ultra-fast`: required `prompt`, `image`; the recorded provider schema allows duration 5 or 8 seconds, but this preset supports only the quoted 5-second operation. The job-owned image is authenticated-uploaded. The recorded estimate is USD 0.10 for 5 seconds; 8-second pricing is intentionally unsupported until quoted and is rejected before submission. Success downloads `video-output.mp4` and returns `needs_review`.

The selectable `gemini-omni-video-3s-v1` preset maps to `google/gemini-omni-1.1-flash/image-to-video` and accepts exactly `prompt`, `duration: 3`, `resolution: "360p"`, and `aspect_ratio: "16:9"` in addition to the job-owned input. It deliberately rejects WAN-only `seed`/`negative_prompt`, other durations, resolutions, aspect ratios, and `last_image`. Its fetched WaveSpeed schema permits durations 3..10, 360p/720p/1080p/4k and 16:9/9:16; this named preset is narrower because only the exact 3-second 360p 16:9 operation has a stored USD 0.09 estimate. A square source is framed into 16:9, so the prompt must preserve the complete figure, feet, held props and margins; this preset does not promise that the provider will obey the framing request. It is not described as universally cheaper or better than WAN.

The selectable `minimax-h3-ne-source-5s-768p-v1` preset remains the fixed legacy MiniMax configuration. It accepts one job-owned image plus `prompt`, exactly `duration: 5`, exactly `resolution: "768p"`, and an optional integer seed. Its existing explicit settings and USD 0.20 discounted recorded estimate remain unchanged for replay and older fixtures.

The backward-compatible `minimax-h3-action-3s-480p-v1` preset maps to `wavespeed-ai/minimax-h3/image-to-video` and is the configurable source-video preset. It accepts one job-owned image plus `prompt`, duration `3`, `5`, `8`, or `10`, resolution `"480p"` or `"768p"`, and an optional integer seed. Omitted source settings default to 3 seconds and 480p. The adapter sends the identical uploaded full-resolution image as both `image` and `last_image`; the provider canvas follows that image's aspect ratio. The allowed service subset is narrower than the live-fetched 2026-09-21 provider schema (3..15 seconds and 480p/540p/768p/1080p). Quote and budget validation use the selected pair: the recorded discounted estimate is USD 0.02/second at 480p and USD 0.04/second at 768p, grounded by the retained 3s/480p USD 0.06 and 5s/768p USD 0.20 quote records. The exact duration and resolution are bound in queued params, request identity, provider payload, quote and persisted provider state. Same-frame endpoints constrain the boundary but do not prove motion; static output must be rejected during source review.

## extract_frames

Params:

```json
{
  "input": "video-output.mp4",
  "fps": 12,
  "indices": [6,7,8],
  "output_prefix": "selected"
}
```

Manual requests run ffmpeg once at the declared FPS, then copy only the explicitly selected zero-based decoded frame indices as lossless RGBA PNGs named `<prefix>-frame-0000.png` etc. The server-owned automatic-review runner may add a non-client-forgeable typed receipt; that path uses ffmpeg `select` on the validated contiguous native frame indices instead of FPS resampling. `extract-frames.json` records which selection mode was used, source hash, indices/timestamps, dimensions, alpha summary and hashes. Both paths return `needs_review`; extraction is not downstream visual or alpha approval.

## remove_background (paid)

Params:

```json
{
  "inputs": ["selected-frame-0000.png"],
  "preset": "waldlicht-removal-v1",
  "budget": {"authorized": true, "max_usd": 0.004}
}
```

Uses configured preset `waldlicht-removal-v1` and recorded WaveSpeed schema `wavespeed-ai/image-background-remover`, one authenticated local upload and one prediction per input. Recorded estimate is USD 0.004/image. The whole batch quote must fit the cap before any submission. Existing true alpha can be preserved by skipping this stage and packing the original selected cutouts. Success writes `cutout-frame-0000.png` etc., verifies non-empty real alpha, and returns `needs_review`. A partly submitted or ambiguous batch returns `needs_attention` and never blindly resubmits.

## pack

Params:

```json
{
  "inputs": ["cutout-frame-0000.png", "cutout-frame-0001.png"],
  "image_id": "keeper-walk-ne",
  "action": "walk",
  "direction": "ne",
  "fps": 12,
  "loop": true,
  "canvas": {"width": 80, "height": 80},
  "target_visible_height": 58,
  "target_root": {"x": 40, "y": 72},
  "anchor": {"x": 0.5, "y": 0.9},
  "gutter": 2,
  "columns": 8,
  "resample": "nearest",
  "cleanup": {
    "recipe": "conservative-alpha-fringe-v1",
    "minimum_visible_alpha": 8
  }
}
```

All source frames must have the same dimensions and non-empty alpha. One shared scale is derived from the median visible alpha height. One shared source root is derived from the median alpha-weighted x centroid and median visible bottom. The same full-canvas resize and paste offset is applied to every frame; per-frame crop/recenter is forbidden. Frames touching or leaving the target canvas are rejected.

`cleanup` is optional for legacy replay and explicit when used. The pinned `conservative-alpha-fringe-v1` recipe runs only after the shared transform and clears RGBA where `0 < alpha < 8`. It does not key colors, remove connected components, fill holes, draw pixels, or change any pixel with alpha at least 8. `normalization.json` records the canonical recipe hash, pre/post RGBA hashes, alpha changes and RGB changes separately for every frame; the atlas manifest binds the same recipe. The atlas gate rejects surviving 1..7-alpha resampling fringe while allowing strong disconnected details such as a lantern.

Outputs: `normalized-frame-NNNN.png`, `atlas.png`, `atlas-manifest.json`, `normalization.json`, and `pack-result.json`. The deterministic row-major pack schema is named `animation-pipeline-atlas-v1`. It is not claimed to be the isometric-framework stock V4 pack/provenance format. The manifest binds source and normalized-frame hashes, atlas hash, frame rectangles, alpha bounds, anchor and clip timing; `pack-result.json` binds the final manifest SHA-256.

## mirror

Params:

```json
{
  "atlas": "atlas.png",
  "manifest": "atlas-manifest.json",
  "target_direction": "nw",
  "target_image_id": "keeper-walk-nw-derived"
}
```

Mirrors each declared RGBA frame exactly, without resampling, and mirrors normalized anchor x as `1-x`. Outputs `mirror-atlas.png` and `mirror-manifest.json`, returns `needs_review`, and labels every output `DERIVED_NOT_PROVIDER_GENERATED`. The manifest warns that handed props (for example a lantern) switch screen side. No stock V4 acceptance is claimed.

## Provider state, quotes and charges

`provider.py` implements authenticated WaveSpeed upload (`POST /media/uploads`, then server-ticket `PUT`), one-shot prediction submission (`POST /<model>`), and safe resume (`GET /predictions/<id>/result`). POST is never retried. Prediction IDs are validated and persisted immediately. Network/HTTP/response ambiguity before a valid ID is represented as `submission_unknown`/`needs_attention`. Once an ID exists, only that ID is polled. Quotes are recorded estimates, while actual charge remains `null`/unknown unless the provider supplies an authoritative value.

The model schemas and prices are the recorded Waldlicht records, not live-discovery claims:

- `art/character-motion/ne-facing-01/schema-01.json` — Muse edit, USD 0.011.
- `art/character-motion/ne-video-01/schema.json` — WAN 5-second I2V, USD 0.10.
- `artifacts/gemini-omni-video-3s-01/schema.json` and `quote.json` — fetched Gemini Omni schema and exact 3-second/360p/16:9 estimate, USD 0.09.
- `art/character-motion/se-cutout-01/schema.json` — remover, USD 0.004/image.

`provider.AdapterRegistry` is the extension boundary. Tests register the explicitly offline `FixtureAdapter` to prove alternate-adapter selection without claiming that any alternate model was live-tested.

## Free real-data replay

`python3 tools/replay_existing.py --replace` copies the accepted Waldlicht keeper reference plus all 16 accepted SE provider cutouts into `artifacts/replay-existing/`. It runs `inspect_reference` and the generic `pack`, then requires every normalized PNG hash, dimension and alpha record plus the final atlas hash to equal Waldlicht's accepted recorded outputs. The source game remains read-only and the replay makes zero provider calls. Full provenance and measurements are in `artifacts/replay-existing/replay-report.json`.

## Automatic cycle and cadence gates

Local candidate analysis normalizes the detected foreground before comparing loop poses, measures head-region skin visibility/centroid as a source-pose orientation signal, and records rejected alternatives separately from selectable candidates. A low whole-frame endpoint difference cannot outrank an interval that rotates the character: orientation drift, a discontinuous normalized loop pose, or failure to leave and return to the starting motion state rejects the interval before reviewer submission. These measurements are deterministic technical evidence, not visual approval.

After the reviewer chooses a complete alternating cycle, export sampling uses one explicit hash-bound policy: compact `8` (default), `12`, `16`, or backward-compatible dense `native` (`native-density-v2`). Compact modes spread exactly the selected count over the original start-inclusive/end-exclusive interval, preserve its duration by setting playback FPS to count/duration, and have no artificial 18 FPS minimum. They reject cycles with too few distinct originals. All modes use exact original frames only: no interpolation, duplicates, ping-pong, or filler. Reviewer evidence images are independent from export frames. `selection-density-receipt.json` binds the immutable reviewer receipt hash, source revision/hash, approved interval, policy option/hash and deterministic indices; the same binding continues through extraction and atlas manifests. Analysis caches are policy-bound so a different density choice cannot reuse a stale receipt. The native option retains the prior bounded 18 FPS/pose-gap behavior for old receipts and explicit dense exports.

## Unsupported rather than simulated

No stage visually approves an image or motion. No arbitrary client URL is accepted. No 8-second WAN job is submitted without a recorded quote. No output is described as stock framework V4. Unsupported provider statuses, schemas, media types, and unsafe paths raise `ValueError` or return `needs_attention`; no fabricated provider output is created.

## Private reusable spatial runner

`spatial_export.py CONFIG.json` is the reusable downstream runner for an exact,
already-reviewed selection. It invokes the existing `extract_frames` stage,
then uses verified content-addressed cutouts and deterministic local processing.
Its cache identity is `(extracted input SHA-256, provider preset, removal
recipe)`; output size and geometry are deliberately outside that key so native
160px and 80px products are independently derived from the same full-resolution
master. Neither variant is derived from the other.

The config must bind the source-video SHA-256, selection receipt and exact native
indices. The current CLI accepts only `explicit_human_reviewed`; it fails rather
than labelling those indices automatic. Every run writes `run-result.json`,
`timings.json`, `verification.json`, a manifest player and `export.zip` in a
fresh output directory. Provider calls are absent from this cache replay path.

The authenticated service exposes the same path as `spatial_export`. Its params
are exactly `source`, `selection_receipt`, `selection_mode`, `export_preset`,
`removal_preset`, and `removal_recipe`; artifact fields must be safe job-owned
basenames and presets are server allowlisted. Explicit mode requires current
human approvals for both source and the receipt generated by
`POST /v1/jobs/{id}/selections`. Automatic mode requires the source's current
typed `automatic_model_validated` approval and validates the exact automatic
result, analysis, source hash, extracted native indices and model before export.
An explicit receipt cannot be relabelled automatic. Cache misses stop with no
provider submission; clients must separately authorize the paid removal stage.

Removal submission inside the service supports a server-owned bounded
in-flight limit `ANIMATION_REMOVAL_MAX_INFLIGHT` (1..5, default 5). A configured bound submits only while slots are
available, polls immutable known IDs first, atomically persists each ID, retains
ambiguous liabilities and never submits later items after a definite partial
failure. The whole batch quote is still authorized before the first upload.
Per-item UTC/monotonic upload, submit, poll, download and normalize/verify
timings plus configured and actually observed maximum in-flight counts are persisted in `remove-background-state.json`. Provider rejection or rate limiting is reported as a measured blocker; the service does not silently relabel lower concurrency as five.
