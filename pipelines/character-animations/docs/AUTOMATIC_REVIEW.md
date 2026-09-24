# Automatic animation review core

`animation_review.py` is the bounded reviewer core. It is wired into the authenticated API, durable SQLite store, serial runner, and UI as the `automatic_review` source-selection stage. Existing manual reviews remain usable, and downstream frame/alpha/atlas review gates remain in force.

## Exact review model

The configured review model is exactly `google/gemini-3.8-flash` through OpenRouter. There is no DeepSeek fallback, Gemini 3 alias, or silent substitute. OpenRouter routing is fixed to:

- `allow_fallbacks: false`
- `require_parameters: true`
- `data_collection: deny`

This review model is unrelated to the existing WaveSpeed generative preset `gemini-omni-video-3s-v1` (`google/gemini-omni-1.1-flash/image-to-video`). That generation preset remains unchanged.

A live read of `https://openrouter.ai/api/v1/models` on 2026-09-20 recorded the exact model with `text`, `image`, `video`, `file`, and `audio` input modalities and text output. The returned token prices were USD 0.00000075/prompt token and USD 0.00000375/completion token. These are a metadata snapshot, not a fixed run quote. Evidence is in `artifacts/review-candidates/openrouter-model-metadata.json`. Fetch and verify fresh exact-model capability and pricing metadata before any future paid request.

## Local candidate analysis

```python
analysis = analyze_candidates(
    workdir,
    "source.mp4",
    sample_fps=12,
    minimum_loop_seconds=0.5,
    maximum_loop_seconds=2.5,
)
```

The input must be one regular, non-symlink video basename confined to `workdir`. URLs, absolute paths, traversal, unsupported extensions, files over 20 MiB, videos over 12 seconds, dimensions over 1920 pixels, and excessive decoded-pixel workloads are rejected. `ffprobe` and one bounded `ffmpeg` decode are run without a shell and with timeouts.

The analyzer records the source SHA-256, byte count, native FPS, native frame count, sampled index, timestamp, and mapped native source frame index. Sample index and native index are deliberately distinct: `source_frame_index = round(timestamp_seconds * native_fps)`. Native video/VLM sampling is never described as frame-accurate.

The reusable server preparation interface is `Runner.prepare_automatic_review_analysis(job_id, artifact_name)`. Its `animation-automatic-analysis-cache-v1` receipt binds the job-owned source basename, SHA-256 and artifact revision; exact 12 FPS / 0.5..2.5 second analyzer recipe; complete canonical analysis hash; and current production density-policy hash. Only an artifact registered by the server as `automatic_analysis_preparation` is eligible for reuse. The review stage verifies the stored artifact hash and all inner bindings before using it. Stale bindings trigger a fresh production analysis, while malformed or hash-corrupt registered cache data fails closed. The automatic-review HTTP schema has no candidate-analysis field, so client-crafted candidate JSON cannot enter this path.

Candidates are ranked using endpoint image difference, foreground displacement, neighboring horizontal motion-direction discontinuity, and internal motion. Scores are heuristic suggestions only. A static source, a repeatedly edge-touching foreground, or no non-static interval is rejected locally. Local hard failures cannot be overridden by a model response.

The foreground detector assumes a comparatively stable corner background. Complex scenes can produce false positives or false negatives, so a non-rejected local result is not visual approval.

## Multimodal request

```python
request = build_review_request(workdir, "source.mp4", analysis)
```

The request contains:

- the exact short local video as a base64 `video_url` data URI;
- no client-provided remote URL;
- machine features and candidate provenance;
- numbered PNG samples immediately around candidate start/end boundaries;
- exact sample indices, timestamps, mapped native frame indices, and source SHA-256 on every frame label;
- a strict JSON Schema response format covering decision, candidate bounds, direction/identity/framing/clipping/static/seam/motion issues, and rejection reason.

The prompt treats visual/media content as untrusted data and grants it no tools or code execution. The video gives temporal context; numbered boundary frames remain the exact index/timestamp evidence.

## Response validation

`validate_review_result(analysis, response)` rejects extra/missing fields, invalid JSON, the wrong model, stale source hashes, unknown candidate IDs, changed indices/timestamps, malformed issues, and invalid decisions. An approval must select an existing candidate unless a local hard failure already forces rejection. Model confidence is retained only as:

```json
{"value": 0.8, "calibrated": false}
```

It is not used as calibrated probability or as a gate bypass.

## Paid submission contract

`submit_review(...)` is fail-closed. It performs no request unless all of the following are supplied explicitly:

- `paid_enabled=True`;
- `OPENROUTER_API_KEY` or an explicit key argument;
- a per-call USD cap;
- bounded declared maximum input tokens and completion tokens;
- freshly fetched metadata for exactly `google/gemini-3.8-flash` with video/image/text and structured-output support;
- token-bound price estimate within the cap.

Missing configuration, HTTP/provider errors, oversized responses, malformed envelopes, invalid JSON, or provenance/schema failures return `needs_attention`, never approval. Submission is one-shot and not retried. The declared token calculation is an estimate, not a provider-side fixed-price guarantee.

Only injected mocked transports are exercised by tests. No paid OpenRouter inference was run for this work. The API integration additionally requires a fresh (at most 24 hours old) exact-model metadata file from the OpenRouter models endpoint and separate `ANIMATION_REVIEW_*` server policy. Missing configuration persists `needs_attention` rather than falling back.

When OpenRouter returns token usage and an actual cost, both are persisted. The declared maximum token-price calculation is labelled as a quote/estimate; absent provider cost remains `null` with `actual_cost_known:false`.

## Free replay

```sh
.venv/bin/python tools/replay_review_candidates.py --replace
```

The replay copies two bounded local videos into `artifacts/review-candidates/`, runs real `ffprobe`/`ffmpeg`/Pillow candidate analysis, builds the exact request locally, and stores hashed boundary-frame evidence plus a request manifest. It never invokes provider inference.

Results:

- rejected 3-second Gemini Omni footage: hard rejection `foreground_touches_frame_edge`, matching the recorded clipped-body review;
- existing WAN footage: five heuristic candidates, with the top interval at sampled indices 11..30 (0.916667..2.5 seconds, mapped native frame indices 28..75).

The WAN source previously had an accepted early window for bounded loop suitability. This replay does not claim the whole source, its newly ranked candidate, or any provider inference was visually approved.

## Integrated stage and remaining blocked work

`POST /v1/jobs/{job_id}/automatic-review` binds the request to a recorded video basename, SHA-256 and revision. The durable queue never retries an interrupted paid review after restart. Local hard failures stop before submission. Only a validated approval from exactly `google/gemini-3.8-flash` creates a typed automatic receipt; arbitrary client flags and manual review payloads cannot create one.

The validated candidate's mapped native start-inclusive/end-exclusive indices drive exact native-index ffmpeg extraction. Generated `selected-frame-*.png` files and `extract-frames.json` return to `needs_review`. Background removal still requires actual alpha validation and paid authorization. Neutral `animation-pipeline-atlas-v1` packing still requires approved inputs and enforces its existing alpha/canvas criteria.

Still blocked/unclaimed:

- no live OpenRouter VLM inference was authorized or executed;
- no automatic background-removal approval;
- no automatic atlas-quality approval;
- no claim that the full generation-to-atlas chain is unattended.

Free real HTTP evidence is in `artifacts/automatic-review-http-smoke.json`: the rejected 3-second clip hard-fails with zero paid calls, WAN footage persists five candidates as `needs_attention` while the reviewer is disabled, state survives an isolated server restart, and recorded files download only through bearer-authenticated endpoints.
