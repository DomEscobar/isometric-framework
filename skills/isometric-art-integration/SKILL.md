---
name: isometric-art-integration
description: Calibrate and integrate isometric game sprites and terrain against a shared projection, ground footprint, and physical scale. Use when adding an art pack or diagnosing misaligned bases, bad proportions, seams, or occlusion; not for unrelated gameplay changes.
---

# Isometric art integration

Follow the [production asset policy](../isometric-visual-loop/references/asset-policy.md)
for new worlds. Treat generated art and reused generated sources as candidates until their geometry and proportions
work together in the game. A valid atlas or passing collision test is not visual
acceptance. Respect the requested scope: an analysis request does not authorize
rewriting assets, and a skill invocation does not authorize paid services.

## Read only what the task needs

- To generate candidates or remove backgrounds without a GPT-specific tool, use
  [game asset generation](../game-asset-generation/SKILL.md).
- For this runtime's manifest, rendering, and coordinate rules, read
  [the neutral runtime binding example](references/runtime-binding.md).
- Before measuring a pack, read [the calibration contract](references/contract.md).
- Before accepting or repairing its appearance, use
  [the visual checks](references/visual-checks.md).
- For scenery that must blend into the terrain, use
  [grounded assemblies](references/grounded-assemblies.md): compose the object,
  its contact zone and the actor together before expanding the pack.

## Establish the contract before composing a world

Keep `art-contract.json` beside the host's artwork. Record the actual projection,
height scale, reference actor height, furniture landmarks, contact points, rigid
ground outlines, and intentional foliage/shadow overhang. Set tolerances before
evaluating candidates; explain any later change. These are authoring records,
not extra fields in the runtime's Scene or AssetManifest.

For repairs, preserve close-up evidence of the named defects and calibrate one
representative asset before changing the pack. Record intended proportion ranges
before scaling candidates; keep resulting measurements separate from targets.
A contract assembled after implementation is retrospective validation, not proof
that the implementation satisfied independently chosen proportions.

Copy [the starter contract](references/starter-contract.json) to the host art
folder, then replace its illustrative numbers, image paths, and zero hashes with
measured values. It is deliberately not an approved pack. Document landmark
uncertainty and measurement method in an adjacent notes file.

Use the user's art direction to set proportions. Do not impose realistic adult
dimensions on a deliberately stylized game. Compare chairs, tables, doors, and
characters using shared physical landmarks; padded image widths are not units.

Inspect actual decoded output dimensions and ground-plane edges. A prompt asking
for a precise atlas grid or 2:1 projection does not establish either. Separate
terrain tops, rigid prop bases, vertical height, foliage, and shadows when
measuring. Anchors translate art; they cannot correct a wrong perspective or
footprint shape. Do not squeeze a whole prop to hide a base mismatch.

## Calibrate a small set first

For packed raster actors and animated tile overlays, run the
[decoded packed-art inspector](../isometric-visual-loop/references/acceptance.md)
and inspect its preview before accepting a larger pack. Unlike this skill's PNG
metadata checker, it decodes frame pixels and can flag crop-edge contact,
unexpected alpha components, static motion clips and diamond-overlay leakage.
Neither checker proves visual quality; validate measured contacts and in-game
appearance separately. A raw sheet can look correct while the runtime crops fail.

Use one composed ground patch, actor and representative prop with its intended
root/threshold/bank connection. Add furniture only when its proportions matter.
Mark measured source contacts, projected ground
corners, collision footprints, and vertical reference landmarks. Keep animation
frames at a stable scale and check contact drift in every authored facing.

Before generating a full transparent pack, test one representative output with
an actual pixel decoder. Inspect its background and interior gaps on contrasting
backgrounds; a painted checkerboard is not alpha. If a retry repeats the same
technical failure, change the failing assumption or generation approach before
spending another attempt. See the visual checks for the preflight details.

From the Runtime folder (or use absolute script paths):

```sh
node skills/isometric-art-integration/scripts/check-art.mjs path/to/art-contract.json
node skills/isometric-art-integration/scripts/preview-art.mjs path/to/art-contract.json path/to/calibration.html
```

The tools need only Node, not Pixi, a backend, an image service, or installed
dependencies. They support local PNG sources. For other formats, verify decoded
dimensions and equivalent measurements in a browser or extend the checker with
appropriate tests; do not claim that unchecked formats passed. The HTML board
embeds the images, uses one shared scale, and overlays contacts and footprints.
It is an inspection aid, not a playable scene or an automatic aesthetic verdict.

Then use a tiny **host-owned playable calibration scene** through public APIs:
three adjacent border pieces along each grid axis, one corner, and the actor
walking in front of and behind representative props. The board alone cannot
prove joins, animation, depth ordering, or actual collision. Keep calibration
content outside `src/`; do not bake a game's asset names into engine code.

Bind the sidecar to the actual host image and rendering definitions. Matching the
sidecar's own hash does not establish that the game uses that image. Check the
delivered scene against the calibrated values:

```sh
node skills/isometric-art-integration/scripts/check-scale-binding.mjs path/to/art-contract.json path/to/scene.json path/to/binding-plan.json
```

It compares projection, crops, effective anchors, render scale, offsets, grid
footprints and each `bodyHeight` against the one calibrated world scale, and names
every sprite type and textured tile that no contract asset covers. Uncalibrated art
and a deliberately conservative collider need a stated reason, not silence.
The contract checker also decodes each frame's alpha and measures the visible
silhouette, because no pixel outside the ground diamond a `footprint` reserves can
belong to that asset at any height. Terrain and prop artwork must sit inside that
diamond on both sides, so declaring contacts across one tile of a six-tile wall no
longer shrinks it and an empty frame is rejected rather than passed. Deliberate
overhang needs a measured `overhangPx` budget together with the `allowedOverhang`
reason; a budget without a reason is a finding.

A budget and a reason are no longer enough on their own, because the measurement
cannot tell a drooping canopy from a wall base covering the neighboring square:
both read as a wide silhouette. Where art fits only because of its budget, the
checker names the exact spilling columns, measures how far their lowest material
stays above the nearest ground contact, and hashes that region. Passing then needs
a ruling in `overhangRulings` that classifies each spilling side and cites that
hash, so the verdict answers the measured question and expires whenever the
artwork, frame, anchor, scale, footprint or projection moves. Only `canopy`,
`eave`, `attachment` and `shadow` may leave the footprint; `ground-contact`,
`foundation` and `unclear` are findings. Read
[the classification question](references/overhang-prompt.md) before ruling, and
judge the band in place at magnification rather than the asset as a whole:

```sh
python skills/isometric-art-integration/scripts/show-overhang.py <contract> <new directory>
```

That writes one magnified view per spilling side, marks the nearest ground contact,
and reports the hashes a ruling must cite. It runs before a budget exists, so view
the band first and only then decide whether to widen the footprint or rule on it.

What the framework proves is which pixels left the footprint and what they were
weighed against; the class itself is a judgement. A wrong verdict still passes, so
the recorded `basis` has to name the part of the artwork the band contains.

The silhouette also bounds how tall a prop is. For each prop the checker reports
`bodyHeightPx`, the band of body heights the artwork's top allows above its ground
contact, and the host binding's `bodyHeight` may not fall below that band. That
number is what the renderer orders depth and resolves collision with, so art
rising above the body a host claims sorts and blocks as a stub while towering on
screen. Only the floor is enforced, since a body taller than its art is a
deliberate collider rather than a defect, and the floor stays generous for large
footprints because the silhouette cannot say which cell owns the highest pixel.
It settles orders of magnitude, not single pixels. Read
[the binding plan](references/contract.md#bind-the-contract-to-the-host) for its
fields and the comparisons it still leaves to you.

This establishes that the game renders the values you measured, never that those
values suit the game. Proportion judgement stays with the preview board and the
rendered scene; a passing binding cannot approve a scale that reads wrong.

## Choose the repair from the evidence

- Correct a crop/contact/scale only when the underlying projection is compatible.
- If rigid edges cannot fit together, reauthor or regenerate the incompatible
  asset. Measure its new output again; retain source and prompt provenance.
- Use appropriate orientations, ends, and corners for modular borders. Foliage
  may cross tile edges deliberately; unexplained stone-base spill is a failure.
- Split a furniture composite when its internal proportions or required
  front/back ordering cannot be represented correctly as one sprite. A large
  image must not automatically become a large solid rectangle.
- Change engine behavior only after a minimal compatible-asset example shows a
  renderer defect. A placement workaround is not proof of an engine bug.

## Accept and hand off

Report **metadata**, **visual compatibility**, and **gameplay** separately as
pass, fail, or unverified. Metadata success means the supplied annotations agree
with each other; it does not prove the annotations match the artwork. Save close
views of rigid joins and player/furniture proportions as well as the full scene.
State which measurements are independent, authored, or inferred, and name the
covered assets and animation states. Idle measurements do not approve jump frames.
Check intended desktop/mobile sizes, animation, occlusion, collision, and
production image loading as relevant to the change.

Preserve failing evidence and correct it before claiming completion. Do not
broaden tolerances, relabel accidental overflow as foliage, or accept a distant
screenshot to turn a visible defect into a pass. Stop and report unresolved
constraints if the requested scope excludes the needed repair.

Carry the contract, source hashes, calibration evidence, and known limitations
with the host's art pack. Future agents must repeat affected checks when replacing
an image, frame, anchor, display scale, or footprint.
