---
name: directional-sprite-authoring
description: Author directional character poses and animation frames from images or video, map them to this isometric runtime, and verify facing, frame contacts, and playback. Use for turnarounds, walk/jump/attack sprites, video-to-sprite extraction, or incorrectly facing characters.
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
For generated character walks, approve a neutral character view in each requested
direction before animating it. A mannequin supplies poses, not character identity.
For the two-template SE/NE workflow, establish SE, derive and review NE from that
approved character, then pair each view with its matching mannequin as described
in [walk templates](references/walk-templates.md#establish-the-character-before-animation).
Reuse existing approved views instead of regenerating them. Identify front/back from
face/chest versus back/pack, and left/right from the nose, torso, and feet together.
An arrow or filename is a label, not evidence. Reject or relabel a misfacing
candidate based on what it visibly depicts; never rotate the controls to fit it.

Do not mirror asymmetric equipment, change the weapon hand, or rotate a standing
sprite in 2D to synthesize a new camera view. Mirroring also changes light direction.
Any intentional reuse must preserve the art contract and be recorded as reuse,
not counted as an independently drawn direction.

## Generate poses against approved references

Use the project's selected production route: authored frames, generated strips,
individual poses, or [video-derived frames](references/video-to-sprites.md).
For generated animation, start with the approved character view; use a matching
pose or motion reference when that route calls for one. Generate one directional
animation candidate, visually inspect its frames and playback, repair diagnosed
defects, and recheck before acceptance. Reuse existing approved frames or a supplied
video instead of generating again. A motion-reference video is optional, and does
not guarantee exact output poses or timestamps.
Do not plan around getting a finished walking sheet in one request. Generating
frames separately also requires checking consistency across the assembled clip.
Check one action in one direction before requesting a whole matrix.

For a four-frame walk animation, the optional bundled
[NE and SE mannequin templates](references/walk-templates.md) provide isolated
pose references. Use them when their proportions and camera fit the character;
they are guidance, not proof that generated frames animate correctly.

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
frames in the review record. Include them in a repair request only as explicitly
identified edit targets, alongside the approved pose and identity references.

Define [action phases](references/poses.md) before generating: walk
contact/pass/opposite contact/pass; attack anticipation/strike/recovery; jump pose
appropriate to the current runtime.
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
correction. Repair the smallest affected region or frames against the approved
pose and identity references, preserving accepted pixels where possible. A failed
candidate may be the edit target, but must not become the new pose/identity
authority. Reassemble and recheck the whole clip after every repair or cleanup,
including previously accepted frames and transitions. Keep before/after images
and playback evidence. Stop within the agreed repair budget; a repeated defect
without a new diagnosis requires revising the approach, not another blind retry.
Unresolved facing, anatomy or gait failures block acceptance and further matrix
expansion. Template-specific checks are in the
[walk-template review loop](references/walk-templates.md#visual-check-and-repair).

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
