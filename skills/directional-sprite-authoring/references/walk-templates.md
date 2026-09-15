# Four-frame mannequin walk templates

Use these optional pose references for characters compatible with the mannequin's
bipedal gait and isometric camera. Other body plans or actions need suitable poses.

| Template | Screen travel | Source row (one-based) |
| --- | --- | --- |
| [walk-ne.png](../assets/walk-templates/walk-ne.png) | Upper-right, rear three-quarter | 2 |
| [walk-se.png](../assets/walk-templates/walk-se.png) | Lower-right, front three-quarter | 1 |

Each transparent PNG is 512 × 128 pixels: four 128 × 128 cells, ordered left to
right. Preserve this order and the common canvas. The blue and peach limbs help
track opposite limbs; they are not the target character's palette. These are
user-selected pose templates, not accepted runtime animations or character art.
Crop provenance and hashes are in [provenance.json](../assets/walk-templates/provenance.json).

## Establish the character before animation

1. Establish one neutral character facing SE (bottom-right, front three-quarter).
   When matching a supplied style, attach that style image to the selected
   reference-edit workflow and specify character design and SE facing separately.
   The style reference supplies pixel treatment, palette and materials, not its
   subject or layout unless requested. Inspect and repair identity, anatomy,
   camera and facing before accepting this character master.
2. Derive a neutral NE view (top-right, rear three-quarter) of that same approved
   character. Review it beside SE for proportions, palette, equipment, lighting
   and actual facing. Repair and approve it before starting the walk strips.
   Reuse either view if it is already approved; do not regenerate it for ceremony.
3. Generate and review one directional walk at a time using the pairs below.
   Finish the visual check and repair loop for the first strip before expanding.

| Walk candidate | Appearance reference | Pose reference |
| --- | --- | --- |
| SE | Approved SE character | SE mannequin strip |
| NE | Approved NE character | NE mannequin strip |

"Right" alone is ambiguous: SE is bottom-right; E is a different screen direction.
Provider selection stays in the asset-generation workflow. Choosing a different
provider does not change these character, facing and motion acceptance steps.

## Use one direction at a time

Attach the actual matching character view and mannequin strip. The character
controls identity and appearance; the mannequin controls the four poses and
camera. Do not substitute an SE character image for the approved NE view in an NE
walk request. Inspect the result rather than assuming the prompt resolves
conflicting references.

Example for the NE strip:

Replace the illustrative ape identity below with the project's approved character.
The two images must agree on camera elevation and body proportions before this
request; resolve incompatible references instead of asking the model to guess.

> Image 1 is the approved NE character: preserve this exact ape's identity,
> proportions, fur palette and pixel treatment. Image 2 is the NE mannequin strip:
> it controls all four poses, camera, limb placement and frame order.
> In every frame the ape walks diagonally toward the upper-right of the image,
> away from the viewer, with its back visible. Keep the same facing throughout.
> Preserve the alternating leg poses, including the opposite contacts in frames
> 1 and 3. Replace the blue/peach guide colors with the ape's consistent fur
> palette. Produce one row of four equal cells with a stable character scale and
> root placement. Transparent background; no white fill, checkerboard, labels or
> ground. Do not add views or frames.

For SE, use the approved SE character as image 1 and the SE strip as image 2.
Change NE to SE in the reference descriptions and change the direction sentence to:
"In every frame the ape walks diagonally toward the lower-right of the image,
toward the viewer, with its front visible." Adapt the appearance to the project.

## Visual check and repair

Follow the skill's required visual review and repair loop before accepting a strip:

1. Open the mannequin and generated frames side by side at a shared scale. Check
   facing in every frame, then trace each leg through frames 1 and 3: the opposite
   leg must lead, rather than the same silhouette being recolored. Check the
   passing poses, arm swing, anatomy, character identity and root placement too.
2. Play the assembled strip for at least two cycles at the intended speed and
   display size. Inspect weight transfer, foot sliding, scale changes and the
   4-to-1 transition. Step through frames to diagnose a visible hitch.
3. Name the failure precisely, for example: "Frame 3 repeats frame 1's leading
   leg; match template frame 3's opposite contact while preserving the approved
   torso, facing and scale." Attach the relevant pose crop when repairing.
   Correct local failures locally; a wrong direction across the strip needs a
   corrected directional request within the remaining generation budget.
4. Compare before/after and replay the entire repaired strip. Background cleanup
   also requires rechecking hands, feet and outlines against contrasting colors.
   Save the comparison, playback evidence, and pass/fail or unverified verdict
   with the candidate. Do not expand to another direction until this probe passes.

Requested cell sizes and transparency are not guarantees: measure the returned
sheet and inspect its decoded alpha. A painted checkerboard is a background, not
transparency. Bind only reviewed frames to runtime clips and then verify movement
in the host. These two references do not supply other directions automatically.
