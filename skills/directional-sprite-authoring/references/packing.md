# Deterministic character atlas packing

Packing arranges already approved character pixels for the runtime. It never
generates motion, changes facing, repairs anatomy, resizes a frame, or infers an
anchor. Animated inputs must be emitted by the reviewed video extractor or by
the horizontal facing helper from those extracted frames.

Run the version 2 pack emitted beside extracted frames:

```sh
uv run --python 3.12 --with "Pillow==11.3.0" python -B skills/directional-sprite-authoring/scripts/pack-sprites.py art/walk-frames/sprite-pack.json --out art/walk-packed
```

For `origin.kind: "video-extraction"`, the packer loads the adjacent extraction
provenance, checks that it binds the exact pack specification and every frame
hash, and then copies those pixels into equal cells. Do not hand-author this form;
`extract-video.py export` creates it from reviewed timestamps, crop, mask route,
direction, action, FPS, loop setting, and anchor.

For `origin.kind: "mirrored-extraction"`, the packer loads the adjacent mirror
provenance, checks that it names `mirrored-extraction` and binds the specification
and every flipped frame hash, and then copies those pixels. Do not hand-author
this form; `mirror-frames.py` creates it from a reviewed video-extraction pack
and an allowed horizontal pair. The packer still does not flip, rotate, or guess
a facing.

A single generated directional facing may be packed as a static idle only:

```json
{
  "version": 2,
  "origin": {"kind": "static-facing"},
  "imageId": "ranger",
  "cell": {"width": 96, "height": 128},
  "anchor": {"x": 0.5, "y": 0.875},
  "requiredDirections": ["ne"],
  "requiredActions": ["idle"],
  "clips": [
    {"action": "idle", "direction": "ne", "fps": 1, "loop": true, "frames": ["idle-ne.png"]}
  ]
}
```

`static-facing` rejects multiple frames and every non-idle action. It is not a
fallback for missing walking, jumping, attack, or animated-idle video. Version 1
specifications are retired and rejected.

Input paths resolve beside the specification. Each PNG must match the declared
cell, have real transparency, and contain visible pixels. The tool refuses unsafe
paths, duplicate action/direction clips, missing declared coverage, non-finite
values, oversized allocations, stale provenance, and existing output folders.

Outputs are `sheet.png` and `runtime.json`. The runtime file contains the image,
named textures and clips, directional mappings, custom actions, source hashes,
cell size, anchor, gutters, and row order. Atlas success proves deterministic
layout only. Inspect every frame and at least two playback cycles at the intended
game scale for direction, identity, root drift, edge damage, and the loop seam.
