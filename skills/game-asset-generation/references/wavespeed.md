# WaveSpeed path

API shapes checked 2026-09-08 against the official
[Seedream Pro model card](https://wavespeed.ai/models/bytedance/seedream-v5.0-pro),
[background remover reference](https://wavespeed.ai/docs/docs-api/wavespeed-ai/image-background-remover),
[edit model card](https://wavespeed.ai/models/bytedance/seedream-v5.0-pro/edit),
[upload guide](https://wavespeed.ai/docs/upload-files), and
[sync guide](https://wavespeed.ai/docs/sync-mode).
Recheck the current schema when a provider rejects a field. Prices displayed in
model cards and README tables can differ; use the current task estimate instead
of baking a price into a skill or spending plan.

## Generate and resume

The included Node 22 client supports text-to-image, Seedream Pro Edit, and the
background-remover endpoints. It uses async jobs and URL outputs. No SDK install is needed.
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
download URL as `image`. Follow the current upload guide; this is not implemented
by the helper. Never forward the API bearer key to a storage ticket or CDN URL.
An existing generated URL can be reused directly without another upload.

## Reference-guided generation and alternatives

For an accepted style/character reference, the separate endpoint is
`bytedance/seedream-v5.0-pro/edit`, with `prompt` and an `images` array, plus
generation settings. The client supports 1–10 public HTTPS reference URLs and
leaves the provider's aspect-ratio default intact when that field is omitted.
Embedded base64 references are outside this helper's supported inputs. References
do not belong in the text-to-image request, whose schema has no image field.
For a complete directional action-pose request, use
[the pose recipe](../../directional-sprite-authoring/references/poses.md).

If another provider is already available, use its supported generation/edit
interface and retain the same source, alpha, and calibration gates. Do not switch
providers merely to satisfy this skill. Seedream availability is not a dependency
of a generated game's runtime.
