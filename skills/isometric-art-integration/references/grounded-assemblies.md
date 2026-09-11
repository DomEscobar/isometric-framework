# Connect scenery to its ground

Use when placed objects look pasted on, or a reference calls for a continuous
landscape. These examples are illustrative; use the current project's own art,
materials and scale. Crisp pixel clusters can create a flowing transition without
blur, gradients or extra noise.

## Design the contact zone together

An asset's anchor solves placement. Its contact zone explains why it belongs there.
Record the relevant treatment in the existing brief, not another contract:

| Assembly | Physical support | Visible connection |
| --- | --- | --- |
| Tree on a grassy bank | Trunk/root origin lies on supported planting ground | Roots enter exposed earth; nearby tufts and a restrained shadow join the lawn. |
| Building beside a trail | Foundation and doorway meet their reserved ground | Foundation shadow, sparse growth at the base and worn approach connect to the threshold. |
| Stream with a crossing | Shared banks bound the water; deck has actual walking support | Wet edge, exposed bank and grass lip form a continuous cross-section; deck meets both landings. |

Choose one representative assembly with the actor. Compose its quiet ground,
transition and object before producing a whole family. Match pixel cluster size,
outline weight, palette/light and stylized proportions at actual playing zoom.
Different materials need different treatment; uniform speckles are not variety.

## Separate layers only where behavior needs it

- Ground owns soil, wear, low grass transitions and contact shadows. Retain these
  in a ground-only view; they are not optional clutter concealing bad geometry.
- The object owns its solid or upright part, with measured contact and occupancy.
- Foreground roots, grass or rails are separate only when an actor must pass
  between them or the art needs another depth order. Moving foliage keeps its
  planted base fixed.

A generated contact patch or small composed assembly can supply these layers.
An isolated portable prop may instead use a separately authored ground treatment.
Do not trim away intended root/earth pixels merely to obtain a pristine cutout.
Do not bake walkable decks or foreground structures into a single ordinary sprite
and assume a nonblocking flag will make actors draw above it.

A flush, static bridge top may remain in a composed ground surface when the host
provides matching walking support, draws actors above it, and excludes it from
moving-water masks. It does not need a separate cutout solely because it is a
bridge. Raised decks, rails and overhangs still need the depth/support treatment
their behavior requires. Verify near, middle and far crossing poses either way.

Join patches to the surrounding material with irregular, deliberate cluster
boundaries and a shared world origin. Avoid identical oval dirt pads under every
tree, double shadows, rectangular patch seams and repeated border stamps. Keep
the usable route clear; visual fringe must not promise unsupported walkable land.

## Approve the connection in the game

Compare the reference, current patch and previous capture at comparable playing
scale. Ask where the object's base meets the terrain and whether the transition
is readable without a grid overlay. Inspect the same area with upright props
hidden, then dressed with the actor present.

Physical and visual verdicts are separate. Reject floating foundations even if
grass hides the gap, and pasted-on scenery even if its coordinates are valid.
For a crossing, inspect the actor's full lower body and feet on the near, middle
and far deck and both landings. For an interaction, inspect its actual idle/action
endpoint from the relevant reachable approach sides. A completed action with the
actor wholly concealed is a failed view, not a successful visual interaction.

Use these poses in the existing comparison/evidence set. Do not add a parallel
review system or regenerate unrelated art. Expand after the contact zone works;
additional props and ambient animation cannot compensate for a failed connection.
