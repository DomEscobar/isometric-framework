---
name: directional-sprite-authoring
description: Generate character facings and derive character animation through image-to-video, reviewed frame extraction and packing. Map clips to this isometric runtime and verify facing, contacts and playback. Use for turnarounds, walk/jump/attack clips, or incorrectly facing characters.
---

# Directional sprite authoring

A spritesheet stores pixels; the manifest selects their meaning. Correct labels
and complete clips cannot establish that the drawn character actually faces the
declared direction. Approve both the visible pose and its runtime mapping.

Follow the central [production asset policy](../isometric-visual-loop/references/asset-policy.md).
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
For a static idle, a generated neutral view in each required direction is enough
when no animated idle was promised. For any character motion, first approve a
generated T2I or I2I character-facing image for that direction. Record the actual
local source, provider job or request ID, submitted references and its approval;
never fabricate provider parameters or replace that record with a description.
Reuse accepted generated views with their provenance instead of regenerating them.
Identify front/back from
face/chest versus back/pack, and left/right from the nose, torso, and feet together.
An arrow or filename is a label, not evidence. Reject or relabel a misfacing
candidate based on what it visibly depicts; never rotate the controls to fit it.

Do not mirror asymmetric equipment, change the weapon hand, or rotate a standing
sprite in 2D to synthesize a new camera view. Mirroring also changes light direction.
Any intentional reuse must preserve the art contract and be recorded as reuse,
not counted as an independently drawn direction.

## Produce character motion from an approved facing image

Character motion has one production route: approved generated character-facing
image (T2I or I2I), then image-to-video, review of the actual video, deterministic
[video extraction](references/video-to-sprites.md), deterministic packing, and
runtime review. Direct generated sheets, individual generated gait/action frames,
and authored character-animation frames are not production alternatives. Editing
masks or crops is allowed; synthesizing replacement motion poses is not.

Before spending, confirm that an approved image-to-video tool can actually submit
the proposed input. If budget, access, or a capable approved tool is missing, stop
and record the blocker. Do not pretend that an image client can submit video.
Use the approved facing image as the identity input and record the actual image
file/hash and provider request details. A motion guide is optional and must have
its role and provenance recorded. Keep camera, lighting, body proportions, and
root stable. Check one action in one direction before requesting a whole matrix.

Review the actual returned video before extraction for facing, identity, anatomy,
stationary root, alternating contacts, stable camera, and a usable loop interval.
Treat phase plans as requested motion semantics, not evidence that a clip contains
those phases. Reuse an accepted generated video only with its source provenance.

When passing exact crops to a provider, use the offline request bundle described
by [game asset generation](../game-asset-generation/references/request-preparation.md).
For a directional action matrix, its calibration receipt ties the reviewed probe
to the currently selected approved identity source hashes. It records a
self-reported judgement and does not prove visible facing or animation quality.

Generate each direction's action video from its approved neutral view and the same
master identity. Avoid chains where each unreviewed generation becomes the next
reference: errors in scale, anatomy, and equipment accumulate. Keep the camera,
lighting, body proportions, and root stable throughout the motion.

Define [action phases](references/poses.md) before generating: walk
contact/pass/opposite contact/pass; attack anticipation/strike/recovery; jump pose
appropriate to the current runtime.
These are phase plans for the I2V request and review, not claims that a request
will produce smooth motion. Expand frames only through a newly reviewed video.

## Normalize and assemble accepted frames

Measure one shared crop window across the decoded video frames. Reject windows
that cut through the body or include other subjects. Alpha-bounds cropping cannot
recover discarded pixels or separate overlapping subjects. Do not derive the
character's scale/root independently from each changing silhouette.

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

For already normalized extracted frames, use the deterministic
[sheet packer](references/packing.md). It copies pixels into equal cells and emits
explicit clips; it never resizes, trims, rotates, mirrors, guesses directions, or
creates missing poses.

For video, the [extraction helper](references/video-to-sprites.md#prepare-and-export)
records actual decoded timestamps and applies one explicit crop and mask across
selected frames. Cycle suggestions and filenames are not facing or gait evidence.
Keep extraction settings in its recipe and derive the packer input from that recipe.

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

Visual review is an acceptance gate, not an optional report. Open the actual
reference/candidate comparison and observe at least two complete playback cycles
at the intended speed, including the loop seam. If playback cannot be inspected,
mark motion unverified; do not certify it from a contact sheet or script results.

A smaller multimodal reviewer can inspect numbered reference/frame comparisons
for bounded checks such as facing or obvious mask damage. Require frame IDs,
visible evidence, and `pass`, `fail`, or `uncertain`; do not replace visual playback
with confidence scores or a general "looks good" judgement. Route ambiguous gait,
anatomy and seam findings to further review. Technical checks and reviewer verdicts
remain separate; neither automatically establishes the other's result.

For each failure, record the affected frames, visible defect, and intended
correction. Mask and crop cleanup may repair the smallest affected extraction
region while preserving accepted pixels. Do not synthesize new motion poses in
extracted frames: a facing, anatomy, gait or phase defect requires a newly reviewed
I2V candidate from the approved facing image. Reassemble and recheck the whole clip
after every cleanup, including previously accepted frames and transitions. Keep
before/after images and playback evidence. Stop within the agreed repair budget; a
repeated defect without a new diagnosis requires revising the approach, not another
blind retry.
Unresolved facing, anatomy or gait failures block acceptance and further matrix
expansion.

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
