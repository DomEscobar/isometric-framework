# Source lineage

This extraction starts from the Traviso-based engine in `Client/engine/traviso.js` in the AI-Pixel-World repository. The standalone implementation is rewritten into typed modules and a smaller scene/runtime contract. It is not a verbatim vendoring of that file or a compatible replacement for its full application API.

The source areas informing the extraction include these locations in the original checkout (line numbers are orientation aids and may move):

| Original source | Retained concept / treatment |
| --- | --- |
| `Client/engine/traviso.js`, around line 2915 | Isometric column/row projection and inverse tile picking; extracted into explicit geometry functions. |
| `Client/engine/traviso.js`, around lines 1838–2413 | Grid pathfinding and A*; reworked into a renderer-independent typed core. |
| `Client/engine/traviso.js`, around line 3491 and its occupancy helpers | Solid footprints, tile walkability, and occupied cells; represented with explicit scene/entity data. |
| `Client/engine/traviso.js`, movement/tween and rendering sections | Actor movement, depth ordering, and camera responsibilities; movement rewritten around elapsed seconds and runtime-owned state. |
| `Client/engine/move-handler.js`, `handlePress`, around line 152 | Original control orientation retained: W increases columns (northeast), D increases rows (southeast), S decreases columns (southwest), A decreases rows (northwest). Keyboard and mobile directional pad share this mapping. |
| `Client/components/panels/builder/` and application engine integration | Evidence of editor/application coupling; these UI modules are not dependencies of this package. |

The extraction introduces per-instance ownership, explicit destruction, a versioned JSON format, validation, and event-based gameplay integration. The demo's garden data, generated visual shapes, page, and collection rule are separate application examples. No existing bitmap asset pack is copied into this folder.

## Licensing

Example artwork remains in the source checkout with its own provenance records;
it is excluded from the consumer package.

This file records technical provenance, not a new grant of rights. Preserve the repository's applicable notices and review the original Traviso/upstream and repository licensing before redistributing or publishing a derived package. This extraction does not assert that original project code or assets are public domain or grant a license the repository has not established. Pixi.js and other installed dependencies retain their own licenses and notices.
