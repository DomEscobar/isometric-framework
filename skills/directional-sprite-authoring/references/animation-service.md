# Optional animation service backend

An authenticated stage API may run facing edit, image-to-video, automatic source
review, background removal and packing. It is an optional operator backend, not
the production authority. The skill route remains: approved generated facing →
image-to-video → reviewed extraction → alpha review →
[pack-sprites](../scripts/pack-sprites.py) → runtime review under the
[asset policy](../../isometric-visual-loop/references/asset-policy.md).

Use this reference only when the host already has a base URL, bearer token and
server policy for the service. Do not hardcode a public host, game name or
deployment path into production records.

## Stage mapping to skill gates

| Service stage or endpoint | Skill meaning |
| --- | --- |
| `inspect_reference` | Numeric inspection of the facing PNG, not visual approval |
| `generate_facing` (paid) | Provider facing edit; result needs visual facing review |
| `generate_video` (paid) | Provider I2V; result needs video review before extraction |
| `POST .../automatic-review` | Bounded reviewer verdict on a source cycle interval; not motion acceptance |
| `extract_frames` | Exports selected frames; still needs cutout and playback review |
| `remove_background` (paid) | Skip for framework hosts: the extractor's removal manifest rejects inputs that are not pixel-identical to its own unkeyed crops |
| `pack` | Emits `animation-pipeline-atlas-v1`; preview only for framework hosts |
| `mirror` | Excluded: derived mirrored motion is not a production route |
| `spatial_export` | Cache replay / preview export; not a V4 provenance substitute |

Job state `completed` means the stage ran. It never means the artwork or gait was
visually approved. Treat `needs_attention` as a hard stop on that prediction; do
not resubmit an ambiguous paid call.

Read the service's published agent guide for the current `params` schemas, quote
caps and capability flags. Paid stages require server enablement plus an explicit
per-request authorization and cap outside `params`: `authorize_paid` with
`budget_cap_usd` for stages, `authorize_paid_review` with `budget_cap_usd` for
automatic review.

## Bridge to framework V4 packing

The service atlas schema is not the stock V4 pack format. To feed
`verify-world` and host binding:

1. Write the ledger records from the service's provider state, using provider
   prediction IDs, never the service job ID: a generation record for the facing
   (provider, model, prediction ID, submitted input, output hash) and a video job
   record with `selectedImageSha256` and `videoSha256`.
2. Keep the job-owned `video-output.mp4` as the local motion source.
3. Take the approved native frame indices or timestamps from the automatic-review
   or human selection receipt.
4. Run the offline [extractor](video-to-sprites.md) `prepare` on that video. Map
   each service native index to a preparation `decodedFrames` entry by matching
   `timeSeconds` within a small epsilon. On constant-frame-rate sources the
   zero-based native index usually equals the preparation index; if they
   diverge, select by timestamp, never by guess.
5. Write those indices into the recipe `selection`, isolate through the skill's
   reviewed removal route, then `export` and pack with `pack-sprites.py`. Do not
   submit the service `atlas.png` / `atlas-manifest.json` as the runtime art pack.

Automatic-review approval of an interval is evidence for which source frames to
extract. It does not replace playback review of the packed clip in the host.
Compact frame selection follows the sampling rule in
[video-to-sprites](video-to-sprites.md#prepare-and-export).

## What not to claim

- Do not describe service outputs as stock framework V4.
- Do not use `mirror` to invent a facing or walk direction.
- Do not treat a public demo atlas or UI replay as production provenance.
- Do not embed operator tokens, environment files or host-specific paths in
  skill instructions or game records.
