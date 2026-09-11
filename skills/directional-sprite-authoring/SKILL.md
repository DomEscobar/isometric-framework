---
name: directional-sprite-authoring
description: Author directionally consistent character poses and action spritesheets from reference images, map them to this isometric runtime, and verify facing, frame contacts, and action playback. Use for turnarounds, walk/jump/attack poses, or incorrectly facing animated characters.
---

# Directional sprite authoring

A spritesheet stores pixels; the manifest selects their meaning. Correct labels
and complete clips cannot establish that the drawn character actually faces the
declared direction. Approve both the visible pose and its runtime mapping.

Use [game asset generation](../game-asset-generation/SKILL.md) for provider jobs,
background removal, alpha inspection, and provenance. Use
[isometric art integration](../isometric-art-integration/SKILL.md) for projection,
physical scale, and in-game acceptance. This skill adds the directional pose and
animation workflow; it does not create combat rules or change movement axes.

## Establish identity, facing, and action coverage

Read [directions and runtime binding](references/directions.md) before naming any
frame. W is NE, not screen-up. Record the required directions and actions before
generation. Four tile-axis directions are enough only when other movement/facing
directions are intentionally excluded or explicitly mapped as visual compromises.

Choose an approved character reference: proportions, clothing, palette, equipment
hand, asymmetric details, lighting, camera elevation, canvas, and display scale.
Generate and review neutral NE/SE/SW/NW views first. Identify front/back from
face/chest versus back/pack, and left/right from the nose, torso, and feet together.
An arrow or filename is a label, not evidence. Reject or relabel a misfacing
candidate based on what it visibly depicts; never rotate the controls to fit it.

Do not mirror asymmetric equipment, change the weapon hand, or rotate a standing
sprite in 2D to synthesize a new camera view. Mirroring also changes light direction.
Any intentional reuse must preserve the art contract and be recorded as reuse,
not counted as an independently drawn direction.

## Generate poses against approved references

Use the project's selected provider and its reference workflow for repeated poses.
The [Seedream pose recipe](references/poses.md) is one optional implementation,
not a provider selection rule. Reference editing does not prove animation
coherence or exact facing.
Check one action in one direction before requesting a whole matrix.

When passing exact crops to a provider, use the offline request bundle described
by [game asset generation](../game-asset-generation/references/request-preparation.md).
For a directional action matrix, its calibration receipt ties the reviewed probe
to the currently selected approved identity source hashes. It records a
self-reported judgement and does not prove visible facing or animation quality.

Derive each direction's action poses from its approved neutral view and the same
master identity. Avoid chains where each unreviewed generation becomes the next
reference: errors in scale, anatomy, and equipment accumulate. Keep the camera,
lighting, body proportions, and root stable while changing the pose.

When approved and rejected poses share a sheet, supply only the approved crops
as identity references. For example, if the neutral row passed but the walk rows
repeat one leading foot, isolate the neutral views before requesting new contacts;
do not send the failed rows with an instruction to ignore them. Keep rejected
frames in the review record, outside the reference inputs for the next attempt.

Define action phases before generating: walk contact/pass/opposite contact/pass;
attack anticipation/strike/recovery; jump pose appropriate to the current runtime.
These are phase plans, not claims that isolated generated images form smooth
in-between motion. Expand frames only when the intended playback needs them.

## Normalize and assemble accepted frames

Measure crop windows on the decoded source. A requested equal grid does not prove
the returned sheet has equal pose spacing. Reject windows that cut through bodies
or include neighboring boots, hands or heads. Alpha-bounds cropping after a bad
grid split cannot recover discarded pixels or distinguish a neighboring subject.
Do not derive the character's scale/root from a contaminated crop bounding box.

Preserve original candidates. Remove backgrounds and review masks separately.
Normalize approved frames to a common canvas and root using measured landmarks;
never auto-fit each silhouette. A raised sword, extended leg, or crouch must not
cause the whole character to shrink or its anchor to jump. Keep the same source
pixel-to-world scale across actions, and leave room for their widest silhouettes.

The root is the entity's local origin before runtime translation/elevation.
For a planted pose, foot contact helps establish it; for crouching or raised feet,
retain the coherent body/root relationship. Do not re-anchor each airborne frame
to its lowest painted foot. Runtime jump elevation already supplies flight, so
do not also bake a full upward flight path into frame positions.

For already normalized frames, use the deterministic
[sheet packer](references/packing.md). It copies pixels into equal cells and emits
explicit clips; it never resizes, trims, rotates, mirrors, guesses directions, or
creates missing poses. A generated full sheet can also be used, but its actual
cell boundaries/order must be measured and visually classified rather than
inferred from a requested row layout.

## Verify the matrix and play it

Use the [decoded packed-art inspector](../isometric-visual-loop/references/acceptance.md)
on the actual runtime manifest, including every used idle, movement and custom
action clip. Inspect its shared-scale preview and animate the packed frames, not
only the raw sheet. Component/margin checks catch common crop failures; they do
not establish anatomy or true foot contact. Missing directional motion remains
open work; a static fallback does not satisfy a promised walking cycle.

Compare each clip at native scale and the host's intended display size. Inspect
every frame and the loop seam for facing changes, identity drift, swapped hands,
foot/root drift, halo damage, and apparent scale changes. Frame-by-frame review
and playback catch different defects; preserve both forms of evidence.

In the host scene, move along all required axes and release to idle. Test jumping
only when it is supported and included in the requested action coverage.
Check movement vector, visible facing, selected clip, and stable contact together.
For eight-way play, test combined directions as well as WASD. Show front/behind
occlusion and an asymmetric prop to make accidental mirroring visible.

Automatic states are only idle/walk/jump. Custom attack/cast/interact clips use
host-owned animation overrides and action timing, as explained in the runtime
binding reference. A non-looping clip does not create a hit, stop motion, emit an
action-complete event, or automatically restore idle.

Report packing/manifest validity, visible facing, motion continuity, and gameplay
binding separately. List exact directions/actions/frames checked, intentional
fallbacks, and unverified states. A complete JSON matrix cannot certify anatomy
or pose direction. Keep jobs, hashes, normalized-frame provenance, the packing
spec, and the host's accepted display scale with the art pack.
