# Visual calibration and acceptance

## Calibration before composition

For a repair, capture the reported defect at close zoom before replacing assets.
Use the same scene location and comparable scale for the after view. Establish
the smallest candidate and intended proportions before expanding the layout;
label a contract created later as retrospective.

For newly generated transparent art, decode one representative output before
requesting a full atlas. Check actual dimensions and alpha values, then inspect
edges and interior holes on light and dark backgrounds. An RGBA file or a single
transparent pixel does not prove a clean cutout. Record failed output and the
changed assumption for a retry; repeated baked checkerboards call for a changed
source/prompt approach, not another identical transparency instruction.

1. Display candidates at the same camera zoom and world scale. Never auto-fit
   each sprite independently in a comparison: it hides proportion mismatches.
2. Overlay the actual cropped source contact points, projected footprint, and
   height landmarks. Verify the annotations against the image itself. A script
   will accept fictional annotations if they are internally consistent.
3. Compare the actor beside a chair/table/door when present. Check seat and table
   heights against the intended style, not the enclosing image rectangle.
   For composites, check seat, table, and canopy/door clearance together before
   selecting a global scale. Collision blocking cannot make a visually implausible
   clearance correct. If one scale cannot satisfy the intended relationships,
   split or reauthor the composite, or report the remaining visual limitation.
4. Place three border segments along each grid axis and form a corner. Inspect
   hard-edge continuity, stone-base spill, double walls, gaps, perspective, and
   shadows at close zoom. Document intended foliage overhang separately.
5. Walk in front of, behind, and beside props. Check feet and base contacts during
   idle, every facing, walking, and jumping. A single depth value for a furniture
   composite may fail when an actor must pass between its parts.
6. Recheck without overlays at the game's intended zoom and mobile size. Inspect
   texture seams, relative pixel density, alpha fringes, and readable silhouettes.

The HTML board is a quick source/metadata inspection tool. It does not instantiate
the runtime. The playable calibration scene belongs to the host and must use its
actual manifest and rendering settings, not a prettier independent mockup.
Diagnose camera mismatch from rendered ground edges and internal lines, not the
padded source rectangle's aspect ratio. Terrain's supported nonuniform tile fit
alone is not evidence of a projection defect.

## Record distinct verdicts

| Verdict | Evidence required |
| --- | --- |
| Metadata | Checker result, source hash, measured contacts and heights; error tolerances recorded |
| Visual compatibility | Close views of both border axes/corner, actor beside furniture, foreground/background occlusion; image annotations visibly credible |
| Gameplay | Actual movement, footprint blocking, routing, jump interactions where applicable, release and pause behavior |
| Delivery | Production URLs decode, intended viewport sizes work, remaining limitations stated |

Use `pass`, `fail`, or `unverified` for each. A metadata pass cannot promote an
unverified visual or gameplay check. Preserve a failing screenshot before any
repair. Report the visible defect, likely owner (asset, placement, or renderer),
and the smallest test that could distinguish those causes.

Include the exact covered assets and states with each verdict. Keep source
comments and handoff claims within that coverage; a four-facing idle calibration
does not measure every walking pose or jump shadow. An interrupted browser run
remains incomplete until its outstanding checks finish and its evidence is
validated. Choose the host's ignored output directory before starting capture.

## Known case to avoid repeating

The first Sunflower courtyard used generated rectangular planters at width 82
with 1×1 footprints and independently sized gardener/furniture images. It passed
image-bound and collision checks but
showed protruding stone borders and implausible player/furniture proportions.
That version is a failure example, not a calibrated reference pack. A pleasing
full-map screenshot did not establish correct joins or physical scale.

Do not repair that class of problem by clipping the entire sprite to its tile:
valid foliage, umbrellas, and tall objects need overhang. Measure and correct the
rigid ground geometry; reauthor incompatible assets when offsets cannot fix it.
