# Inspecting an isometric game

The optional `createDebugOverlay` helper is exported from the package root. It
reads the public `runtime.getDebugSnapshot()` API and has no Pixi dependency.
Keep diagnostics behind an authoring toggle in the host UI.

```ts
import { createDebugOverlay } from 'isometric-framework';

// runtime is ready; container is the same element containing its canvas.
const debug = createDebugOverlay(runtime, { container, panel });
debug.setEnabled(true); // Initially off, including the panel.
debug.refresh();        // Explicit refresh after a paused authoring mutation.
// Host teardown (runtime.destroy also disposes the helper):
debug.destroy();
```

Give the panel its own layout space. The SVG is noninteractive and covers the
canvas without intercepting pointer input. Snapshots and overlay geometry use
canvas-local CSS pixels, the current camera, and absolute surface/feet elevations.
Frame refreshes are throttled to ten per simulation second; camera, view-floor,
pause, and scene changes refresh immediately, including while paused.

| Display | Meaning |
| --- | --- |
| Cyan diamonds and coordinates | Visible floor tiles and their grid coordinates |
| Red outlines | Blocking entities' committed rectangular occupancy |
| Yellow line | Selected actor's current planned walking route |
| Green cross and dashed box | Selected sprite's actual origin and full image-frame bounds |
| Readout | Committed cell/floor, continuous pose, body height, facing, state, clip, frame, named texture, override, anchor, route |

Select an entity from the panel. Compare the gardener's feet with the green
origin, rigid props with red footprints, and action clips with the facing readout.
Use this with close-up screenshots and the art integration skill: metadata does
not prove that visible artwork aligns or has convincing proportions.

The snapshot is detached data. Changing it cannot move an actor or alter art.
It is a diagnostic contract, not a scene save: use `serializeScene()` for saves.
The overlay does not simulate collision, edit assets, or repair artwork.

Limits: the grid is capped at 2,000 tiles; image bounds include transparent margins;
built-in shapes have no sprite-frame metadata; occupancy stays at committed cells
during motion/flight. Routes are recalculated against current occupancy and are
not a movement history or jump trajectory. This first overlay is intended for
small authoring maps, not a performance profiler or a full level editor.
