# Interactions and timed actions

`createInteractions` is a renderer-independent controller exported from the
package root and `/core`. It composes public runtime methods. Inventory, rewards,
permissions, and action definitions belong to the host game, outside scene JSON.

One controller owns one active action. Its sequence is `approaching → preparing →
recovering → idle`. It routes to a reachable tile beside the target footprint,
stops the actor, faces the target, optionally plays a directional clip, applies
one synchronous host effect, and recovers. Corner-only contact is excluded.
Actor and target must be grounded and stationary at the effect point, on the same
floor ID and at equal feet elevation by default. The controller option
`maxHeightDifference` accepts a finite nonnegative pixel distance for games that
allow vertical reach. It filters approach tiles and is checked again before the
effect; a reachable lower neighbor does not grant access to an arbitrarily high
target. Add other game permissions or reach constraints in `canPerform`.

```ts
import { createInteractions, type InteractionAction } from 'isometric-framework';

let flowers = 0;
const picking: InteractionAction = {
  id: 'pick-flower', prepareSeconds: .9, recoverSeconds: .45,
  // Optional: these names must exist in this game's scene.assets.animations.
  clips: { ne: 'pick-ne', se: 'pick-se', sw: 'pick-sw', nw: 'pick-nw' },
  canPerform: ({ target }) => target.data?.role === 'collectible',
  perform: ({ target }) => {
    // Claim the target before granting a reward; another actor may collect it.
    if (!runtime.remove(target.id)) return false;
    flowers++;
    return true;
  },
};
const actions = createInteractions(runtime, {
  onChange: state => updateActionHud(state), // Host UI function.
  onError: error => showError(error.message), // Host error handling.
});
actions.request({ actorId: 'hero', targetId: 'flower-1', action: picking });
// Cancel button / host scene-loading start:
actions.cancel('cancelled');
// Host teardown, before runtime.destroy():
actions.destroy();
```

`runtime` in the example is an already-created runtime. Use
`createRuntime({ container, scene, clickToMove: false })` when the host handles
`tileclick`: call `actions.request` for an actionable object, otherwise cancel
and `runtime.moveTo` to the clicked ground cell. This disables only automatic
click movement; picking, panning, zooming, and keyboard input remain available.
Without this option the runtime's default move would replace the action's route.
`demo/main.ts` is the complete Sunflower integration.

## Timing and cancellation contract

- Durations are simulation seconds, finite and in `[0, 3600]`. Pause freezes
  preparation, recovery, and sprite playback. No wall-clock timers are used.
- The movement frame reaching the interaction tile is not counted as preparation.
  Zero-duration phases still run on the next simulation frame. Large steps may
  cross both timed phases; use ordinary small frame steps for visible animation.
- Repeating the active actor/target/action ID is a no-op. Another request replaces
  it. Unreachable, airborne, or paused requests return `false`; malformed action
  definitions throw. There is no queue or cooldown after completion.
- An actor's external `moveTo`, non-neutral held input, `jump`, or `stop` cancels
  the action when the runtime accepts that command intent. Actor/target movement,
  removal, or invalidation is also checked on simulation frames.
- Cancel before the effect grants nothing. Cancel during recovery preserves the
  committed effect. `getState().effectApplied` records the last result when idle.
- Successful scene replacement cancels the old action without touching new-scene
  entities. Cancel explicitly **before** starting asynchronous scene loading if
  effects must stop during asset loading. Runtime destruction disposes subscriptions.
- `perform` and `canPerform` must be synchronous. `perform` is attempted at most
  once per accepted action and must return `true` after committing the effect.
  The controller cannot roll back side effects if a callback throws or returns
  false after modifying host state. It is not a network transaction or a lock
  shared by several controllers; host effects must claim shared targets atomically.
- Use one controller per actor for concurrent actors. Do not attach competing
  controllers to the same actor. Destroy controllers when replacing their host.

## Directional artwork

`clips` and optional `recoveryClips` map screen directions to named animation
clips. Approach sides use NE/SE/SW/NW. Missing entries leave automatic animation
alone (or retain the preparation override during recovery); explicit unknown
clips fail the action. Owned overrides are cleared on completion/cancellation.
Non-looping clips hold their last frame. The action's duration determines effect
timing, not an animation-complete callback.

`runtime.setFacing(id, direction)` sets visible facing without movement; later
motion may change it. It returns false for missing entities and built-in shapes.
Legacy sprites can retain direction metadata but need named directional clips to
visibly turn. Do not reach into renderer internals to set direction.

Apply the bundled [directional sprite skill](../skills/directional-sprite-authoring/SKILL.md)
when authoring poses. The Sunflower demo reuses existing grounded gardener frames
as a short gesture and reverse recovery. It does **not** contain newly drawn
hand-to-flower picking poses. Dedicated action artwork can replace those clips
without changing the controller or inventory rule.
