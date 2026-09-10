# Directions and runtime binding

This runtime's names are screen compass directions. Rows in a sheet are not
interpreted automatically. The host explicitly maps cropped textures to ordered
clips and clips to directional states.

| Input / grid delta | Screen facing | Usual visible surfaces |
| --- | --- | --- |
| W / `(c+1,r)` | `ne` upper-right | Back and rightward silhouette |
| D / `(c,r+1)` | `se` lower-right | Front and rightward silhouette |
| S / `(c-1,r)` | `sw` lower-left | Front and leftward silhouette |
| A / `(c,r-1)` | `nw` upper-left | Back and leftward silhouette |
| W+D / `(+1,+1)` | `e` right | Right-facing profile |
| D+S / `(-1,+1)` | `s` down | Front |
| S+A / `(-1,-1)` | `w` left | Left-facing profile |
| A+W / `(+1,-1)` | `n` up | Back |

The last four rows describe motion vectors; actual routing/input can produce
different sequences when blocked. Test observable movement in the host. Up/down
on a 2:1 ground plane is not the same as a character turning its head upward.
Describe facing with screen travel, torso orientation, and visible surfaces in
the generation prompt. Camera orientation stays fixed.

Built-in demos use `diagonal: false` for click/tap paths, so their routed walking
steps select NE/SE/SW/NW. Combined held input remains a separate capability and
can request the other four directions. Do not enable diagonal click paths merely
to exercise eight-view artwork; preserve the game's chosen movement policy.

## Three layers of mapping

```text
input W -> movement c+1 -> facing ne
                          |
visual.animations.directions.ne.walk -> "ranger.walk.ne"
                          |
assets.animations["ranger.walk.ne"].frames -> texture IDs in time order
                          |
assets.textures[textureID].frame -> explicit rectangle in the sheet PNG
```

For example, a host may map `walk.ne` to row 3 or row 0; both work if that row
visibly contains NE frames and the rectangles match the image. Do not rename a
front-facing row to NE just to complete the matrix.

The automatic resolver checks directional state, then general state, directional
idle, general idle, and the base animation. Missing directional clips can therefore
silently show another facing or idle art. Declare the required matrix and check
it explicitly rather than treating absence of a runtime error as success.
The initial facing is SE and facing persists after movement stops. Use the public
`runtime.setFacing(id, direction)` to face a target without movement. Subsequent
movement can change it; do not call internal renderer methods from a host game.

For a four-view pack used with eight-way movement, choose explicit nearest-view
aliases only as a documented compromise and test their appearance. The packer
does not invent aliases. Do not count aliases as eight distinct authored views.

## Automatic and custom actions

The packer emits `assets` and `visualAnimations`. A host can use the generated
data with a named sprite after importing the actual PNG URL through its bundler:

```ts
import sheetUrl from './art/ranger/sheet.png?url';
import packed from './art/ranger/runtime.json';

const assets = {
  ...packed.assets,
  images: { ...packed.assets.images, ranger: { url: sheetUrl, sampling: 'nearest' as const } },
};
const visual = {
  kind: 'sprite' as const,
  animation: packed.visualAnimations.idle,
  animations: packed.visualAnimations,
  width: 64, // Chosen from this host's measured art contract, not a universal size.
};
// Set scene.assets = assets and scene.entityTypes.ranger.visual = visual.
// Preserve other host assets/types when merging an existing scene.
```

This example assumes `imageId: "ranger"` and that the spec includes idle clips.
Use the actual image ID. Do not set `visual.anchor` to a conflicting value: it
overrides the texture anchor. The image URL in generated JSON is relative and must
resolve in the deployed host, not merely beside the JSON file on disk.

Only idle/walk/jump belong in `visual.animations`. For a custom directional action:

```ts
const attackClip = packed.customActions.attack.ne;
runtime.setFacing(playerId, 'ne');
runtime.setAnimation(playerId, attackClip);
// Host action logic applies effects and tracks duration in simulation time.
// When the action ends or is cancelled:
runtime.setAnimation(playerId, null);
```

For actual play, the host chooses the action direction from its own movement or
aim state; the hardcoded NE above is only a binding example. An override selects
a fixed clip and does not automatically switch to other facing variants while
moving. Decide whether the action locks direction, permits motion, or is cancelled.
Do not use a wall-clock timeout that continues while the runtime is paused.
No public animation-complete event is supplied. Reissuing a non-null clip restarts
it; a `loop: false` clip holds its last frame until the host clears/replaces it.
Hit timing, reach, collision, and targeting remain host game rules.

For an approach-and-interact action, the reusable
[interaction binding](interaction-binding.md) supplies adjacent routing,
facing, preparation/recovery phases, cancellation, and one synchronous host effect.
Supply the generated `customActions` direction maps as `clips`/`recoveryClips`.
Its simulation timing still needs to match the visible poses; a passing effect
test does not prove the gesture looks like picking, attacking, or using a tool.

## Jump limitation

The automatic jump clip starts when flight begins; it is not phase-synchronized
to takeoff/apex/landing events. An arbitrary multi-frame clip can depict landing
too early or remain in an apex pose after its final frame. A single readable
airborne pose is the safest first slice, with motion supplied by the runtime.
If multiple phases are needed, explicitly coordinate host action timing with
simulation flight, or implement a separately scoped runtime capability; do not
claim that a new spritesheet alone adds that synchronization.
