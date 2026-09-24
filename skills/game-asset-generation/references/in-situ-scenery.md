# Scenery objects on an approved plate

Use this for trees, wells, houses and other upright scenery that must sit on an
approved ground plate whose cell layout is already frozen. Generate the objects
onto that plate, isolate each instance with segmentation, then bind it to the
runtime as its own sprite. The plate remains owned by composed ground or another
accepted terrain route; this is not a second ground pipeline.

## Why the plate comes first

Segmentation cuts pixels out; it does not reconstruct what they covered. Cutting
a house out of one generated full scene leaves a hole in the ground behind it,
and the repaint would be unreviewed art. Editing objects onto an approved plate
keeps the original plate intact under every object. A full-scene generation with
extracted objects is still possible as layered scene artwork, but only with its
own reviewed plan for the hidden ground.

## Preconditions

- An approved plate image at delivery size, with provenance under the
  [asset policy](../../isometric-visual-loop/references/asset-policy.md).
- Frozen host cells for every object in the same projection as the plate:
  one cell for a tree or well, the complete footprint for a building. A padded
  sprite frame is not a footprint.
- For buildings, bridges and other multipart structures, a blueprint from
  [multi-tile assembly](../../multi-tile-asset-assembly/SKILL.md): footprint,
  solid volumes, door or passage cells and depth parts. Segmentation supplies
  pixels for those parts; it does not decide collision or the depth split.
- A style authority or prompt that matches the plate's materials and light.
- A budget and an approved edit provider that accepts the plate as an image
  input, plus an approved segmentation provider such as WaveSpeed
  `wavespeed-ai/sam3-image`. Missing access or budget is a blocker, not a silent
  paint-in.

Collision and walk support stay host-owned from the frozen layout. Do not derive
them from the painted result or from mask outlines.

## Mark feet, then edit

On a working copy of the plate, draw a small numbered marker at the projected
foot of each single-cell object and outline each building footprint. Keep the
unmarked plate as the production original.

Prompt the edit so each numbered marker becomes exactly one named object whose
base locks to that marker or footprint. One object per marker; no extras, merges
or relocated feet. Record the submitted marked plate hash, prompt, model and
prediction identity, and download the edited plate.

Inspect the returned edit for invented elevation, blocked approaches and objects
that drifted off their markers before segmenting. Preserve failures and revise the
conflicting constraint instead of cropping misplaced silhouettes into place.

## Segment instances, then assign with a reviewer

Text prompts often return one mask per class, not per instance. Collect every
connected candidate above a minimum pixel count. Do not decide identity from
color, size, filename order or spatial heuristics; geometry may only narrow the
candidates.

Give a multimodal reviewer the edited plate, the numbered markers, the object
list and a board of numbered candidates. Require for each object: candidate id,
`pass` / `fail` / `uncertain`, and visible evidence such as marker number and
silhouette cue. Uncertainty stays open. An empty or conflicting assignment is a
hard stop until resolved; do not auto-fill gaps.

When an object drifted, re-run segmentation with point prompts at its observed
foot on the edited plate. Keep earlier candidates; a replacement is bound to the
new mask job.

## Cut out and bind as runtime sprites

For each assigned candidate, clip to the region around its cell or footprint,
keep the connected component nearest to its foot, and export an RGBA cutout with
real alpha. Measure the contact anchor from visible contact pixels, not from the
bounding-box center.

Bind every cutout as its own texture and entity sprite following
[runtime binding](../../isometric-art-integration/references/runtime-binding.md),
with the entity on its frozen cell and the measured anchor. The renderer orders
depth by entity position, so actors pass behind a tree only when it stays a
separate sprite. Do not paste cutouts into the plate for the playable scene;
a flattened composite is a preview. Buildings follow their assembly blueprint:
separate front parts, proxy colliders and door cells come from that blueprint,
not from one mask.

The mask drops the root bed and contact shadow that the edit painted around the
object, and the unmarked plate has none there. Resolve contact deliberately with
[grounded assemblies](../../isometric-art-integration/references/grounded-assemblies.md):
a ground-owned contact treatment on the plate or a separate reviewed contact
layer. A floating object is a failure even when its anchor is numerically right.

## Provenance and acceptance

For each object the ledger origin is the generated edit record and its edited
plate output. The mask job, cutout and any contact layer are transforms ending
at the runtime image. Hashes establish local correspondence, not provider
authenticity. Acceptance still inspects contact, silhouette and occlusion with
an actor in the host; a complete assignment map is not a pass.

Known limit: numbered foot-lock prompts reduce but do not stop swaps and drift.
The candidate-and-reviewer assignment step remains mandatory after every paid edit.
