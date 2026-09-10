# Packed-art and world acceptance gates

Use these gates for a new world or substantial visual production. For a focused
asset repair, scope the plan to the affected assets, clips and playable views.
They are authoring tools; nothing is added to scene JSON or the runtime API.

New complete worlds use acceptance-plan **version 3** with the
[production stages](production-flow.md). Version 3 adds mandatory prerequisite,
spatial-placement and rigid-binding checks to the image workflow below. The
version 2 example here documents the compatible image-comparison format; add its
protected `production` section and set `version` to 3 for a new world. Pass
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

An inspected frame may be up to 4096 pixels on a side and 1,048,576 pixels in
area. This permits a wide joined assembly while bounding per-frame analysis.
Cutouts still need transparent padding; pack an assembly's union bounds with
padding and adjust its anchor instead of setting a zero crop margin. A whole
strip must pass the same visible join and motion review as its smaller pieces.

## 1. Protect requirements and art checks before implementation

Keep `acceptance-plan.json` and `packed-art.json` beside the new host. Derive the
requirements from the user's brief and the approved proposal. Separate visual,
motion, gameplay and performance requirements. Give concrete criteria: whole
silhouettes, stable feet in every used facing/action, joined flowing water,
readable player views and requested atmosphere. Do not reduce this to asset counts.
Keep motion requirements for every promised direction/action; static fallbacks
remain incomplete unless the user explicitly changes the scope.

Example `game/acceptance-plan.json` (illustrative host; adapt IDs, roots and views):

```json
{
  "version": 2,
  "root": "..",
  "inputRoots": ["game", "src"],
  "artChecks": ["game/packed-art.json"],
  "reviewMode": "independent",
  "requirements": [
    {"id":"world-style","domain":"visual","description":"Brief's palette, terrain treatment, density and player readability at game scale","views":["desktop","mobile"]},
    {"id":"ground-composition","domain":"visual","description":"Natural ground reads as continuous regions; no dominant repeated diamonds, mirrored motifs or per-cell color checkerboard","views":["ground-only-playing-zoom","ground-only-overview"]},
    {"id":"ground-transitions","domain":"visual","description":"Path/grass and bank boundaries remain continuous through bends and junctions with consistent pixel treatment and readable traversal","views":["transition-closeup","desktop","mobile"]},
    {"id":"ranger-walk","domain":"motion","description":"Whole silhouette, stable root and correct facing throughout all four walking cycles and their wraps","views":["desktop","mobile"]},
    {"id":"river","domain":"motion","description":"Flow follows the channel, joins remain covered and pause freezes it","views":["desktop"]},
    {"id":"crossing","domain":"gameplay","description":"Walk across and back; reject rail and water entry","views":["desktop","mobile"]},
    {"id":"timing","domain":"performance","description":"Record median/p95, renderer and blank baseline; assess against the brief","views":["desktop"]}
  ],
  "comparisons": [
    {"id":"style-desktop","requirements":["world-style"],"view":"desktop","reference":"game/art/target.png","role":"style","focus":"Shared pixel treatment, materials, hierarchy and player readability"},
    {"id":"style-mobile","requirements":["world-style"],"view":"mobile","reference":"game/art/target.png","role":"style","focus":"Style and readability at the mobile playing scale"},
    {"id":"ground-playing","requirements":["ground-composition"],"view":"ground-only-playing-zoom","reference":"game/art/ground-target.png","role":"style","focus":"Continuous ground without dominant tile stamps"},
    {"id":"ground-overview","requirements":["ground-composition"],"view":"ground-only-overview","reference":"game/art/ground-target.png","role":"style","focus":"Variation across cells and coherent larger regions"},
    {"id":"edges-close","requirements":["ground-transitions"],"view":"transition-closeup","reference":"game/art/edge-target.png","role":"style","focus":"Interlocking material edges with shared pixel density"},
    {"id":"edges-desktop","requirements":["ground-transitions"],"view":"desktop","reference":"game/art/ground-target.png","role":"style","focus":"Continuous path and bank boundaries at playing zoom"},
    {"id":"edges-mobile","requirements":["ground-transitions"],"view":"mobile","reference":"game/art/ground-target.png","role":"style","focus":"Readable transitions and paths at mobile scale"}
  ]
}
```

`root` resolves relative to the plan. `inputRoots` are paths inside that project
root; every file under them is hashed, including added/removed files. Include host
source, assets, relevant engine source or installed runtime files, and build/config
inputs that affect the delivered view. Avoid unrelated examples and dependencies.
Keep evidence outputs outside these roots. `artChecks: []` is only appropriate
when the task has no packed raster art. Select `reviewMode: "self"` only when an
independent reviewer is unavailable; disclose it instead of inventing independence.

The ground requirements illustrate a natural-landscape brief. Adapt them to actual
material pairs and intended style; deliberate formal paving may use regular grids.
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
