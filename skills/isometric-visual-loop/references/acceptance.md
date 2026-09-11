# Packed-art and world acceptance gates

Use these gates for a new world or substantial visual production. For a focused
asset repair, scope the plan to the affected assets, clips and playable views.
They are authoring tools; nothing is added to scene JSON or the runtime API.

New complete worlds use acceptance-plan **version 3** with the
[production stages](production-flow.md). Version 3 adds mandatory prerequisite,
spatial-placement and rigid-binding checks to the image workflow below. Use the complete example below and pass
`--production-receipts DIR` to final `snapshot` and `accept`. Scene JSON versions
are independent of authoring-plan versions.

The script is `skills/isometric-visual-loop/scripts/verify-world.py`. Use Python
3.10+; decoded art and visual-comparison commands also need Pillow. With uv on Windows:

```sh
uv run --python 3.12 --with pillow python skills/isometric-visual-loop/scripts/verify-world.py --help
```

Below, `python` means that interpreter (or replace it with the uv prefix above).
These files and the tool travel with the npm package. Use its absolute script path
when running in a consumer's own application.

An inspected cutout or diamond frame may be up to 4096 pixels on a side and 1,048,576 pixels in
area. This permits a wide joined assembly while bounding per-frame analysis.
Cutouts still need transparent padding; pack an assembly's union bounds with
padding and adjust its anchor instead of setting a zero crop margin. A whole
strip must pass the same visible join and motion review as its smaller pieces.

## 1. Protect requirements and art checks before implementation

The agent prepares `acceptance-plan.json` beside the new host, deriving its
requirements from the one approved project contract. Add `packed-art.json` only
when raster assets are in scope; no second brief or manual completion ledger is needed. Separate visual,
motion, gameplay and performance requirements. Give concrete criteria: whole
silhouettes, stable feet in every used facing/action, joined flowing water,
readable player views and requested atmosphere. Do not reduce this to asset counts.
Keep motion requirements for every promised direction/action; static fallbacks
remain incomplete unless the user explicitly changes the scope.

Start from the complete [version 3 example](acceptance-plan.example.json). It
already includes all six production stages; do not splice together incompatible
version examples. The example IDs and values are illustrative, not requirements
for a new game. The agent derives descriptions, views, comparisons, layout scope
and rigid checks from the approved project contract and chosen technique. Remove
absent features and add every promised outcome before freezing.

Set `contract` to the project-relative approved brief (normally
`PROJECT_CONTRACT.md`). Freeze protects its bytes alongside the plan, art specs
and target images. This prevents using an old plan after the contract changes;
it does not understand prose or prove the agent translated every requirement.
Review that mapping once before implementation. Existing plans without this
optional field remain readable. Keep ongoing progress in receipts, not in the
frozen contract.

`root` resolves relative to the plan. `inputRoots` are paths inside that project
root; every file under them is hashed, including added/removed files. Include host
source, assets, relevant engine source or installed runtime files, and build/config
inputs that affect the delivered view. Avoid unrelated examples and dependencies.
Keep evidence outputs outside these roots. `artChecks: []` is only appropriate
when the task has no packed raster art. Select `reviewMode: "self"` only when an
independent reviewer is unavailable; disclose it instead of inventing independence.

For natural landscapes, include ground composition and transition criteria
for the actual material pairs; deliberate formal paving may use regular grids.
Use the [terrain evidence rubric](../../consistent-tileset-authoring/references/landscape-composition.md#terrain-acceptance-evidence)
for explicit observations. The tool enforces their records, not aesthetic judgment.
Version 2 requires a protected image comparison for every visual requirement/view.
Prepare the actual references before freezing; follow the
[image comparison round](visual-comparison.md) for capture, review and repair.
Version 1 plans remain readable for historical tasks and may have zero image
comparisons; they do not establish completion of the new visual workflow.

Example `packed-art.json`:

```json
{
  "version": 1,
  "manifest": "art/runtime.json",
  "groups": [
    {"id":"ranger-walk","kind":"cutout","clips":["hero.walk.ne","hero.walk.se","hero.walk.sw","hero.walk.nw"],"margin":1,"maxComponents":1,"minComponentPixels":2,"minDistinctFrames":2,"bounds":[18,28,38,48]},
    {"id":"ranger-idle","kind":"cutout","clips":["hero.idle.ne","hero.idle.se","hero.idle.sw","hero.idle.nw"],"margin":1,"maxComponents":1,"bounds":[18,28,38,48]},
    {"id":"river","kind":"diamond-overlay","clips":["river.flow"],"minDistinctFrames":2}
  ]
}
```

The manifest is either an AssetManifest or an object containing `assets`, such as
the directional packer's `runtime.json`. Image URLs must be local relative PNG
paths resolved against the manifest directory. Export the actual host manifest,
not a separately invented passing manifest. For document-relative runtime URLs,
rebase only those URLs to the same local image files; preserve crops, anchors and
clips. Check all frames used by the actor's
real clips, including idle and host-selected custom actions. `textures` can list
static texture IDs. Duplicate pixels do not satisfy `minDistinctFrames`.

`bounds` is `[minWidth,minHeight,maxWidth,maxHeight]` of visible pixels. Set it from
the intended actor proportions, not from already contaminated bounding boxes.
`alphaThreshold` defaults to 16. `maxComponents` counts 8-connected alpha islands
of at least `minComponentPixels` (default 2). Separate effects or floating parts
may need a larger declared limit: document the reason in the brief. This heuristic
does not identify anatomy; a connected neighbor fragment can escape it.

`diamond-overlay` requires transparency outside the frame-centered tile diamond,
using pixel centers. Use this only for sprite layers meant to occupy that diamond.
Terrain materials are clipped by the terrain renderer and may remain rectangular.
Strip overlays, waterfall faces and intentionally overhanging effects need their
own measured geometry and rendered acceptance; do not mislabel them as diamonds.

`surface` is for an intentionally edge-opaque terrain plate or its bounded chunks.
Its frames may be up to 8192 pixels per side and 16,000,000 pixels. Surface frames
use explicit content-only `frame` rectangles and `{"x":0,"y":0}` anchors; no
transparent crop margin is required. A composed surface declares unique `textures`,
and `composition` with a local RGBA PNG `reference` and displayed `[x,y]` source
`origin`; its texture placements come from the manifest's `placements` dictionary,
keyed by texture ID. Placements are signed reference content coordinates, including
the origin, so the checker subtracts `origin` before fitting chunks to the reference.
Each group selects its own pieces; other groups may share the manifest. The
checker rejects missing or duplicate selected chunks, holes, overlap, out-of-bounds
placements, and every RGBA reconstruction mismatch, including RGB under transparent
pixels. An optional static PNG grayscale (`L`/`1`) `coverageMask` is allowed only with
a composition and its luminance bytes must match the reference alpha exactly; it is a
diagnostic, not collision topology.
The reference and mask are protected inputs. Preview inspection shows both individual
chunks and the composed result with origin and mask/failure notes.

Freeze the plan and art thresholds before generating the full pack. Referenced
manifests/images may be produced later; the plan and art-check spec must exist.

```sh
python skills/isometric-visual-loop/scripts/verify-world.py freeze game/acceptance-plan.json test-results/my-game/baseline.json
```

Existing receipts are never overwritten. If the user changes scope or calibration
establishes a necessary correction, record what changed and why, retain the old
baseline, and create a new one. Do not weaken checks simply to accept failures.
Freezing an already built host is retrospective verification; say so.

## 2. Inspect the packed result before expanding

When later planned asset families do not exist yet, inspect named groups from
the same protected spec with `--groups GROUP_ID [GROUP_ID ...]`. For example,
select the actor's existing idle/walk groups during its initial calibration.
The report and preview explicitly label this a calibration subset. Keep the
complete plan and thresholds unchanged; `accept` always inspects every planned
group and cannot accept a subset receipt. Add missing assets as production advances.

```sh
python skills/isometric-visual-loop/scripts/verify-world.py inspect game/packed-art.json --out test-results/my-game/art-round-1
```

Exit 1 means structural failure. Decoded art checks produce `report.json` and
a self-contained `preview.html`, including failed findings. Missing inputs or
invalid specifications can stop before a preview is written. Open the preview in a browser:
check decoding, every selected frame, the declared anchor, shared scale, and every
clip. Playback respects fps and loop flags (runtime defaults: 8 fps, looping).
Use Replay clips to restart one-shot actions; it also works while paused.
Pause to inspect truncation, neighboring fragments and root/identity drift.
View against dark and checker backgrounds. Then inspect the actor and a joined
animated patch in the actual game's rendering path at desktop/mobile sizes.

Reject bad extraction and missing poses before populating the world. Derive
explicit crop windows from actual pixels; a requested equal grid does not prove
one exists. The tool does not repair or normalize images. A structural PASS leaves
visual and motion acceptance open. Fixed anchors alone do not prove fixed feet.

## 3. Capture a candidate, then obtain complete reviews

After implementation/repairs and structural checks:

```sh
python skills/isometric-visual-loop/scripts/verify-world.py snapshot test-results/my-game/baseline.json test-results/my-game/candidate-1.json
```

Capture the candidate's relevant views, gameplay and complete motion cycles.
Run `verify-world.py compare` with the current captures to create a comparison
board and review template. After a repair, supply `--previous` with the preceding
review so the next critic sees both images and all prior unresolved findings.
Give the reviewer the original brief/reference role, protected requirements,
packed preview, live captures and prior open defects. Preserve a complete defect
list; selecting three repairs for a round does not limit what can fail. A reviewer
must issue `pass`, `fail` or `unverified` for each requirement. LANDED only describes
a repair; it cannot substitute for a fresh whole-scope verdict.

Example verdict fragment (include **every** protected requirement in the generated
review template, retaining its `comparison` section for version 2):

```json
{
  "candidateSha256": "SHA256_OF_CANDIDATE_JSON",
  "reviewMode": "independent",
  "verdicts": [
    {"id":"ranger-walk","status":"pass","reviewer":"review-session-id","notes":"Observed all four cycles and wrap; whole body, no fragments, stable feet and correct direction at both sizes.","evidence":[
      {"path":"ranger-desktop.webm","sha256":"SHA256_OF_MEDIA","kind":"motion","view":"desktop"},
      {"path":"ranger-mobile.webm","sha256":"SHA256_OF_MEDIA","kind":"motion","view":"mobile"}
    ]}
  ]
}
```

Evidence paths resolve against the review JSON. `image` accepts PNG/JPEG/WebP;
`motion` accepts WebM/MP4/GIF; `measurement` accepts JSON/text. Motion requirements
need motion media for every declared view. Still captures and changing frame IDs
cannot approve a motion requirement. Review notes must describe actually observed
quality; attaching an unwatched video is not a review. Performance needs measurements.
Hash files with Python `hashlib.sha256(Path(path).read_bytes()).hexdigest()` or an
equivalent local SHA-256 tool. Include all required views in every relevant verdict.

To attach a newly captured receipt without editing an existing review, use:

```sh
python skills/isometric-visual-loop/scripts/verify-world.py attach-evidence review-1.json --baseline test-results/my-game/baseline.json --candidate test-results/my-game/candidate-1.json --requirement ranger-walk --view desktop --file ranger-desktop.webm --out review-1-with-evidence.json
```

The command checks the protected requirement/view, infers `image`, `motion`, or
`measurement` from a supported file extension, decodes images (and GIFs) or parses
JSON measurements, hashes the actual file, verifies that the candidate and review bind
to that baseline, and writes a new review only beside the original review (so existing
relative evidence paths remain stable). It preserves
comparison fields and other verdicts, replaces the matching path/view evidence, and
sets the affected verdict to `unverified`; it never creates a pass or recaptures media.

```sh
python skills/isometric-visual-loop/scripts/verify-world.py accept test-results/my-game/baseline.json test-results/my-game/candidate-1.json test-results/my-game/review-1.json
```

The command reruns decoded art checks, verifies frozen requirements/thresholds,
checks source and evidence hashes and rejects missing/failed/unverified verdicts,
omitted views and wrong evidence types. Changes to source, art, manifest, thresholds
or evidence invalidate the corresponding records. Capture/review a new candidate
after repairs; keep prior failures.

This is a required completion command for the applicable workflow, not a security
boundary against an agent rewriting its own records. It does not authenticate a
reviewer's identity, understand media content or prove beauty. `npm run check` and
`npm run build` remain technical checks; they do not imply world acceptance. Report
those verdicts separately and do not call an unaccepted world complete.

## Tool regressions

```sh
uv run --python 3.12 --with pillow python -m unittest discover -s skills/isometric-visual-loop/tests -v
```

Synthetic tests cover neighboring fragments, crop-edge contact, opaque rectangular
overlays, repeated-pixel animation, stale inputs/evidence, missing views, still-only
motion reviews and altered requirements. They do not certify any bundled game's art.
