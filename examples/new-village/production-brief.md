# Larkspur Crossing: current scope

The playable host is a compact original village with four exterior buildings,
a connected path junction, a curved stream, one usable crossing, planted margins
and one controllable traveler. Interiors, combat and inventory are outside scope.

`reference/style.jpg` is the original protected **style reference**, not a layout
to copy or an asset sheet. It informs clustered pixels, warm worn paths, foliage,
ground contacts and bank transitions. The village uses its own layout and artwork.
Do not silently replace the reference with a screenshot of the current host.

The chosen technique is a composed generated ground plate, bound through public
tile textures, with separately generated scenery and authored animation processing.
Nine built-in image-generation calls were used in the original trial; this history
does not authorize further generation or a provider change. All runtime images and
the compact source provenance are local to this example.

`layout.json` owns routes, planting, building footprints, entrance approaches and
bridge support. Four 2x2 buildings have reachable exterior thresholds. The bridge
is a flush three-cell deck in the ground surface, without an underpass or raised
rail promise. Trees must keep their roots outside reserved circulation.

The traveler uses four body facings with source-derived walking contacts at 8 fps;
movement is 1.1 cells/second. A clipped water overlay must flow inside fixed banks,
and restrained leaf motion must leave roots fixed. Pause must freeze the scene.
These bindings exist; their complete temporal and aesthetic acceptance remains open.

The migration browser check in `tests/new-village-browser.mjs` covers the four
entrances, both crossing directions, desktop mouse/mobile touch input and pause.
Its captures require actual inspection. Packed-art checks establish file/clip
structure, not anatomy, compatible style or convincing movement.

Remaining acceptance work is the complete visual comparison with the protected
reference, contextual walk/water/leaf motion review, and performance assessment.
Keep executed evidence under the repository's ignored `test-results/new-village/`.
Historical trial receipts do not certify this relocated host or a changed baseline.
