# Quellbrunn

A complete small village built from authoritative playable geometry: five cottages,
two gardens, two bridges, a winding stream and three walking residents.

The current host includes the [generated-ground experiment](terrain-trial/README.md).
Use **Boden: generiert / vorher** for the direct comparison; generated ground is
the current default. Earlier full-world receipts describe the previous source.

```sh
node node_modules/vite/bin/vite.js --config examples/quellbrunn/vite.config.ts --host 127.0.0.1
```

Open http://127.0.0.1:4202/. Click/tap dry ground to walk, use WASD/arrow keys,
drag to look around, and use the wheel or + / − to zoom. **Dorfrunde** crosses
both bridges; **Pause** freezes characters and scenery. Roofs and trees fade
when they obscure the player. House doors are exterior destinations, not interiors.

The host uses the framework's public headless pathfinder. Its Canvas2D renderer,
continuous terrain materials, water flow, wheel, smoke, authored character poses
and resident schedules are host-owned. No engine API changed.

`world.ts` owns land, stream, solid footprints and supported decks. Every dry
supported location outside solids is eligible for walking; painted road centrelines
are not navigation corridors. `export-layout.mjs` emits the semantic review data.
`art/binding.json` supplies the measured rigid sprite transform used by the renderer.

The original generated cottage, oak, pine and shrub are recorded in `art/provenance.json`.
Five cottage colour variants share one original building design; they are not five
independently generated buildings. The raw generation is preserved in `art/source.png`.
Terrain, bridge, character and animation pixels are authored, not generated.

Build: `node node_modules/vite/bin/vite.js build --config examples/quellbrunn/vite.config.ts`.
Type check: `node node_modules/typescript/bin/tsc --project examples/quellbrunn/tsconfig.json --noEmit`.
Browser checks: `node tests/quellbrunn-browser.mjs` with production preview on 4203.
Evidence and acceptance receipts remain under `test-results/quellbrunn/`, outside source.

This is an original village layout guided by the user's forest image's material
integration, not a replica. Character art and architectural variety are simpler
than that reference. It has no combat, interiors, overlapping floors or physics simulation.
