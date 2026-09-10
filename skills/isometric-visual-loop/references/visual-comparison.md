# Execute an image comparison round

The image comparison format starts with acceptance-plan version 2. New complete
worlds use [version 3 production stages](production-flow.md), retaining this image
format and adding prerequisite checks. The comparison format extends the
existing plan and review files; do not create a competing project contract.
Version 1 remains readable for older tasks, but its acceptance result may report
zero `visualComparisons`. That is not evidence of this workflow.

## Protect a concrete target

Use the user's supplied image with its declared role: `style`, `layout`, or
`both`. If a project-specific target is needed, author or generate one within the
chosen technique and spending authorization, while retaining the original style
reference. It should depict an achievable game view with the intended projection,
pixel scale and camera, not a cinematic interpretation. Do not lower the target
to match an unsuccessful implementation. A target assembled retrospectively must
be labeled as such. If no visual target can be obtained, keep visual acceptance
unverified; do not fabricate an image review from the text brief.

For example, `game/acceptance-plan.json` for a small visual-only repair:

```json
{
  "version": 2,
  "root": "..",
  "inputRoots": ["game", "src"],
  "artChecks": [],
  "reviewMode": "independent",
  "requirements": [
    {"id":"terrain","domain":"visual","description":"Natural path and bank transitions with coherent pixel treatment and no dominant tile stamps","views":["ground-only"]}
  ],
  "comparisons": [
    {"id":"terrain-ground","requirements":["terrain"],"view":"ground-only","reference":"game/art/ground-target.png","role":"style","focus":"Compare grass/path interlocking edges, bank continuity, pixel clusters and repeated motifs. Different path layout is allowed."}
  ]
}
```

This example omits packed-art checks only to illustrate a task without packed
raster actors/overlays. Add those checks and motion/gameplay/performance requirements
when relevant. Each visual requirement/view must occur in a comparison. Several
requirements can share a comparison when they use the same view and reference.
All reference paths resolve from the plan's project root. Use static PNG/JPEG/WebP;
the tool decodes them and freezes their hashes with the plan. Camera, dimensions,
state and reference role must be intentional, not chosen to hide a defect.

Run `verify-world.py freeze PLAN BASELINE` before implementation, using the
commands in [acceptance](acceptance.md). Keep outputs outside `inputRoots`.

## Capture, assemble, actually inspect

After the scoped implementation, take a source snapshot, then capture the live
game at the declared views. `captures.json` maps comparison IDs to source images:

```json
{
  "terrain-ground": {
    "path": "ground-current.png",
    "captureNotes": "Live host, 960x640 viewport, fixed camera at zoom 1, optional props hidden, actor idle. No image edits."
  }
}
```

Image paths resolve beside `captures.json`. These must be actual current captures;
the tool can verify file contents but cannot prove how a screenshot was obtained.
For `layout`/`both`, reference, previous and current dimensions must match. Capture
again at the proper camera/viewport rather than stretching or silently cropping.
For `style`, differing dimensions/layouts are permitted and remain visible.

```sh
python skills/isometric-visual-loop/scripts/verify-world.py snapshot test-results/game/baseline.json test-results/game/candidate-1.json
python skills/isometric-visual-loop/scripts/verify-world.py compare test-results/game/baseline.json test-results/game/candidate-1.json test-results/game/captures.json --out test-results/game/round-1
```

The new folder contains `board.html`, `packet.json`, exact copies of the source
images, `review-request.md` and `review-template.json`. The packet preserves the
complete protected requirement descriptions, and the board shows the relevant
criteria beside each comparison. The self-contained board
shows reference, previous (when present) and current views. Shared zoom preserves
source pixels and aspect ratio. Drag a rectangle on either image to get
`[x,y,width,height]` in its original pixels; these coordinates locate observations.
Use close-up comparisons as separate protected views if the overview cannot show
the defect clearly. Inspect the full frame too; a selected region does not replace it.

Give a fresh authorized reviewer the original brief, comparison folder and request.
It must open the board or inspect the bundled images through a vision tool. Merely
reading filenames, hashes or the builder's explanation is not visual inspection.
If independent review is unavailable, declare `self` before freezing and disclose
it. Missing vision leaves the review unverified. Do not claim an independent
reviewer's identity based on a string in a JSON record.

## Localize differences and close the loop

The reviewer fills the existing verdicts plus the new `comparison` section, saves
the template as `review.json`, and gives every comparison a complete assessment:

```json
{
  "id": "terrain-ground",
  "status": "fail",
  "observations": [
    {"id":"path-fringe","status":"fail","currentRegion":[120,160,100,80],"referenceRegion":[80,100,140,90],"difference":"Current path has a uniform dark staircase rim; reference breaks the boundary with crisp grass/earth clusters.","repair":"Replace the repeated rim with shared irregular edge clusters and keep their pixel scale consistent across adjoining pieces."}
  ]
}
```

Coordinates above are illustrative, not a reusable finding. For `pass`, locate
the visibly matching quality in both images and describe it. For `unverified`,
explain what could not be observed; regions may be null. Every failure needs an
actionable repair. Complete the whole relevant scope, not only a short list of
favorite fixes. Inspect composition, material treatment, pixel density, transitions
and readability according to the reference role. Similar palette alone is insufficient.

Repair the actual host. Snapshot the new source and recapture, then assemble:

```sh
python skills/isometric-visual-loop/scripts/verify-world.py compare test-results/game/baseline.json test-results/game/candidate-2.json test-results/game/captures-2.json --previous test-results/game/round-1/review.json --out test-results/game/round-2
```

The next board includes the previous image and open findings. Reinspect each prior
finding using its same ID and mark its resolution `resolved`, `open` or `regressed`
with a reason, while adding any new defects. A resolution must agree with a fresh
observation. Keep earlier rounds; output folders cannot be overwritten. If a defect
persists across rounds, reconsider the asset or assembly approach instead of only
tuning colors. Do not change reference or scope to obtain a passing judgment.

If a packing/representation correction or additional comparison coverage requires
a new baseline, preserve the old baseline and record the precise change. Use a new
freeze and snapshot, then add `--rebaseline-note "Describe the correction or added coverage"`
to `compare --previous ...`. Requirements and review mode must remain identical.
Preserve every existing comparison definition and target hash; new comparisons
may add coverage. The board announces the change and retains
the old packet, images and every open finding. This permits a documented art-check
correction, not reduced asset/action coverage or a lower visual target. The reviewer
must assess that explanation and the complete current packed-art scope. Final
acceptance still checks all current frozen art specs; the tool does not infer
whether an art-threshold change was authorized or artistically justified.

When a new view exposes an area previously missing from the evidence, a resolution
may name its destination `comparison`. Retain the finding's ID and explain the
move in `reason`. The destination must share the original viewport, a protected
requirement and the same target image. Review the original comparison too; moving
a finding cannot remove coverage or silently close it.

Finally run `verify-world.py accept BASELINE CANDIDATE round-2/review.json`.
Unresolved visual observations block acceptance even if other verdicts say pass.
The tool validates image/reference hashes, candidate identity, comparison coverage,
source-pixel regions and previous finding resolutions. It does not call a vision
model, calculate beauty or authenticate judgments. A forged complete record is
outside its trust boundary. The coding agent owns the actual inspect–repair loop.

Still comparisons cannot approve motion or interaction: retain separate observed
clip playback, traversal and performance evidence under their existing requirements.

## Verify changes to this authoring tool

Run `python -m unittest discover -s skills/isometric-visual-loop/tests -p 'test_*.py'`
with Pillow installed. For the board, use an authoring installation of Playwright
and Chromium, serve a generated bundle locally, then run
`node skills/isometric-visual-loop/tests/comparison-board-browser.mjs BOARD_URL`.
Exercise a first round and a round with previous findings. The probe checks decoded
images, shared zoom, source-pixel regions, overlays, mobile layout and decode failure
labels. These checks validate the review tool; actual game quality needs its own review.
