# Animation Pipeline API

Local, single-owner FastAPI service around `pipeline.run_stage(stage, workdir, params)`. The API uses a durable SQLite queue and one serial worker. It binds to localhost in all documented commands.

## Framework integration

This service is an optional backend for
[directional sprite authoring](../../skills/directional-sprite-authoring/SKILL.md).
Map stages and bridge video plus approved native indices through
[animation-service.md](../../skills/directional-sprite-authoring/references/animation-service.md)
into `extract-video.py` / `pack-sprites.py`. Do not treat `animation-pipeline-atlas-v1`
or the `mirror` stage as stock framework V4 production outputs.

## Install in an isolated environment

```sh
cd /root/services/animation-pipeline
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

No global Python installation is required or modified.

## Run locally

```sh
cd /root/services/animation-pipeline
export ANIMATION_API_TOKEN='replace-with-a-long-random-token'
export ANIMATION_DATA_DIR="$PWD/var"
export ANIMATION_PAID_ENABLED=0
export ANIMATION_MAX_STAGE_USD=0
export ANIMATION_REVIEW_ENABLED=0
.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 4386
```

`GET /health` is public. Every `/v1/*` endpoint requires an `Authorization: Bearer ...` header containing the configured API token. If `ANIMATION_API_TOKEN` is absent, protected endpoints return 503 rather than enabling anonymous access.

Paid stages are disabled unless both server settings explicitly enable them. A client request alone cannot enable spending. Do not set `ANIMATION_PAID_ENABLED=1` without a separately approved provider budget and credential policy.

Automatic source review has a separate OpenRouter policy and is disabled by default. Local video analysis remains free and available while the reviewer is blocked. Enabling one-shot review requires all of the following server-owned settings; it does not enable WaveSpeed generation:

```sh
export ANIMATION_REVIEW_ENABLED=1
export OPENROUTER_API_KEY='server-owned-key'
export ANIMATION_REVIEW_MAX_USD=0.05
export ANIMATION_REVIEW_MAX_INPUT_TOKENS=50000
export ANIMATION_REVIEW_MAX_OUTPUT_TOKENS=1200
export ANIMATION_REVIEW_MODEL_METADATA_FILE='/absolute/path/to/fresh-openrouter-model-metadata.json'
```

The metadata file must be fetched from `https://openrouter.ai/api/v1/models` within the previous 24 hours, identify exactly `google/gemini-3.8-flash`, declare text/image/video input, structured response parameters, and token pricing. The runner allows no fallback and makes no blind paid retry. A request must additionally authorize that single review and provide a cap no larger than `ANIMATION_REVIEW_MAX_USD`.

## Browser UI

Open `http://127.0.0.1:4386/ui/`. The same relative URL works when the service is reverse-proxied below a prefix such as `/animation/ui/`; the UI derives the API prefix from its own location instead of hardcoding `/v1` at the domain root.

Enter the API token in the password field. It is held in memory and this tab's `sessionStorage`, never added to a URL or served HTML. The public demo uses only the allowlisted replay atlas and its generic `animation-pipeline-atlas-v1` manifest. Job data, uploads, reviews, artifacts and ZIP downloads remain bearer-authenticated. Artifact previews are fetched with the bearer header and displayed through local blob URLs.

Uploading a PNG starts only the free `inspect_reference` stage. Paid controls reflect the authenticated `/v1/capabilities` server policy, require an explicit per-stage authorization and cap, and remain disabled when server policy disables paid execution.

For the MiniMax H3 source-video preset, the UI exposes `Videodauer` values 3, 5, 8 and 10 seconds plus `Videoauflösung` values 480p and 768p; defaults are 3 seconds and 480p. These source-video settings are separate from automatic export sampling (8/12/16/native frames) and the later 80/160 px sprite products. `/v1/capabilities` publishes the preset-specific choices and quotes. Unsupported values and values intended for another video model are rejected before queueing or provider access.

For jobs that already contain a recorded video artifact, the UI exposes automatic source selection separately from video generation. It shows local candidates, exact timestamps/native frame indices, reviewer availability, and any selected candidate. `google/gemini-3.8-flash` is labelled as the review model, never as the image-to-video generator.

## Coding-agent integration

The public UI contains a German `Für Coding-Agents` section whose prompt is
loaded from the same public, token-free source that agents can read directly.
Production URLs:

- `https://huecki.com/animation/agent-prompt.txt`
- `https://huecki.com/animation/agent-guide.md`
- `https://huecki.com/animation/openapi.json`
- `https://huecki.com/animation/docs`

The OpenAPI document declares the public `/animation` server prefix and bearer
security on `/v1/*`. Health, UI and documentation remain public. The guide is
the authoritative programmatic schema and example source for the deliberately
generic, stage-specific `params` object. It documents the tested free upload →
inspect → poll → artifact/ZIP path, review gates and current paid-stage policy
without embedding the owner token. External agents must read the token only
from `ANIMATION_API_TOKEN`; the v1 token is a single-owner credential with
access to every job, not a scoped third-party token.

## API v1

### Upload and inspect a reference

The v1 upload accepts PNG only, at most 20 MiB, at most 4096 pixels per side and at most 16 million pixels. The server stores it under the fixed job-owned name `reference.png`; the client filename is never used as a filesystem path.

```sh
curl --fail-with-body \
  -H "Authorization: Bearer $ANIMATION_API_TOKEN" \
  -F 'reference=@/absolute/path/reference.png;type=image/png' \
  -F 'options={"auto_start":true}' \
  http://127.0.0.1:4386/v1/jobs
```

`auto_start:true` queues the free `inspect_reference` stage. Inspection is numeric processing, not visual approval. A job state of `completed` means the stage ran successfully; it does not mean that any artwork was visually approved.

### List or inspect jobs

```sh
curl --fail-with-body -H "Authorization: Bearer $ANIMATION_API_TOKEN" \
  http://127.0.0.1:4386/v1/jobs

curl --fail-with-body -H "Authorization: Bearer $ANIMATION_API_TOKEN" \
  http://127.0.0.1:4386/v1/jobs/JOB_ID
```

Job states are `queued`, `running`, `needs_review`, `completed`, `failed`, or `needs_attention`. A service restart converts an interrupted running stage to `needs_attention`; it is not blindly retried.

### Review an exact artifact revision

Read the artifact `name`, `sha256`, and `revision` from job status. Submit the exact current hash:

```sh
curl --fail-with-body -X POST \
  -H "Authorization: Bearer $ANIMATION_API_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"artifact":"inspect-reference.json","sha256":"EXACT_64_HEX_SHA256","decision":"approve"}' \
  http://127.0.0.1:4386/v1/jobs/JOB_ID/reviews
```

`decision` is `approve` or `reject`. A stale or incorrect hash returns 409. Approval is bound to the current SHA-256 and revision and stops applying when that artifact is replaced.

### Queue another stage

Free-stage example:

```sh
curl --fail-with-body -X POST \
  -H "Authorization: Bearer $ANIMATION_API_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"stage":"mirror","params":{"atlas":"atlas.png","manifest":"atlas-manifest.json","target_direction":"nw","target_image_id":"keeper-walk-nw-derived"}}' \
  http://127.0.0.1:4386/v1/jobs/JOB_ID/stages
```

The API requires current approvals for every source artifact before a dependent stage is queued. Accepted stage names are `inspect_reference`, `generate_facing`, `generate_video`, `extract_frames`, `remove_background`, `pack`, `mirror`, and `spatial_export`. Detailed pipeline parameter schemas are in `docs/PIPELINE.md`.

Paid-stage authorization is separate from `params`:

```json
{
  "stage": "generate_facing",
  "params": {
    "input": "reference.png",
    "prompt": "turn the character northeast"
  },
  "authorize_paid": true,
  "budget_cap_usd": 0.011
}
```

Budget or authorization fields inside `params` are rejected. The server must also have `ANIMATION_PAID_ENABLED=1`, and `budget_cap_usd` must not exceed `ANIMATION_MAX_STAGE_USD`. Submission POSTs are not blindly retried; ambiguous charged-stage submissions become `needs_attention`.

### Automatic source review and extraction

Submit the current recorded video hash and revision plus a frame policy to the dedicated endpoint. The allowed values are `"8"`, `"12"`, `"16"`, and `"native"`; the default is `"8"`. This endpoint, not the generic stage endpoint, creates the server-owned automatic-review queue record:

```sh
curl --fail-with-body -X POST \
  -H "Authorization: Bearer $ANIMATION_API_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"artifact":"video-output.mp4","sha256":"EXACT_64_HEX_SHA256","revision":1,"frame_policy":"8","authorize_paid_review":true,"budget_cap_usd":0.05}' \
  http://127.0.0.1:4386/v1/jobs/JOB_ID/automatic-review
```

The serial runner always performs local cutoff/static/candidate analysis first. A local hard failure records `rejected` and makes zero reviewer calls. A safe source with missing enablement, key, fresh metadata, token bounds, authorization, or cap records `needs_attention`; it never becomes approved by fallback. Only a successfully schema/provenance-validated result from exactly `google/gemini-3.8-flash` creates the typed `automatic_model_validated` approval bound to the source SHA-256 and revision.

Server-side preflight code may call `Runner.prepare_automatic_review_analysis(job_id, artifact_name)` once before queueing review. It creates a registered immutable analysis receipt bound to the exact source SHA-256/revision, analyzer recipe and production density policy. The review runner reuses only that server-owned receipt. Stale source/revision/recipe/policy bindings recompute safely, unregistered client-authored JSON is ignored, and corruption of a registered receipt fails closed. `tools/real_cold_e2e.py` uses this handoff so its budget preflight and review use the same candidate list without a second video analysis.

Local analysis rejects intervals with measured source-pose orientation drift, normalized loop-pose discontinuity, or incomplete motion return and retains ranked rejected alternatives for diagnosis. The reviewer selects the complete alternating cycle before export sampling. Compact policies then choose exactly 8, 12, or 16 distinct original native frames spread over that immutable interval; they preserve the interval duration and do not impose a minimum FPS. If the interval contains too few originals, the request fails rather than changing policy or filling frames.

An approved candidate is extracted with ffmpeg's exact native frame-index selector, using the validated start inclusive/end exclusive bounds. The optional backward-compatible `native-density-v2` policy retains the previous dense behavior. Every policy has a canonical hash in the job, automatic result, selection receipt, extraction receipt, and final atlas manifest; a prepared-analysis cache from another policy is not reused. Sampling never interpolates, duplicates, ping-pongs, or changes cycle duration. Reviewer evidence count remains independent from export count.

### Download an artifact or safe ZIP

```sh
curl --fail-with-body -H "Authorization: Bearer $ANIMATION_API_TOKEN" \
  -o inspect-reference.json \
  http://127.0.0.1:4386/v1/jobs/JOB_ID/artifacts/inspect-reference.json

curl --fail-with-body -H "Authorization: Bearer $ANIMATION_API_TOKEN" \
  -o job.zip \
  http://127.0.0.1:4386/v1/jobs/JOB_ID/download
```

Only artifact basenames recorded for that job are downloadable and included in ZIP files. Database files, source code, hidden service files, symlinks, arbitrary paths, and client URLs are not accepted as artifacts.

## Verification

Unit/API tests use an explicitly labelled injected fake pipeline:

```sh
.venv/bin/python -m pytest tests/test_api.py -q
```

All service tests:

```sh
.venv/bin/python -m pytest tests -q
```

### Reusable cached spatial export (private CLI)

`spatial_export.py` runs exact selected-frame extraction, content-addressed
cutout lookup, direct-from-master 160/80 normalization, atlas packing, three-loop
preview encoding, all-frame/multi-background verification and ZIP packaging from
one JSON job config. A new job changes only its config; no Python rewrite is
required:

```sh
.venv/bin/python spatial_export.py /absolute/path/to/job-config.json
```

The accepted replay configs and measured evidence are under
`review/fast-clean-pipeline/`. They deliberately say
`selection_mode: explicit_human_reviewed`: importing accepted cutouts proves the
spatial/cache path, not automatic selection and not a cold-provider SLA.
`timings.json` uses monotonic durations plus UTC boundaries and marks source
generation and CI as excluded. Cache entries bind the exact extracted-frame
SHA-256, removal preset and removal recipe; receipts and immutable cached PNGs
are hash-checked on every lookup. A changed source is a miss and corruption is a
hard failure.

The same implementation is available as the authenticated `spatial_export`
stage. An explicit selection is first recorded with
`POST /v1/jobs/{id}/selections`, then both the exact video revision and generated
`spatial-selection.json` must be approved. The stage accepts artifact basenames
and named server presets only; client filesystem paths, URLs and geometry are not
accepted. `automatic_model_validated` mode instead requires the current typed
automatic approval plus its bound extraction evidence. A cache miss fails closed
and makes no provider call; paid removal remains the separately authorized
`remove_background` stage.

Real isolated HTTP acceptance for this path:

```sh
.venv/bin/python tools/smoke_spatial_api.py --port 4393
```

This exercises bearer auth, job state, reviewed selection, the real spatial
stage, baseline-identical atlases, artifact download and nested ZIP integrity.

Real automatic-review HTTP smoke (isolated server on port 4389, server-side copies of the existing rejected 3-second and WAN videos, reviewer disabled, zero paid calls, restart persistence and authenticated downloads):

```sh
.venv/bin/python tools/smoke_automatic_review.py
```

The smoke report is written to `artifacts/automatic-review-http-smoke.json`. It explicitly sets `live_vlm_claimed:false`; mocked approval/extraction exists only in `tests/test_automatic_review_integration.py`.

Real Chromium UI smoke (starts and stops its own localhost server on port 4388, performs a real free upload/inspection, checks atlas frame progression and pause, and writes desktop/mobile screenshots):

```sh
.venv/bin/python tools/smoke_ui.py
```

Real Chromium source-option smoke (localhost port 4394, verifies 3s/480p defaults and captures a 10s/768p stage request before it reaches the server/provider; no generation or charge):

```sh
.venv/bin/python tools/smoke_source_options.py
```

Real HTTP smoke using the actual `pipeline.py` implementation, an accepted local reference, a temporary database/data directory, and no provider credential:

```sh
.venv/bin/python tools/smoke_api.py
```

The smoke harness first verifies that `127.0.0.1:4386` is free. It refuses to kill or replace another listener, starts only its own localhost server, applies request timeouts, performs upload → real `inspect_reference` → exact SHA/revision review → artifact/ZIP checks, and stops that server in `finally`. It never invokes a paid stage.

## systemd template

`deployment/animation-pipeline.service.template` is a template only. Copy it to an operator-controlled location, replace every `@@...@@` placeholder, create the environment file with mode 0600, and review paths/user permissions before installation. This repository does not install or enable a unit.
