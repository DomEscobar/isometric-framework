# Runtime art binding

This illustrative manifest assumes the current host supplies a 64×48 PNG with
two measured 32×48 frames. It supplies no artwork or art direction. Replace the
dimensions, contacts, IDs and URL with the host's actual assets.

```ts
import { validateAssetManifest } from 'isometric-framework/art';

const assets = validateAssetManifest({
  images: { actor: { url: '/art/actor.png', sampling: 'nearest' } },
  textures: {
    'actor-0': {
      image: 'actor', frame: { x: 0, y: 0, width: 32, height: 48 },
      anchor: { x: 0.5, y: 0.875 },
    },
    'actor-1': {
      image: 'actor', frame: { x: 32, y: 0, width: 32, height: 48 },
      anchor: { x: 0.5, y: 0.875 },
    },
  },
  animations: {
    step: { frames: ['actor-0', 'actor-1'], fps: 8, loop: true },
  },
});
// Assign assets to scene.assets; a host entity type can select:
const visual = { kind: 'sprite' as const, animation: 'step', width: 32 };
```

The example anchor places the contact at `(16,42)` in each frame. A shared number
does not establish shared feet: measure actual contacts before using it. Two
frames demonstrate binding only; judge the required movement through playback.

- Frame rectangles use integer source pixels from the upper-left. Omit `frame`
  to use the whole image. Rotated/trimmed third-party atlas metadata needs explicit
  conversion; the runtime does not infer a generated grid.
- URLs resolve against the host document. With Vite, import host-local artwork
  using `?url` so the build supplies the deployed URL. Scene serialization retains
  references, not image bytes. Keep the source and deployed paths valid.
- `visual.anchor` overrides the texture anchor. Otherwise named textures default
  to their declared anchor, with bottom-center `(0.5,1)` when omitted.
- Effective render scale is `(visual.width / frame.width) * visual.scale`, with
  omitted factors treated as 1. Render size does not change the grid footprint
  or an explicit physical `bodyHeight`.
- A local grid displacement projects to `x=(dc+dr)*tileWidth/2` and
  `y=(dr-dc)*tileHeight/2-height`. Sprite offsets change pixels, not occupancy or
  depth origins. Correct the assembly position when its contacts belong elsewhere.
- Terrain clips its material to a diamond; entity sprites keep their own alpha
  silhouette. Do not reuse an opaque terrain rectangle as an animated overlay
  without preparing the required transparency.
- Named clips default to 8 FPS and looping. `loop: false` holds the last frame.
  Simulation time advances sprites and pause freezes them. Direction/action maps
  are covered by the [directional skill](../../directional-sprite-authoring/SKILL.md).

Manifest validation checks metadata; the loader checks image bounds. Neither
establishes facing, anatomy, contacts or visual compatibility. Use the calibration
contract and rendered checks on the delivered host.
