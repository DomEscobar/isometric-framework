# Inspect supplied registration landmarks

Use this offline Pillow helper when a layout guide and a candidate PNG are already
in the same capture coordinate system. It measures only landmarks a reviewer
supplies; it neither discovers them nor moves either image.

```sh
python skills/consistent-tileset-authoring/scripts/inspect-registration.py registration.json --out review/registration-1
```

The recipe is version 1. Image paths are local forward-slash paths relative to
the recipe. Supply three to 256 uniquely named points on each image, with exactly
the same IDs and at least three distinct coordinates. IDs are nonempty strings
of at most 128 characters. Distribute them over the features that matter and
include at least one expected point strictly inside the image, so
matching corners cannot stand in for a bridge, path, entrance, or other interior
feature. Coordinates are finite pixel coordinates from `0..width-1` and
`0..height-1`; fractional measurements are allowed. `pixelTolerance` is a finite
number in `0..max(width,height)`. Choose it for this particular review and record
why. The helper deliberately provides no universal tolerance.

```json
{
  "version": 1,
  "layoutGuide": "registered-layout.png",
  "candidate": "candidate.png",
  "pixelTolerance": 1,
  "expectedLandmarks": [
    {"id": "north-west", "x": 0, "y": 0},
    {"id": "south-east", "x": 639, "y": 383},
    {"id": "bridge-centre", "x": 304, "y": 188}
  ],
  "observedLandmarks": [
    {"id": "north-west", "x": 0, "y": 0},
    {"id": "south-east", "x": 639, "y": 383},
    {"id": "bridge-centre", "x": 305, "y": 188}
  ],
  "provenance": {"reviewer": "optional caller metadata"}
}
```

`registration-board.png` is a side-by-side review board: transparent image areas
are composited over a neutral checkerboard, green markers meet the declared
distance tolerance, and red markers fail it. Its footer repeats that landmarks
are caller-supplied, plus tolerance and maximum residual. `measurements.json` records
the expected and observed points, x/y residuals, Euclidean distance, threshold,
and pass result. `provenance.json` records input and tool hashes plus the board
hash. `timings.json` records duration. The output directory must not exist and
is never overwritten. The recipe is at most 1,048,576 bytes. Inputs must be
single-frame static PNG files of exactly equal dimensions; each image is at most
8192 pixels per axis, 16,000,000 pixels and 64 MiB encoded. The rendered board,
including its 64-pixel footer, is capped at 64,000,000 pixels. Malformed paths, non-finite/out-of-bounds coordinates, duplicate or
missing IDs, and missing interior coverage are errors.

Exit `0` means every supplied residual met the supplied tolerance. Exit `3` means
measurement completed and at least one residual exceeded it; review the emitted
board and JSON. Exit `2` means malformed or unsafe input and emits no output.

This is registration evidence only. It does not automatically detect landmarks,
fit a transform, compare pixels, warp artwork, or certify geometry, perspective,
style, seams, animation, collision, or gameplay. Inspect the named interior
features and the actual host separately.

Run the focused synthetic tests with:

```sh
python -m unittest discover -s skills/consistent-tileset-authoring/tests -p test_inspect_registration.py
```
