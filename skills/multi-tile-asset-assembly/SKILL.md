---
name: multi-tile-asset-assembly
description: Place large or multipart isometric assets with measured sprite contacts, explicit solid volumes, walkable floors and open passages. Use for fountains, buildings, bridges and assets whose image rectangle does not describe their collision.
---

# Multi-tile asset assembly

For a world requested in ordinary language, the
[visual production workflow](../isometric-visual-loop/SKILL.md) owns overall scope.
Infer the structural parts needed for its buildings, bridges and large scenery;
the user need not enumerate them. A validated first assembly is a milestone,
then continue with the requested world. Record API limitations before final art;
do not distort intended proportions or remove passages to hide those limitations.

## Define space before dressing it

Keep a host-owned assembly blueprint with one `(c,r,level)` origin and a row per
part: relative grid position, role, footprint, physical height, sprite contact
and floor. Distinguish **solid**, **walkable surface**, **open passage**, and
**decoration**. Map indexing is `map[r][c]`; omitted level means ground. Cells on
different floors are independent. The image's alpha or bounding box is never
an occupancy map.

State the routes the player must use, the cells they must not enter, and actual
player/jump dimensions. Describe vertical volumes as well as ground occupancy.
A fountain with a low basin and tall stone centerpiece needs both solid heights;
declaring the stone decorative just to fit one collider changes the game design.
Use separate blockers or explicitly choose a conservative full-height footprint.
Walking around an asset alone cannot expose jumping through its upper structure.

## Assemble supported pieces

Current entity colliders are axis-aligned grid rectangles (`columns`, `rows`,
`blocking`, `bodyHeight`). Use several proxy entities for irregular unions, with
a transparent named texture when art is separate. Keep `bodyHeight` independent
of render height. There is no freeform polygon, hollow collider or assembly
transform field in the scene schema. Do not add fictional fields to JSON.

A raised traversable bridge needs a sparse upper `levels[].map`, access `links`,
ground supports and appropriate deck barriers. Declare what belongs underneath:
blocked water, a visible opening, or an actual traversable underpass. Do not add a
walkable underpass requirement to every bridge. Raising a bridge sprite does not
create walkable space; a full-size ground blocker destroys an intended underpass.
Where traversal underneath is required, check slab headroom with the actual actor
height. Inspect the relevant floor views and both access
directions. Read [complex assemblies](references/complex-assemblies.md) for the
bridge/arch and building/doorway patterns and current renderer limits.

## Fit art to the blueprint

Apply [isometric-art-integration](../isometric-art-integration/SKILL.md) for shared
player/prop scale and source measurements. Use actual geometry/decoded pixels. Its PNG
checker does not validate SVG; for the bundled SVG fixture use measured contacts
in the assembly sidecar and inspect browser rendering. Do not claim PNG-tool
acceptance for that fixture. Measure at least three noncollinear
rigid contacts, not the padded image center. For a frame-local point `p`, compare
`(p - anchor * frameSize) * scale + offset` with the expected projection relative
to the entity origin. Here scale includes `visual.width / frame.width` and
`visual.scale`; for this runtime `x=(dc+dr)*tileWidth/2`,
`y=(dr-dc)*tileHeight/2-height`. Keep source facts distinct from design intent.

Offsets move pixels, not the entity's depth/occupancy footprint. If a rigid part's
contacts move into another cell, correct its world placement or assembly parts;
do not compensate with a taller `bodyHeight`. Check repeated edges beside an
idle actor on the adjacent walkable row, not only at assembly access points.

All parts share a world scale and assembly origin; each may have its own anchor.
Keep a helper or data builder in the host if the assembly is reused. Reorienting
an assembly needs transformed local grid offsets, footprints, access links and
matching rendered views; rotating a 2D sprite does not rotate isometric geometry.
For modular rails/walls, measure matching endpoint contacts and projected slope.
An anchor cannot turn a shallow generated rail into a 2:1 edge. Reject a materially
wrong camera or request a focused replacement. For a small retained residual,
record its magnitude and acceptance basis; fitting a midpoint distributes error
but does not correct the camera. Inspect the actual repeated joints as well as
one isolated part. A three-cell footprint spans three tile intervals at its outer
edges, while its first/last cell centers span only two: confusing these produces
gaps when repeating rails. Keep collider reservations separate from render spans.
For moving parts, add [animated-environments](../animated-environments/SKILL.md)
after the solid and traversal contracts are established.

## Check the actual scene

Write the relevant expectations in an [assembly plan](references/assembly-plan.md)
beside the host scene, then run:

```sh
node --experimental-strip-types skills/multi-tile-asset-assembly/scripts/check-assembly.mjs scene.json assembly-plan.json
```

Run from the repository root with Node 22.18+. The checker reads public core and actual scene
bindings; it checks declared contacts, occupancy, solid heights, paths and slab
clearance. Use exact paths for a required passage: mere reachability may detour.
The plan is authoring evidence, not a new engine schema or a pixel/physics test.

Finish with one rendered overlay and an actual traversal covering the requested
entry/exit and front/behind behavior. If jumping is enabled, include the relevant
raised solid or ceiling in that journey. Do not move a probe or weaken a blocked
cell expectation just to get green. Report physical, visual and animation
acceptance separately, including conservative collision or depth limitations.
See the [generated-asset trial](../../docs/GENERATED_ENVIRONMENT_TRIAL.md) for
observed source contacts, rejected rail perspective and remaining approximations.
