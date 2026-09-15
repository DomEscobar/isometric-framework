# Video-derived sprite frames

Use this optional route when an existing or generated video supplies useful
directional motion. Authored poses and generated sheets remain alternatives.
Extraction is repeatable; it cannot make incorrect anatomy or movement correct.

## Choose inputs that simplify extraction

Start with an approved character image in the required facing. A rear walk needs
a rear-facing reference; a direction word does not reliably override a conflicting
image. Reuse existing views. For generation and provider inputs, follow
[game asset generation](../../game-asset-generation/SKILL.md).

Prefer one full-body character, fixed camera, stable scale and a stationary root.
Choose a uniform background color absent from the character, including equipment
and outlines. Cyan, green and magenta are options, not universal defaults. Avoid
ground shadows when they are not wanted in the actor sprite. Compression,
gradients, color spill and painted checkerboards complicate masking.

A compatible motion video can guide pose order and rhythm. Assign reference roles:
the character image controls identity and facing; the motion guide controls
movement. Check camera and proportions agree. A four-pose held-frame guide supplies
four poses, not accurate authored intermediate motion. Do not assume the generated
video preserves its phase timestamps or loop length.

Example motion prompt, adapted to the character and selected key color:

> The reference image supplies the character's identity and rear three-quarter
> facing. Keep this facing toward the upper-right throughout a steady walk in
> place. Full body visible, fixed elevated isometric camera and constant scale.
> Alternate the leading legs and opposing arm swings. Preserve natural body bob
> around a stationary root. Uniform cyan background, distinct from the character,
> with no ground shadow or other objects. Begin already walking and maintain the
> same pace throughout.

When supplying a motion video, add its role and intended rhythm. Inspect the output
instead of treating requests as guarantees. Check cost before generation; preserve
the prediction ID and resume existing jobs after interruption, without resubmitting.

## Prepare and export

The offline [extractor](../scripts/extract-video.py) needs Python 3.12+, Pillow,
and `ffmpeg` / `ffprobe` on PATH. These are authoring dependencies, not runtime
dependencies. Example commands from the framework root:

```sh
uv run --python 3.12 --with "Pillow==11.3.0" python -B skills/directional-sprite-authoring/scripts/extract-video.py prepare art/walk-source.mp4 --key "#00ffff" --tolerance 48 --out art/walk-review
```

Use a new output directory. Preparation preserves a local source copy, decodes
without forcing a frame rate, and records indices, actual timestamps and hashes.
It creates numbered boards, an inspection preview and `extraction.json`. Crop and
cycle suggestions need review; no cycle or direction is automatically approved.
Omit `--key` to preserve real alpha; an opaque source still needs a reviewed mask.

Inspect masks over contrasting backgrounds, including enclosed gaps and equipment.
The key tolerance is a per-channel RGB distance, not semantic segmentation. Wider
tolerance can erase subject colors. If colors overlap or the background is complex,
use a separately reviewed cutout workflow rather than hiding damage with tolerance.

Edit the generated recipe, keeping its preparation hashes intact. Set the shared
`crop`, reviewed `mask`, explicit `selection`, and `clip` fields. For example,
**only when these source indices and timing have actually been reviewed**:

```json
"selection": {"indices": [0, 3, 6, 9, 12, 15, 18, 21], "fps": 8},
"clip": {
  "imageId": "ranger", "action": "walk", "direction": "ne", "loop": true,
  "anchor": {"x": 0.5, "y": 0.9}
}
```

These are fields in the generated JSON, not a standalone file. Replace the anchor
with measured contact coordinates divided by cropped cell dimensions. Do not
anchor raised feet independently. The recipe is extraction data, not another
project contract or proof of visual acceptance.

Find a full gait cycle between equivalent contacts of the same anatomical leg;
exclude the repeated endpoint. Sample approximately uniform times using recorded
timestamps, not an assumed 24 FPS. The runtime uses one FPS per clip; nonuniform
selections require deliberate retiming or repeated frame holds. Check resulting
duration and seam. Similarity may favor repeated/near-static poses: inspect actual
opposite contacts and transitions before selecting an interval.

```sh
uv run --python 3.12 --with "Pillow==11.3.0" python -B skills/directional-sprite-authoring/scripts/extract-video.py export art/walk-review/extraction.json --out art/walk-frames
uv run --python 3.12 --with "Pillow==11.3.0" python -B skills/directional-sprite-authoring/scripts/pack-sprites.py art/walk-frames/sprite-pack.json --out art/walk-packed
```

Export applies one saved crop and mask across selected frames, preserving pixel
scale. It checks source/preparation/frame hashes, selection bounds and cutout
validity; it refuses existing outputs and crops that discard visible pixels.
Outputs include PNGs, provenance, a fresh preview and the existing packer's input.
It does not recenter, stabilize roots, infer facing or repair limbs. If source
pixels change, prepare a new review rather than replacing hashes to bypass checks.

## Review, repair and handoff

Inspect exported cutouts as well as the source. Changes to mask or crop require
renewed review; preserve evidence and use a new export directory for revisions.
Follow the skill's [frame, playback and runtime gates](../SKILL.md#verify-the-matrix-and-play-it).
Observe at least two playback cycles including the seam. Instrumented frame
advancement cannot certify motion; unavailable playback means unverified.

For smaller multimodal reviewers, provide a matching reference and a small numbered
board. Ask one bounded question at a time, such as facing or obvious mask damage.
Record `check`, `verdict` (`pass`, `fail`, `uncertain`), affected `frames`, and visible
`evidence`. Scripts own pixel copying, timestamps and dimensions; reviewers own
visual observations. Uncertainty remains open for further review, not a default pass.

Report extraction validity, mask quality, facing, gait/seam and runtime binding
separately. Keep generation cost/time, local processing time and repair effort
distinct. Cheap candidates are not cheaper accepted animation while repairs remain
unresolved. Compare repeated measurements before claiming efficiency gains.
