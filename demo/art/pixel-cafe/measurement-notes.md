# Sunflower courtyard measurement notes

Measured 2026-09-08 against the live host definitions in ../../pixel-cafe.ts.
This sidecar is authoring data, not an extension to the runtime Scene schema.

## Frozen contract and interpretation

This full contract was assembled after the repaired scene was implemented.
It is retrospective calibration. The tolerances below were fixed before running
the checker, but the furniture height references describe the chosen rendered
result; they are not independently dated target proportions. Their agreement
establishes consistency and a future drift baseline, not successful scale design
by itself. See [the run reflection](TASK_REFLECTION.md) for the workflow correction.

- Camera: tileWidth 80, tileHeight 40; vertical height scale 40 world pixels/unit.
- Tolerances were set before checking: ground error 2 world pixels, height error
  4 world pixels. They have not been widened to accommodate failures.
- Reference actor standing height, INCLUDING its hat: 1.85 units. The source is
  deliberately stylized. This is a shared scale convention, not a claim that the
  character has realistic adult anatomy.
- Furniture reference heights: left chair seat .52, right chair seat .49,
  tabletop .74 units. Lamp 1.90, palm 2.65, orange flowering plant 1.43,
  shrub 1.62, parasol apex including finial 3.28, raised soil .25 units.
- Metadata PASS means the recorded measurements, declared projection, hash,
  frame bounds, and scale agree within these tolerances. It is not visual or
  gameplay acceptance.

The current contract contains 28 entries: 3 active terrain textures, 16 authored
planter base variants, 4 actor idle facings, the furniture composite, lantern,
orange pot, shrub, and palm. There are 98 ground correspondences and 28 height
measurements. The checker passes with zero errors.

The preserved before contract contains one original purple planter. At the SAME
2/4 px tolerances it fails with 5 errors: 2 measured contacts spill outside its
1x1 footprint, and 3 source/canonical correspondences have projection errors
13.8364, 15.0382, and 11.9732 px. This is intentionally failing evidence.

## Source integrity and measurement method

All source points are relative to the declared cropped frame. Original PNGs were
visually inspected and decoded read-only using System.Drawing.Bitmap, including
selected RGBA/alpha scans. No image processing was applied by the measurement
workflow. Decoded dimensions:

| Image | Dimensions | SHA-256 |
| --- | --- | --- |
| garden-atlas.png | 1254 x 1254 | 7f08b2abb668528fb81c82e99bd8dae6ddd68ad9d1fd6e0dede2292d626c4fe9 |
| gardener-atlas.png | 1254 x 1254 | 7bb2356b28300c152f0878a2d7b4996eb6c41ddb22c6800721a74b41bf67487a |
| planter-bases.png | 640 x 512 | 1e2e0b0d81621bc66c4dfe526d862c19ead022acdc7443c363d438b0ddf42440 |
| flowers-v2.png | 1774 x 887 | 09737d058efaf88bcce9a555529635fa5356da730fc86a62021601d488fe300a |

build-contract.mjs holds the manual measurements and fixed accepted hashes.
It refuses to regenerate sidecars when a measured source hash changes.
Re-measure first; do not simply refresh a hash to make a check pass.

## Terrain: measured outer tips, intentional renderer warp

For each original active tile, scanned alpha > 200 pixels identify the outer
tip clusters. Coordinates below are the midpoints of those clusters, not corners
invented from the crop bounds:

| Texture | Left | Rear/top | Right | Front/bottom |
| --- | --- | --- | --- | --- |
| terracotta | (4,97.5) | (147.5,6) | (292,97.5) | (146,191) |
| grass | (5,99) | (152.5,5) | (299,98.5) | (152.5,193) |
| sandstone | (5,99) | (151,5) | (294,98) | (151,193) |

Tip uncertainty is approximately 1-3 source pixels from pixel clusters and
transparent fringes. Frame/render dimensions are copied from the actual host:
the entire crop is fit to 80 x 40 with an anchor at (.5,.5). This nonuniform
terrain warp is allowed by the runtime and contract; no equivalent deformation
is applied to actors or props. These measured tips fit within 2 rendered pixels.

This check proves only the outer diamond placement. The original approximately
3:2 source diamonds, their internal paving lines, and the final 2:1 renderer
warp require visual review. It does not independently prove that every internal
drawn grout line has a mathematically exact projection.

## Authored planter bases

build-planters.mjs is the source of the geometry, and its output was inspected.
Each 160 x 128 frame uses exactly 2 source pixels/world pixel, display width 80,
and anchor (80,88) in source pixels. The ground-envelope corners are:
(0,88), (80,48), (160,88), (80,128).
The soil-center height segment is base (80,88), top (80,68): 10 world pixels.

These are the known authored geometric ground projections, independently
established by the generator's c/r mapping and vertical-face depth, NOT an
attempt to reinterpret incompatible generated stone corners. Pixel rasterization
occurs at source pixel centers; points on the outer image boundary describe the
geometric boundary rather than an opaque sample at x=160 or y=128.

All 16 masks share this envelope and height. Neighbor masks remove internal
walls; several theoretical ground corners are therefore hidden or have no
visible wall contact in that variant. The metadata entries deliberately record
the common authored envelope, not falsely observed opaque corners in every
variant. Actual continuous joins along both axes and at corners need rendered
calibration-scene evidence. Separate flower sprites are not part of this rigid
base measurement.

## Actor calibration

The four idle frames use x=82; y=25,328,635,939; size 160 x 280; width 48.
NE/SE/SW/NW contacts are approximately (83,261), (83,261), (83,260), (83,258).
Their frame-local hat-top y values are approximately 13,12,15,11 respectively.
The contract uses vertical segments at x=83, with the ground point beneath
the head inferred from the existing foot-origin alignment.

Standing measurements are 74.4,74.7,73.5,74.1 world pixels, consistent with the
74 px reference. Source-landmark uncertainty is approximately 3-5 pixels
(0.9-1.5 world pixels). Existing x anchor .52 places its origin at 83.2;
the .2 source-pixel difference from the observed contact is immaterial.
The actor's bodyHeight 64 is a separate physical runtime setting; the visual
reference here includes the hat.

Only idle facings are geometrically recorded. Walking poses and jump shadows
share host frame sizes and per-row anchors, but exact contact drift through all
12 other authored frames is UNVERIFIED by this contract. Validate those frames
during actual movement and jumping. Do not count 4 idle entries as 16 frame
acceptance.

## Composite furniture

Frame: atlas (42,6), 275 x 342. Render width 120, uniform scale 120/275,
anchor (138/275,304/342), offset (+40,0), occupied cells 2 x 2.
The origin is inferred from its support arrangement with about +/-8 source px
uncertainty. The offset puts the group over the center of its four occupied cells.

The actual physical landmarks, not the padded crop width, support the scale:

| Landmark | Base | Top | Rendered height |
| --- | --- | --- | --- |
| Left chair front seat corner | (70,327) | (69,279) | 20.95 px / .524 units |
| Right chair front seat corner | (203,316) | (204,271) | 19.64 px / .491 units |
| Table front vertex | (134,327) | (134,259) | 29.67 px / .742 units |
| Parasol apex including finial | (138,304) | (138,3) | 131.35 px / 3.284 units |

Seat/table endpoints have roughly +/-4-6 source-pixel uncertainty because the
legs splay and the surface vertex's exact vertical ground projection is partly
inferred. The small 1 source-pixel x differences on seats are retained rather
than silently straightening the measured endpoints.

Visible support contacts are approximately (25,303), (70,327), (134,327),
(203,316), (254,289). Their grid coordinates are inverse-projected from the
observed contacts under the declared scale, then rounded to .01 cells. These
INFERRED support grids establish containment and a reproducible placement;
they are not independent proof that the artist's furniture ground projection
is exact. The chair/table height comparisons above are separate evidence.

At the previous width 158 the same left seat and table become .689 and .977
units, too high relative to the unchanged 1.85-unit gardener. This is why the
repair changes composite width, rather than enlarging the actor to match it.

The canopy fringe at source y approximately 140-151 has clearance only around
1.7-1.8 units above the inferred support center, near/below the gardener's hat.
Its tall dome and finial are stylized. One sprite cannot independently correct
canopy clearance, permit seating, or interleave the actor with individual
chairs/table legs. This remains a BLOCKED DECORATIVE SEATING GROUP. Its 2 x 2
collision area is conservative; do not claim that art width determines its
collision polygon or that walk-under furniture is implemented.

## Lamp and round pots

Lantern width 27 is retained. Measured base vertices are approximately
(13,310), (44,295), (76,312), (44,329), with +/-3-4 source-pixel uncertainty.
An independently fitted small 16 x 8 world-pixel diamond is a credible 2:1
footing: intended grids (-.1,-.1),(.1,-.1),(.1,.1),(-.1,.1).
Its revised source anchor (44,313) centers the footing instead of using its
front edge. Ground-to-apex (44,313) to (44,3) is 76.09 world pixels.

The round pot bases do not expose rectangular ground corners. Recorded visible
curve points are:

| Asset | Width | Visible curve points | Height segment |
| --- | --- | --- | --- |
| orange-pot | 54 | (77,249), (163,249), (120,264) | (120,253) to (120,3) |
| shrub | 58 | (65,249), (153,249), (110,265) | (110,257) to (110,8) |
| palm | 104 | (118,296), (189,296), (153,310) | (153,300) to (153,3) |

Each grid correspondence is explicitly INFERRED by inverse projection of the
observed curved bottom, rounded to .01 cells. This checks that the measured
base fits inside its occupied cell; it does NOT independently establish the
circle's original camera projection. The hidden rear contact is not measured
or fabricated. Curve estimates have approximately +/-3-5 source px uncertainty;
height endpoints approximately +/-5 px. Foliage apex and ground center are
inferred vertically aligned landmarks, not padded image bounds.

Existing orange-pot anchor (.5,.92) and shrub (.5,.93) remain close to their
base centers. Palm anchor is (153/292,300/325). Plant heights at these widths
are approximately 57.20,64.76,105.78 px respectively and share a believable
scale with the 74 px gardener.

## Coverage limits and outstanding visual/gameplay checks

- flowers-v2.png is separate generated foliage with no hard planter base. Its
  hash/dimensions are recorded above, but no imaginary rigid contact polygon is
  supplied to satisfy the prop checker. Its host frames, two crown placements,
  overhang, and depth behavior need rendered review.
- The smaller collectible seed-pot uses the orange-pot image at width 22; this
  decorative miniaturization is not separately measured as adult furniture.
- Unused separate chair textures, unused decking terrain, and original replaced
  bed textures are excluded from current acceptance coverage.
- Existing fence sprites remain outside this focused contract. Their joins,
  orientation, and rigid outlines must not be claimed calibrated by these
  28 entries.
- Actual movement, collision, front/behind occlusion, mobile/desktop composition,
  corner joins, production image loading, and flower texture alpha are not
  established by a metadata checker. Record their independent evidence elsewhere.
- Current metadata: PASS (28 entries, zero errors). Before diagnostic: FAIL,
  preserved. Visual compatibility and gameplay: require the separate host QA
  evidence; no automatic acceptance is implied here.

Reproduce from the repository root:

    node Runtime/demo/art/pixel-cafe/build-contract.mjs
    node Runtime/skills/isometric-art-integration/scripts/check-art.mjs Runtime/demo/art/pixel-cafe/art-contract.json
    node Runtime/skills/isometric-art-integration/scripts/check-art.mjs Runtime/demo/art/pixel-cafe/art-contract.before.json

The final command intentionally exits nonzero. The original before observations
were copied unchanged from Runtime/test-results/art-skill-contract.json; its
old width 82 and anchor (.5,.79) are preserved, with a portable relative image
path and the new common frozen tolerances for a comparable diagnostic.
