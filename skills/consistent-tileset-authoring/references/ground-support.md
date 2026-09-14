# Check visible support along a route

Use this optional offline Pillow checker when the question is whether the actor's
feet and reserve fit on visible ground throughout a planned or recorded route.
It complements identifiable landmark registration; it does not prove exact layout
reproduction. Choose the check before evaluating the candidate. Preserve earlier
failed or unverified evaluations when explicitly changing the evaluation method.

First register the candidate into the host's projected pixel coordinates with a
declared transform. Derive a visible dry-ground mask from the actual artwork and
inspect it over that artwork, especially at banks and entrances. Keep a separate
mask of the host's planned support minus water and solid footprints. Masks may be
manually authored or proposed by segmentation; expected layout colors copied into
the visible mask are not image evidence. Uncertain fringes should be excluded.
The checker does no segmentation and supplies no universal color thresholds.

Export route points through public `project()` using the same origin and scale as
the image. Match the declared diamond to the actor's actual ground-contact shape,
not its whole upright sprite or occupancy cell. Check the sprite's contact anchor.
Choose a clearance for each route section before inspection; keep tight approaches
explicit. One flat plane is supported; elevated paths need separate registered
planes and their own support checks.

```sh
python skills/consistent-tileset-authoring/scripts/inspect-ground-support.py support.json --out review/support-1
```

Example recipe for a 256 x 160 registered image, two reviewed masks and a small
neutral actor. Numbers are illustrative; all files are local to the recipe:

```json
{
  "version": 1,
  "overlay": "registered-ground.png",
  "supportMasks": [
    {"id": "visible-dry", "image": "visible-dry.png"},
    {"id": "planned-dry", "image": "planned-dry.png"}
  ],
  "footprint": {"halfWidthPx": 8, "halfHeightPx": 4},
  "routes": [
    {"id": "path-bend", "points": [[32, 96], [96, 64], [160, 96]], "clearancePx": 3},
    {"id": "approach", "points": [[160, 96], [192, 80]], "clearancePx": 2}
  ]
}
```

Masks must decode as opaque black/white PNGs of the image's dimensions. White means
supported; every mask must support the complete footprint. Footprint half-extents
are positive finite pixel values. Routes have unique IDs, at least two points and
nonnegative clearance. Duplicate points can inspect a stationary pose. Split
disconnected journeys instead of joining them by a fictitious straight segment.
Paths are relative forward-slash paths inside the recipe directory.

The checker samples each segment at intervals no greater than one pixel. It checks
the diamond expanded by square clearance against all masks; floor/ceil positions
make fractional coordinates conservative. Outside-image footprint pixels fail.
`ground-support-review.png` marks failed footprints, and `measurements.json`
reports sample counts and the first offending pixel per route/mask. Provenance
records input and tool hashes; timings are separate. A new output directory is
required. Exit codes: `0` supported, `3` support failure, `2` invalid input.
Resource caps bound image sizes, route samples, footprint search and check work.

After passing and visually reviewing masks, use the
[ground preparer and runtime binder](composed-ground.md). Inspect the rendered
feet at bends, banks and arrivals. Record public `getEntityPose()` positions during
actual pointer/keyboard journeys, project them into this same image, and check
those traces too. Sampling only arrival events misses motion between destinations;
old arrival events cannot satisfy a later command. Keep each command's evidence
separate. Support results do not establish input behavior, art quality, motion,
whole-map collision equivalence or mask correctness.
