# Terrain authoring tooling audit

Status: the bounded offline preparer, surface inspector, evidence attachment and
motion measurement helper are implemented. The findings below preserve the initial
audit; automatic local deformation remains outside the implemented scope.
Date: 2026-09-11. Scope: lessons from the accepted Quellbrunn ground experiment,
with equal support for authored, supplied, procedural and generated artwork.

## Findings

The existing skills already separate provider from production technique and allow
both compatible terrain catalogs and composed ground patches. The missing piece
is portable execution tooling, not another mandatory artistic contract or review loop.
No engine API change is justified by this experiment.

| Evidence in current code | Consequence |
| --- | --- |
| `skills/game-asset-generation/SKILL.md:15-45` preserves technique/provider/budget and permits mixed production by asset family. `skills/consistent-tileset-authoring/SKILL.md:24-29` permits positioned crops without a 47-mask catalog. | Preserve these choices. Do not promote the last successful method to a universal default. |
| `skills/consistent-tileset-authoring/references/landscape-composition.md:47-63` already describes transition tiles and composed patches. | Add an executable optional recipe here; avoid repeating the entire production policy. |
| `examples/quellbrunn/terrain-trial/prepare.mjs:1-22` requires Chromium, port 4202, a host module, fixed dimensions and a specific river. | Separate a host geometry export from offline pixel preparation. Merely copying this script into a skill would retain hidden example dependencies. |
| `examples/quellbrunn/terrain-trial/analyze-registration.py:18-54` classifies colors and fills mask holes; its sampled river assumes one span per column. | Accept explicit masks/control points. Color classification or segmentation may propose masks but must not silently define topology or collision. Islands, forks and other palettes are outside this detector's assumptions. |
| `examples/quellbrunn/terrain-trial/prepare.mjs:19-22` remaps one world axis between two riverbanks and clamps source coordinates. | This is a restricted correction, not a general 2D registration solution. Missing/reversed samples and out-of-bounds samples need explicit failure or an explicitly chosen border policy. |
| `examples/quellbrunn/generated-ground.ts:9-15` loads all slices and immediately reconstructs one canvas. | Positioned slices have no demonstrated runtime advantage here. Offer a single plate; use chunks when a host actually needs them. |
| `skills/isometric-visual-loop/scripts/verify-world.py:115-157` allows only cutouts/diamonds and at most 1,048,576 pixels per frame. | A legitimate opaque terrain patch is tested as a truncated sprite; the current full plate exceeds the frame budget. Use a distinct surface role with bounded resources instead of padding artwork just to satisfy a cutout check. |
| `skills/isometric-visual-loop/scripts/visual_compare.py:259-285` already builds review templates; `verify-world.py:310-327` validates typed evidence. | Extend this existing path to attach hashed evidence. Do not build another review system. The trial required a repair for invented evidence kind names. |

## Local feasibility probe

`test-results/terrain-tooling-audit/probe.py` read the existing 1536x1024 registered
PNG without changing it. Pillow decoded it in approximately 0.017 seconds and
cropped/reassembled/compared 24 pieces in approximately 0.006 seconds in memory.
Every RGBA byte matched. No browser or game server was involved.

This is one local warm-environment probe, not an end-to-end benchmark. It excludes
registration, PNG encoding/export, generation, browser integration and visual review.
The useful result is feasibility of headless deterministic processing, not a
claimed speed multiplier. The saved `probe.json` also reproduces the existing
full-plate size rejection and opaque-patch cutout-margin finding.

## Recommended implementation order

### 1. Correct the asset role and add a small offline preparer

Owner: `skills/consistent-tileset-authoring/scripts/prepare-ground.py`, with neutral
synthetic tests under that skill. `verify-world.py` now includes a bounded surface
role. See the [implemented recipe](../skills/consistent-tileset-authoring/references/composed-ground.md).

Initial input recipe: source PNG; optional same-sized coverage/moving-region masks;
explicit image origin and intended sampling; optional validated affine matrix;
output mode `plate` or `chunks`; chunk dimensions and gutter policy when relevant.
This is tool configuration derived from the existing project brief, not a second
user approval contract. Authored and supplied images are equally valid sources.

Outputs: prepared image or chunks, existing-format texture manifest plus positioned
placement data, input/recipe/tool hashes, dimensions, actual processing timings,
and exact reconstruction/coverage measurements. Record provenance supplied by the
caller rather than inventing a generation provider. Preserve source files; use a
new output directory and publish a manifest only after all outputs validate.

Scope the first implementation to aligned inputs and explicit affine transforms.
An optional affine fit from supplied landmark pairs can report residuals; it must
reject degenerate data. Fitting outer corners alone does not certify interior
boundaries. Local river correction remains a host adapter until a broader mapping
contract has independent examples and tests. Do not infer a warp from RGB colors.

The surface inspector should allow intentional edge contact, enforce dimensions,
frame bounds and resource limits, and check supplied coverage masks. A composed
chunk check additionally reconstructs the declared image and rejects missing,
duplicated, overlapping or misplaced pieces. Preserve existing cutout margins and
diamond restrictions. Resource caps remain explicit; do not remove them globally.
Exact recomposition verifies extraction, not material coherence or registration.

The host exports layout, masks and contact points from its actual geometry. A
portable consumer must not import an example's `world.ts`, use a fixed server port,
or derive collision from the prepared image. Start with Pillow, already used by
the authoring checks. Additional numerical dependencies need a concrete operation.

### 2. Remove evidence bookkeeping and strengthen motion measurements

Extend the existing comparison/verification commands to attach files by requirement
and view, infer supported evidence kinds, compute hashes, and leave judgments
`unverified`. Diagnose all invalid evidence entries with their requirement/view/path.
Do not have a helper mark visual work passed or silently refresh stale captures.

Add an offline motion measurement helper under `animated-environments` only for
provided timed frames, declared moving/fixed masks and a period. It should emit
an inspection board and separate exact pixel differences, thresholded differences,
stationary-region drift, and sampling coverage. Browser capture remains a host
adapter using actual simulation state; do not impose a new engine diagnostic API.

The trial's `motion-report.py` counts differences greater than 8, so a reported
zero is not by itself proof of byte equality. Keep exact and perceptual-tolerance
metrics separately named. Motion samples and a matching endpoint do not prove
natural flow, continuous playback, correct speed or an invisible loop seam.

### 3. Patch documentation around working tools

| File / insertion point | Minimal change |
| --- | --- |
| `skills/consistent-tileset-authoring/SKILL.md`, composed-crop choice | Link the optional tool recipe; distinguish a whole plate, positioned chunks and reusable transition tiles. |
| New `skills/consistent-tileset-authoring/references/composed-ground.md` | Self-contained neutral inputs, commands, output meanings and rejected cases. No trial artwork, game names, hardcoded river or historical-report links. |
| `skills/consistent-tileset-authoring/references/landscape-composition.md`, implementation choices | Link the recipe after the existing composed-patch option. Preserve both generated and non-generated sources. |
| `skills/isometric-visual-loop/references/acceptance.md` | Explain surface-role checks and evidence attachment once implemented; retain visual judgment and freshness boundaries. |
| `skills/animated-environments/references/loop-recipes.md` | Optional masked moving material recipe with exact/tolerant measurement distinctions and topology limits. |
| `skills/game-asset-generation/SKILL.md:29` | Clarify that exact geometry does not prescribe code-painted appearance; link layout-guided image generation only when selected. |
| `docs/ART_PIPELINE.md:10-14` | Make the two terrain assembly choices visible before mask/catalog instructions. |
| `skills/README.md`, task combinations | One optional composed-ground example that points to its owning recipe. |

The root README, project-brief structure and production stages need no new mandatory
process. Keep historical findings in this document, outside skills. Runtime code
and unrelated examples remain outside the implementation scope. Files under
`skills/` already ship in the package; `authoring/` is not in the current package
file list. Do not make a packaged skill require the development checkout's SAM
service scripts. Segmentation can remain an optional external source of masks.

## Acceptance for the proposed tooling

- Identity and known affine transformations; reject singular/nonfinite transforms,
  incompatible mask dimensions, invalid crops and undeclared out-of-bounds sampling.
- Irregular image dimensions, partial edge chunks, nonzero origins, alpha holes,
  missing/duplicate/overlapping chunks and explicit gutter behavior.
- Reconstruction compares every RGBA channel, including RGB under unchanged alpha;
  changing one pixel must fail exact reconstruction.
- A legitimate opaque surface passes its role while a truncated cutout still fails;
  a surface's requested coverage mismatch remains visible and fails its declared check.
- Output hashes repeat for identical inputs; malformed recipes and interrupted work
  cannot leave an apparently complete manifest. Changed inputs invalidate dependent evidence.
- Evidence attachments preserve requirement/view mapping and never synthesize passes.
  Motion tests distinguish frozen sequences, small pixel changes, fixed-bank drift,
  missing timestamps, a discontinuous wrap and a verified exact endpoint match.
- Inspect the new surface preview in the browser and run one affected host journey.
  Use synthetic fixtures for portable tests; an optional trial replay may use this
  existing host but must not become a dependency of copied skills.

Measure future efficiency as preparation time, manual setup steps, failed reruns
and end-to-end elapsed time separately. Reuse the existing dependency receipts;
do not add a second cache or workflow scheduler without a demonstrated need.

## Executed implementation checks

- Six grouped preparer tests include strict input handling, affine bounds, masks,
  irregular chunks, exact RGBA reconstruction, deterministic outputs and direct
  interoperability with the surface inspector.
- The 44-test visual-loop suite covers existing gates and new surface/evidence
  behavior; the 23 existing art-calibration tests also pass.
- Six motion-helper tests distinguish thresholded/exact differences, frozen
  sequences, fixed-region drift, sparse sampling, invalid masks and period endpoints.
- Chromium inspected valid and deliberately damaged neutral compositions at desktop
  and mobile sizes, including actual assembly, source origin, shared zoom, mask and
  reference toggles, failure labels and broken-image reporting.
- An optional replay processed a copy of the existing 1536x1024 registered ground
  as a single plate and as 36 irregular chunks; both passed the new inspector and
  left the original image unchanged. Slices remain positioned map pieces.
- Both existing village browser journeys passed 25 targets each, water rejection,
  pixel-stable pause and exact A/B return; fresh records were kept separately from
  the previous acceptance evidence.
- The motion helper measured 89 retained desktop captures over 22 seconds. Its
  selected 3200 water pixels change, its selected 225 bank pixels remain fixed,
  and both selections match exactly at zero/period. This is limited sampled
  evidence, not a new whole-world or whole-channel acceptance claim.

Evidence is under `test-results/terrain-tools/` and stays outside shipped skills.
No engine API, runtime host behavior, art provider or paid generation was changed.
