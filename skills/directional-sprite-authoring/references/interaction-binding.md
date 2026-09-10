# Bind a timed directional gesture

Use `createInteractions` when the host needs approach, facing, a preparation
gesture, one synchronous effect and recovery. The example assumes an existing
runtime, target and actor, plus host-authored clips with the declared IDs.

```ts
import { createInteractions, type InteractionAction } from 'isometric-framework';

const action: InteractionAction = {
  id: 'use-object', prepareSeconds: 0.5, recoverSeconds: 0.25,
  clips: { ne: 'use-ne', se: 'use-se', sw: 'use-sw', nw: 'use-nw' },
  canPerform: ({ target }) => target.data?.role === 'usable',
  perform: ({ target }) => applyHostEffect(target.id), // Synchronous boolean.
};
const actions = createInteractions(runtime);
actions.request({ actorId: 'actor', targetId: 'object', action });
// Cancel before host scene loading or when an explicit cancel input occurs:
actions.cancel('cancelled');
// At host teardown:
actions.destroy();
```

Replace durations with measured pose timing; these illustrative numbers are not
an animation contract. Supply `customActions` direction maps from the packer as
`clips` and optional `recoveryClips`. Unknown clip IDs fail; missing directions
can leave automatic animation in place, so they need an explicit coverage check.

The controller approaches an adjacent reachable cell, faces the target, prepares,
applies the effect and recovers. Durations use simulation seconds; pause freezes
both phases and sprites. Effect timing comes from the action duration, not an
animation-complete event. Non-looping clips hold their last frame. Owned overrides
are cleared on completion/cancellation.

Use `clickToMove: false` when the host routes its own `tileclick` actions; otherwise
automatic click movement can replace the approach. Default effect eligibility
requires stationary, grounded participants on the same floor at equal feet height.
Host permissions and effects remain host rules. Cancellation before the effect
grants nothing; cancellation during recovery does not undo a committed effect.

Observe each required direction through approach, full gesture and recovery.
An effect counter passing does not show that the pose reads as the requested action.
