# Witchhollow Tactics — Art direction record

Authoring decisions for the agent adding assets. See PRODUCTION_BRIEF.md for
composition; this file answers "what do I draw and how".

## Shared projection
- Tiles: 72×36 world pixels (2:1 diamond). Terrain painted on ONE continuous
  canvas then sliced per tile; each slice is exactly 72×36 with its diamond
  occupying the full rect bounds (center 36,18; corners at (36,0),(72,18),
  (36,36),(0,18)).
- Terrain slice alignment: tile (c,r) center = ((c+r)*36, (r-c)*18).
- Sprites: transparent PNG, feet at anchor (0.5,1), bottom-center of frame =
  tile center. Witch frames 40×52; familiar frames 32×36. Ground contact row =
  bottom row.
- No baked shadows inside sprite frames; engine/landscape handles ground.

## Palette (4-shade ramps, 1 base + 2 mid + 1 dark)
- cream stone: #f4e4c2 #e4cf9e #cbb17e #9c845f
- moss grass: #9cbd7e #7fa06a #64885a #47654a  (high sun: #b5d190)
- teal water: #a8e2e0 #7fcbd0 #4fa8b4 #2f7f8a
- wet bank: #c9b98f #ab9874 #8a7a5c #6b5f46
- amber accent: #ffd98a #f2b85c #d98e35 #a86a1f
- slate outline: #3a3738 (thin, on units/props)
- witch robe (player): #e5f0f7 light periwinkle robe, #6f6bb5 trim
- witch robe (enemy): #f7cf8f warm cream robe, #b5613a trim
- familiar leaf: #d9e08f #9fb65a #6f8f3f #4a6229
- familiar ember: #ffd9a0 #f59a4a #d9612e #a33d1c

## Light
Upper-left. Sides: left face lighter than right face; top faces brightest;
underside darkest. Consistent across terrain, props and units.

## Style
- Cluster size 1-2px max in terrain, 1px crisps on units; occasional 2px for
- outline halos on units: thin #3a3738 contour, 1px.
- No dithering bands < 2px; no per-tile mirrored motifs.
- Unit proportions: head ~1/3 height, hair+hat, robe/boots; big expressive eyes.

## Files
- art/terrain/tile_C_R.png — per-tile ground slices (72×36).
- art/terrain/dais_C_R.png — raised surface slices (72×36).
- art/terrain/side_*.png — side texture strips for raised faces (repeatable).
- art/props/*.png — prop sprites (transparent).
- art/sprites/<model>_<facing>_<state><n>.png — unit frames.
- art/runtime.json — scene asset manifest (host-owned).

## Source record
All assets authored by this project (tools/terrain.py, tools/sprites.py,
tools/props.py). No bundled example or third-party artwork used.
