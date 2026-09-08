# Deterministic sheet assembly

The packer accepts approved, normalized PNG frames on a common canvas. It does
not generate art or infer root positions. Review actual facing and scale before
assigning direction labels. A common declared anchor is an instruction to the
renderer, not a measurement that the painted roots agree.

Save `sprite-pack.json` next to the input frames. Example for the initial four-view
idle review, with 96×128 canvases and a root at source pixel `(48,112)`:

```json
{
  "version": 1,
  "imageId": "ranger",
  "cell": {"width": 96, "height": 128},
  "anchor": {"x": 0.5, "y": 0.875},
  "requiredDirections": ["ne", "se", "sw", "nw"],
  "requiredActions": ["idle"],
  "clips": [
    {"action": "idle", "direction": "ne", "fps": 1, "loop": true, "frames": ["idle-ne.png"]},
    {"action": "idle", "direction": "se", "fps": 1, "loop": true, "frames": ["idle-se.png"]},
    {"action": "idle", "direction": "sw", "fps": 1, "loop": true, "frames": ["idle-sw.png"]},
    {"action": "idle", "direction": "nw", "fps": 1, "loop": true, "frames": ["idle-nw.png"]}
  ]
}
```

Replace dimensions, anchor and filenames with actual approved measurements.
For walking, add `walk` to `requiredActions` and four corresponding clips with
their accepted phase filenames in playback order. For example, a clip can use
`["walk-ne-contact-a.png", "walk-ne-pass-a.png", "walk-ne-contact-b.png", "walk-ne-pass-b.png"]`
at a chosen FPS. Repeated paths are allowed for holds. Custom actions such as
`attack` use the same clip fields; use `loop: false` when they should play once.

From the repository root:

```sh
uv run --python 3.12 --with "Pillow==11.3.0" python -B skills/directional-sprite-authoring/scripts/pack-sprites.py path/to/sprite-pack.json --out test-results/poses/packed
```

Input paths resolve relative to the spec. Use a new output directory. Every PNG
must already match `cell` dimensions and contain both transparent and foreground
pixels. Do not remove backgrounds by deleting the same color from every frame;
apply the generation skill's cutout inspection instead. Unknown fields, duplicate
action/direction pairs, incomplete required matrices, invalid sizes and excessive
allocations fail rather than silently creating a partial sheet.

Each clip occupies one sheet row, following the supplied clip order. Frames are
copied in the specified sequence with transparent gutters. Rectangles in the
output describe exactly where the pixels were placed; consumers must use these
rectangles instead of assuming a third-party row convention.

Outputs:

- `sheet.png`: unscaled, unmirrored pixels on the common cell grid.
- `runtime.json`: `assets` contains the image, named textures and clips;
  `visualAnimations` maps only idle/walk/jump to directions; `customActions` maps
  additional actions to direction-specific clip IDs. Source hashes accompany the
  result for provenance, not as proof of correct facing.

The first supplied clip for each native action becomes its general fallback.
An undeclared direction may therefore show that facing. The required matrix
checks only the actions/directions you explicitly requested; it does not certify
eight-way support for a four-view pack.

Keep `sprite-pack.json` and input source records with the host pack. Copy accepted
output to its maintained art directory and update the image URL through the host
bundler as shown in [runtime binding](directions.md). The JSON is an authoring
bundle, not a complete Scene and not a replacement for game rules.

Packing success proves layout and declared coverage only. Inspect all resulting
frames and actual playback for root drift, visible direction and identity before
acceptance. Preserve explicit frame/action/direction coverage in the handoff.
