# Autumn crossing art provenance

The material, prop, bridge and cliff source PNGs below were generated for this
trial using the built-in OpenAI `image_gen` tool. Its underlying model was not
exposed.
The user's reference and `.world-build/autumn-crossing/concept.png` guide the art
direction; neither is pasted into the playable scene. Request identifiers are
not recorded in the current asset metadata. Do not infer the generation model
from the preparation tools listed below. [PROMPTS.md](PROMPTS.md) records the
generation briefs, tool output filenames and exact cliff prompt.

## Preserved sources

| File | Role | SHA-256 |
| --- | --- | --- |
| `materials-source.png` | Grass, dirt, paving and water sheet | `639da75a008acc4f6fddbf43cde9d9a63619ff80bdd563d09ed742d0366d7240` |
| `props-source.png` | Three trees, rock, shrub and bench | `81acbd1410f64142be224193c0a61de6bd9ce2b8003f642b3f517b37e194ee68` |
| `bridge-source.png` | Rejected first bridge: unsuitable proportions | `5987ed6bc3f072cbd0a66574c7c7aaa274b2d35db53bc492ffc8e21064d83a1e` |
| `bridge-source-v2.png` | Replacement bridge used for face extraction | `d9bf855679380540abe889cd9bf8b15f1bd566fcc2bb663eb9d444141d457fab` |
| `cliff-source.png` | Rock material for raised bank facings | `a6c450a2adaa10eb198be15ee66920c136e60b56a604095b9153f6a4fc824ac2` |

Keep raw sources, cutouts and registered derivatives distinct. Asset registration
metadata is not a gameplay or visual-quality pass. In particular,
`bridge-metadata.json` records its in-game acceptance as unverified.

## Reproducible preparation

Run the following authoring commands from this directory with the preserved
sources available. These tools are not runtime dependencies.

```powershell
uv tool run --python 3.12 --from 'rembg[cpu,cli]==2.0.75' rembg i -m u2netp props-source.png props-cutout.png
uv tool run --python 3.12 --from 'rembg[cpu,cli]==2.0.75' rembg i -m u2netp bridge-source-v2.png bridge-cutout.png
uv run --python 3.12 --with Pillow==11.3.0 python prepare-props.py
uv run --python 3.12 --with Pillow==11.3.0 python prepare-bridge.py
uv run --python 3.12 --with Pillow==11.3.0 python prepare-terrain.py
uv run --python 3.12 --with Pillow==11.3.0 python prepare-cliff.py
```

- `prepare-props.py` removes remaining bright neutral checkerboard pixels from
  the prop cutout, thresholds alpha, measures crop/contact anchors and scales
  the sprites into `props-atlas.png`. Color and brightness adjustment produces
  the muted palette. `props-metadata.json` preserves crops and contact points;
  `props-frames.json` supplies runtime frames. The golden and olive source
  canopies touch the sheet edge and are suited to framing foliage.
- `prepare-bridge.py` applies measured polygon masks and separate affine
  transforms to vertical bridge faces. The transform keeps vertical posts
  vertical while matching the tile-axis slope. It outputs `bridge-arch.png`,
  `bridge-near-rail.png`, `bridge-far-rail.png`, `bridge-metadata.json` and the
  authoring contact board `bridge-registration.png`. Binary alpha removes the
  rembg fringe. Source deck and perpendicular end wall are excluded; runtime
  geometry owns the floor and collision. Deck contacts are manually inferred
  within approximately three source pixels.
- `prepare-props.py` also rectifies a small masonry patch from the replacement
  bridge into `wall-material.png`; `wall-material.json` records the matrix.
  This supplies stair/slab face appearance, not physical geometry.
- `prepare-terrain.py` samples generated RGB into `terrain-atlas.png` and
  `terrain-frames.json`; `terrain-recipe.json` records crops, source hash, world
  phase, masks and limitations. It produces 64 by 32 opaque frame rectangles
  for the renderer's single diamond clip. Neighbor masks blend source colors
  across narrow, deterministically perturbed transitions. Water is sampled in
  screen space to preserve the generated stones' apparent proportions.
  `terrain-preview.png` is an authoring preview, not a game screenshot.
- `prepare-cliff.py` filters the preserved source crop to a 64 by 64 material
  and makes `cliff-atlas.png`: four 32 by 64 frames selected by `(c + r) modulo 4`.
  `cliff-recipe.json` records the source hash, crop, filtering and phase contract.
  Repeated cracks remain possible; the source is not proven seamless. Tile
  elevation determines collision.

The terrain catalog uses eight-cell phases for all water/shore families,
four-cell phases for other families and reflected source samples. The resulting
4,624-frame atlas is 4096 by 2336 pixels (approximately 7.59 MB).
Repetition can remain visible. Cardinal masks do not implement a 47-tile blob
catalog; three-material junctions prioritize shore transitions. These algorithms
assemble and mask source art rather than replace its material RGB with painted
patterns.

## Reused art and validation limits

`scene.ts` reuses `../../../demo/art/pixel-cafe/gardener-atlas.png` from the
existing runtime demo, with directional crops for idle, walking and jumping.
It was not newly generated for this autumn trial. See the runtime's
[existing provenance record](../../../PROVENANCE.md) for the parent asset context.

Water remains static; alpha silhouettes do not define collision and the visible
bridge arch does not provide a traversable underpass. The independent critic and
performance outcome are tracked in [the trial record](../../../docs/AUTUMN_CROSSING.md).
