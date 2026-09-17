# WaveSpeed path

API shapes checked 2026-09-17 against the official
[Seedream Pro model card](https://wavespeed.ai/models/bytedance/seedream-v5.0-pro),
[image background remover reference](https://wavespeed.ai/docs/docs-api/wavespeed-ai/image-background-remover),
[video background remover reference](https://wavespeed.ai/docs/docs-api/wavespeed-ai/video-background-remover),
[edit model card](https://wavespeed.ai/models/bytedance/seedream-v5.0-pro/edit),
[upload guide](https://wavespeed.ai/docs/upload-files), and
[sync guide](https://wavespeed.ai/docs/sync-mode).
Recheck the current schema when a provider rejects a field. Prices displayed in
model cards and README tables can differ; use the current task estimate instead
of baking a price into a skill or spending plan.

## Generate and resume

The included Node 22 client supports text-to-image, Seedream Pro Edit, the image
background-remover, and the video background-remover. It uses async jobs and URL
outputs. No SDK install is needed. It does not generate image-to-video.
The wrapper restricts generation to PNG for this asset workflow even though the
provider also accepts JPEG, and rejects unsupported fields instead of guessing.
Set `WAVESPEED_API_KEY` through the environment/secret mechanism already in use;
never put a real key in a checked-in example or print it for debugging.

From `Runtime/` (adjust paths when using an installed/copied skill), save a request
as `test-results/assets/flower.request.json`, after creating its parent directory:

```json
{
  "prompt": "One isolated orange marigold clump, 2:1 isometric pixel art, warm upper-left light, full leaves and stems, generous margin, flat contrasting backdrop, no soil, pot, shadow, text or checkerboard",
  "aspect_ratio": "1:1",
  "resolution": "1k",
  "output_format": "png",
  "prompt_optimization_mode": "standard"
}
```

```sh
node skills/game-asset-generation/scripts/wavespeed.mjs submit bytedance/seedream-v5.0-pro test-results/assets/flower.request.json test-results/assets/flower.job.json
# Recovery only: submit already waits; use resume after timeout/interruption.
node skills/game-asset-generation/scripts/wavespeed.mjs resume test-results/assets/flower.job.json
```

Use `submit` once. `resume` queries the saved prediction without creating another
generation; use it after a polling timeout or interruption. The client refuses an
existing job filename, persists the prediction ID, bounds polling (default five
minutes; `--timeout-ms` overrides), retries transient GET failures, and never
automatically retries a billable POST. If submission failed ambiguously before an
ID was received, inspect provider history before deciding whether a new submission
is needed. A local timeout does not cancel the server job.

Exit codes: 0 completed, 1 remote/terminal/persistence error, 2 local input error,
3 polling budget exhausted. A completed job contains output URLs. Download those
to new local files using a normal HTTP client, without the API Authorization
header. Verify image decoding and actual format; a `.png` filename alone proves
nothing. Keep signed URLs out of published provenance and use the prediction ID
plus local hashes instead. Save accepted art locally before URL expiry.

For example, after completion in PowerShell (use a fresh destination filename):

```powershell
$assetJob = Get-Content -Raw test-results/assets/flower.job.json | ConvertFrom-Json
if ($assetJob.status -ne 'completed' -or -not $assetJob.outputs.Count) { throw 'Job is not complete' }
if (Test-Path -LiteralPath test-results/assets/source.png) { throw 'Keep the existing source; choose another filename' }
Invoke-WebRequest -Uri $assetJob.outputs[0] -OutFile test-results/assets/source.png
```

On other shells, copy the completed output URL into a file downloader such as
`curl --fail --location --output source.png 'OUTPUT_URL'`. Do not attach the API
key. Inspect the decoded file before calling it PNG or integrating it.

The wire flow is POST `https://api.wavespeed.ai/api/v3/{model}` with bearer auth,
then GET `/api/v3/predictions/{id}/result`. Completion is `data.status=completed`,
with output values in `data.outputs`. Failed/cancelled/timeout/deleted jobs are
terminal. HTTP success alone does not establish generation success.

## Fan out independent jobs

A pass over several assets or directions waits on the provider, not on local work.
`wavespeed-batch.mjs` runs independent jobs of one model concurrently, each through
the same audited `submit` path above, and writes one result fragment per track. Paths
in a batch manifest are relative to the manifest's own directory and use forward
slashes.

```json
{
  "version": 1,
  "concurrency": 4,
  "pilot": "pilot/walk-south/result.json",
  "tracks": [
    {"id": "walk-south", "model": "bytedance/seedream-v5.0-pro", "request": "walk-south.request.json", "job": "walk-south.job.json"},
    {"id": "walk-north", "model": "bytedance/seedream-v5.0-pro", "request": "walk-north.request.json", "job": "walk-north.job.json"}
  ]
}
```

```sh
# Pilot first: one track proves the model and request shape.
node skills/game-asset-generation/scripts/wavespeed-batch.mjs run test-results/assets/pilot.batch.json test-results/assets/pilot --approve 1
# Download and review that output, then set "accepted": true in its result fragment.
node skills/game-asset-generation/scripts/wavespeed-batch.mjs run test-results/assets/facings.batch.json test-results/assets/facings --approve 4
# Recovery only, for tracks whose polling budget ran out. Submits nothing.
node skills/game-asset-generation/scripts/wavespeed-batch.mjs resume test-results/assets/facings.batch.json test-results/assets/facings-resumed
```

Before any submission it rejects a duplicate or existing job path, a request the
client would refuse, an approval number that differs from the track count, an
existing results directory, and a concurrency above 8. `--approve N` authorizes
exactly N billable submissions; a money ceiling comes from the provider's current
task estimate, not from this script. More than one track needs `pilot`: the fragment
of an accepted single-track run with the same model and the same request fields.

Concurrency is capped because a rejected POST is never retried here. A rate limit
therefore arrives as a task whose outcome must be inspected by hand, and each further
launch would add another one.

| Track disposition | Meaning | Next step |
| --- | --- | --- |
| `complete` | Outputs are listed in the job file | Download, review, then set `accepted` |
| `resume-required` | Local polling stopped; the remote task lives on | Resume this batch |
| `task-failed` | The provider rejected or dropped the task | Decide on a new request |
| `inspect-provider-history` | The submission outcome is unknown | Inspect provider history; the batch stopped launching |
| `not-started` | The batch halted before this track | Nothing was submitted for it |
| `missing-job` | Resume found no job file | It was never submitted |

Batch exit codes: 0 all complete, 1 a failed or unknown task, 2 invalid local input,
3 a track needs resuming. Fragments record the prediction ID, request hash and output
count, deliberately not the signed URLs or the prompt; download the outputs from the
job file as below.

The batch writes only per-track fragments. Update the runtime manifest, binding and
coverage ledger from them in one sequential step: every production check from the
static stage onward hashes those files as inputs and fails if they change while it is
in flight.

## Remove a background

Save another request with the actual publicly retrievable generated image URL:

```json
{"image":"https://your-image-host.example/flower-source.png"}
```

```sh
node skills/game-asset-generation/scripts/wavespeed.mjs submit wavespeed-ai/image-background-remover test-results/assets/remove.request.json test-results/assets/remove.job.json
```

Replace the example URL before execution. Download the output separately, leaving
the source unchanged. This model documents URL input; do not confuse its optional
base64 **output** flag with support for local file paths or base64 input. The
wrapper intentionally omits sync/base64 output options. With other clients,
sync timeout can still leave a live prediction: retain its ID and poll it.

For a local-only source, either use local removal or the provider's upload flow:
request a ticket with POST `/api/v3/media/uploads` and filename/size/content_type,
PUT the bytes to the ticket URL using its supplied headers, then pass the returned
download URL as `image`. The helper implements this for one local PNG at a time:

```sh
node skills/game-asset-generation/scripts/wavespeed.mjs remove-local path/to/frame.png path/to/frame.job.json
```

It reserves the job record, validates the local PNG, follows the ticket's opaque
upload method/URL/headers without adding the API bearer token, and submits the
remover exactly once. Resume only a job that already has a prediction ID. A failure
before remover submission needs inspection and a new job path; an ambiguous
submission must never be retried blindly. Existing generated URLs may still use
the explicit request-file route above.

## Isolate a reviewed animation video

When chroma-key review of a character clip fails or is uncertain, an approved
option is to isolate the whole reviewed I2V video before extraction, instead of
removing the background from each selected frame. The model is
[`wavespeed-ai/video-background-remover`](https://wavespeed.ai/models/wavespeed-ai/video-background-remover).
Omit `background_image`: the documented default then returns a transparent cutout.
A replacement plate is compositing, not isolation, and this client rejects that
field.

Keep the original I2V file. Submit a publicly retrievable HTTPS URL of that video:

```json
{"video":"https://your-video-host.example/walk-source.mp4"}
```

```sh
node skills/game-asset-generation/scripts/wavespeed.mjs submit wavespeed-ai/video-background-remover test-results/assets/video-remove.request.json test-results/assets/video-remove.job.json
```

Video jobs can outlast the default five-minute poll; raise `--timeout-ms` rather
than submitting again. Resume an interrupted prediction from its job file. Download
the completed output to a fresh local path and inspect decoded frames for real
alpha over contrasting backgrounds and in playback. A completed prediction is not
mask approval, and an opaque container (typical MP4 without alpha) is a failed
cutout even when the job succeeded. Prepare extraction from the isolated video
with `--key` omitted so the extractor preserves that alpha. The per-frame image
remover remains the other approved fallback when only selected stills need
isolation; do not silently substitute local `rembg` on character motion.

A local-only video still needs a public HTTPS URL for this model. Use the same
upload-ticket flow as a local PNG (`POST /api/v3/media/uploads`, PUT the bytes with
the ticket headers, then pass `download_url` as `video`). There is no
`remove-local` helper for video.

## Reference-guided generation and alternatives

For an accepted style/character reference, the separate endpoint is
`bytedance/seedream-v5.0-pro/edit`, with `prompt` and an `images` array, plus
generation settings. The client supports 1–10 public HTTPS reference URLs and
leaves the provider's aspect-ratio default intact when that field is omitted.
Embedded base64 references are outside this helper's supported inputs. References
do not belong in the text-to-image request, whose schema has no image field.
For character motion, follow
[directional sprite authoring](../../directional-sprite-authoring/SKILL.md): use
an approved generated facing image with an approved capable I2V tool, review the
actual video, then extract, pack and verify runtime playback. Reference support
does not establish animation quality.

## Optional video-to-sprite input

The bundled `wavespeed.mjs` client does **not** generate image-to-video. Do not
reuse an image-edit payload, name a hypothetical WaveSpeed I2V route, or claim
that this client submitted an I2V request. The video background-remover above
isolates an already reviewed clip; it is not a motion generator. Use another
approved, capable I2V tool only after checking its current schema and actual
callable access. If it is unavailable, or budget/access is missing, record the
blocker and stop before generation.

For a capable tool, supply the approved generated character view in the required
direction and record the actual submitted image, input roles, request/job ID and
returned local video hash. A reference's facing can outweigh conflicting direction
text. Choose a flat key color absent from the subject if transparent output is
unavailable. Keep source videos local after completion and resume an existing job
after interruption rather than resubmitting.

Use [video-to-sprite extraction](../../directional-sprite-authoring/references/video-to-sprites.md)
for deterministic preparation, selected frames and review. Inspect actual alpha,
facing and playback; successful video generation is not accepted animation.

If another provider is already available, use its supported generation/edit
interface and retain the same source, alpha, and calibration gates. Do not switch
providers merely to satisfy this skill. Seedream availability is not a dependency
of a generated game's runtime.

Run the [packed-art and acceptance checks](../../isometric-visual-loop/references/acceptance.md)
on the host manifest after binding accepted outputs. A completed prediction leaves
visual and motion acceptance open until observed.
