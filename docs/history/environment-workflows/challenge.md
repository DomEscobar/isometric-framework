# Shared environment authoring challenge

This is the same task for all three trial workflows. Produce `scene.json` and
`placement.md` in your assigned output directory. Use only the existing runtime
scene/API contract; do not modify engine, supplied artwork, or other trials.

Build one 13×13 map with 64×32 isometric tiles, cardinal click routing, one actor
with 48-pixel body height starting at `(1,6)`, and these three environment features:

- River: columns 5 and 6 along all rows, unwalkable to the actor, animated water.
  Its neighboring cells should make a continuous surface. Keep column 4 as a dry
  towpath, including under the bridge.
- Fountain: a large 3×3 solid basin starting at `(1,8)` with a looping water jet.
  Its rigid footprint must align with exactly those nine cells; the actor can
  walk around it. Basin/stonework do not wobble with the water animation.
- Bridge: deck at absolute feet height 72, columns 3..8 and rows 4..6, connecting
  the river banks. Walk through its center row 5 from either bank. Access ground
  steps are `(0,5)=18`, `(1,5)=36`, `(2,5)=54` and `(9,5)=54`, `(10,5)=36`,
  `(11,5)=18`; terrain permits 18-pixel steps. Deck-edge rails occupy rows 4 and 6
  of that deck. Ground piers are at `(3,4)`, `(3,6)`, `(8,4)`, `(8,6)` and block
  only those support cells. The towpath at column 4 must remain walkable from
  row 3 through row 7 under the bridge, independently of the deck above.

Use the supplied `assets/challenge-atlas.svg` and `challenge-sources.json` as the
source; the evaluator serves it at `/__environment-atlas.svg`. The JSON describes
authored source measurements, not a preapproved scene configuration. Name the
image source `challenge`, the main actor `traveler`, the fountain entity/assembly
`fountain`, and the upper floor `bridge`. Asset frame IDs are in the source file.
Other IDs are your choice. Pixel measurements must drive rendered placement.

The initial draft idea was to use the whole fountain at `width:192, anchor:{x:.5,
y:1}` with its 3×3 footprint, and the bridge as one large blocking entity. Treat
these as proposals to evaluate, not fixed requirements. The user wants correct
visible contact, blocked solids, traversable openings and steady animation.

Your placement note should explain the contract actually used, loop period,
solid/decorative/walkable ownership, access routes, occlusion limits, and checks
you ran. Use a few meaningful checks, not an exhaustive regression suite. No
network generation or paid services are needed; this is a functional calibration
scene, not a reproduction of the user's detailed raster reference artwork.
