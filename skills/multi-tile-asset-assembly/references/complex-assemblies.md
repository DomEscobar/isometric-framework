# Buildings, bridges and negative space

## Bridge with an arch

Use these responsibilities, not one large bridge entity:

| Part | Spatial role | Rendering responsibility |
| --- | --- | --- |
| Deck | Sparse raised floor with walkable cells | Tile surface at the actual deck height |
| Stairs/access | Adjacent surfaces and explicit cross-floor links | Art follows the supported heights |
| Abutments/piers | Separate ground blockers, explicit solid height | Ground-anchored support sprites |
| Rails/parapets | Deck-level barriers | Separate near/far pieces at useful sorting origins |
| Arch opening | Open ground cells and sufficient headroom | Transparent negative space between supports |
| Arch stone | Rigid overhead structure | Split front/back art; do not fill the opening with a ground rectangle |

Check the exact lower passage and upper crossing independently. Water below the
arch can remain unwalkable while a dry towpath stays open. If the game requires a
curved collision underside, the current rectangular bodies and floor slabs cannot
represent it exactly. Use an explicitly conservative passage/slab approximation
that meets the gameplay brief, or identify the required engine extension. Do not
claim alpha-shaped arch collision.

Floors share a painter order based on overlapping screen bounds and separated
world-space footprint/height intervals. Ambiguous or cyclic relationships fall
back to front-most contact, with a small footprint-size bias placing compact
bodies ahead of large ones at equal depth. A giant flattened bridge/building cannot interleave correctly with
the actor everywhere. Split at floor boundaries and front/back occlusion needs.
Ground cutaway helps inspect an underpass; it does not fix arbitrary depth order.
Avoid invented `zIndex`, collision polygon or crop-mask fields. Visible parapets
occupying a thin edge still reserve whole cells with current blockers: document
that margin or create a scoped engine change only if precision is required.

If the brief calls for an ornate arch, a plain pier-and-deck assembly proves only
its supported traversal. Create the required layered artwork and check the arch's
visible opening separately before accepting its appearance.

## Shop or building spanning several tiles

Measure the rigid ground corners and doorway threshold; roof extent is not the
foundation footprint. Model walls as rectangular unions leaving doorway cells
open. Put interior floors, access and gameplay in the host scene if entering is
required. A painted door is not automatically an entrance or a scene transition.

Split roof, awning, storefront props and facade where the player must move in
front/behind them. Preserve a useful sidewalk and actual headroom beneath awnings.
The engine has no arbitrary floating collision body: `bodyHeight` grows from an
entity's supported feet. Do not block an entire sidewalk from ground level merely
to imitate an overhead awning. Decorative overhead art is acceptable when its
gameplay omission is explicit and irrelevant to the requested traversal.

Signs and foliage may overhang the footprint; rigid walls must match it. Furniture
and door scale must be compared against the same player in the rendered scene.
Keep placement and collider derivation alongside the source contacts so another
agent can replace artwork without rediscovering or silently changing the layout.

For a building spanning several cells, check the same final actor cell from both
tile axes: one successful approach does not prove stable sorting. Include
compact/large footprint depth ties and foreground actors beside raised surfaces.
Inspect the actor **standing idle on each access step**, on the
deck, and below it; a successful crossing alone misses arrival-time clipping.
Verify the exact cell, floor and feet height after the route ends and after
camera changes. Seeing a coordinate briefly during travel does not prove arrival:
a click on a raised surface's shared edge can target the neighboring upper tile.
Include a tall foreground prop and restore the full scene after a ground cutaway.
Declare `bodyHeight` for nonblocking art too: flat water can use 1px (zero is
invalid), while a parapet uses its actual vertical extent. Sprite rectangle
height includes projection and is not a valid surface height. Unsplit canopy
overhangs still require a fresh visible check and potentially separate pieces.

## Neutral offset example

For tile dimensions `W×H`, a sprite offset `(-W/2,-H/2)` equals one row backward
in this projection. A rigid part declared at `(c,r)` would appear at `(c,r-1)`
while its depth/occupancy footprint remains at `(c,r)`. If its measured contacts
belong to the latter visible cell, place the part at `(c,r-1)` and remove that
offset: the artwork stays in the same screen position and its spatial metadata
now agrees. Preserve its measured physical height; adding image-offset distance
to `bodyHeight` does not repair an incorrect world origin. Include representative
repeated-edge contacts in the assembly plan, not just large-building landmarks.
