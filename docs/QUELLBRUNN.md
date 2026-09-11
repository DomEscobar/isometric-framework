# Quellbrunn: a village with authoritative ground

The user rejected the first version's mixed generated-object/procedural-ground
appearance after its initial review. The current host defaults to the
[generated terrain experiment](../examples/quellbrunn/terrain-trial/README.md),
with a **Boden: generiert / vorher** comparison. One generated ground plate supplies
24 registered map slices and the animated water material. The experiment has its
own focused plan and evidence; earlier whole-world receipts describe the first
version, not the current source.

The host is `examples/quellbrunn/`. Start it with:

```sh
node node_modules/vite/bin/vite.js --config examples/quellbrunn/vite.config.ts --host 127.0.0.1
```

Open http://127.0.0.1:4202/. The delivered village has five cottages, two gardens,
two bridges, three residents and a controllable traveler. Water surface patterns
travel along the channel; a wheel turns, chimney smoke rises, and trees sway
around their roots. Pointer/touch movement, four keyboard axes, pan, zoom and
pause are available. Doors are exterior destinations.

`world.ts` defines terrain support and actual building, garden, root and rail
footprints. Continuous terrain artwork is drawn from those world coordinates.
All supported dry ground outside solids is walkable, including the full road
width and open grass. Quarter-cell navigation has 22,536 connected positions;
that connectivity count alone does not prove the visible paths work.

The generated cottage, oak, pine and shrub have recorded source crops and
provenance. Five roof colours are variants of one original cottage. The initial
ground was authored; the current generated ground is registered to the same map.
Bridge structures, people and animation logic remain authored. The Canvas2D host consumes the public
headless pathfinder; no engine API was added or changed.

The independent image review identified flat figures, a roof obscuring the west
bridge, and a uniform bank rim. Repairs widened and shaded the figures, moved
the cottage clear of the crossing, and added earth/grass bank clusters. Later
inspection also required distinguishable back facings and mobile smoke evidence.

Verification is retained under `test-results/quellbrunn/`: version3 production
receipts, native images, dense motion sequences, full browser recordings and
comparison review. `tests/quellbrunn-browser.mjs` exercises nine road-width
samples, three off-road grass targets, both crossings in both directions, all
five doors, water/building/root/rail rejection, four keyboard axes and pixel-exact
pause at desktop and mobile viewport sizes. Browser timings include a blank
baseline. Emulated mobile viewports are not physical-device performance results.

The terrain experiment tested25 actual target arrivals per viewport, including
12 dry-bank points,9 path/grass points and4 full bridge traversals, plus water
rejection, pixel-exact pause and exact A/B return. Its24 slices reconstruct the
registered source with zero changed pixels. The generated water loop is22seconds;
the inspected crop returns exactly at its wrap and contains no classified grass
pixels. Native images, timed sequences and measured registration limits are kept
under `test-results/quellbrunn/ground-trial/`. Source registration still matters:
the model moved the outline and banks, requiring affine and local image correction.

The style reference remains the user's original forest image. This village has
less architectural variety and simpler character art than that reference; it
does not claim equivalent artistic richness, interiors, combat or stacked floors.
Formal receipts and independent review remain separate from the user's approval.
