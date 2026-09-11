---
name: consistent-tileset-authoring
description: Compose connected isometric terrain with consistent material transitions, shared boundaries and controlled variation, then prepare compatible tiles. Use for natural paths, grass and stream banks as well as constructed borders; the included raised-bed helper handles rigid bed geometry only.
---

# Consistent tileset authoring

Use this when independently generated tiles disagree in perspective, scale or
edge position. Autotiling selects artwork; it cannot correct incompatible artwork.
Use the [neutral runtime binding example](references/runtime-binding.md) for
neighbor masks and host-owned catalogs.

For natural paths, grass or stream banks, start with
[landscape composition](references/landscape-composition.md). Establish regions,
material-pair transitions and variation across cells before selecting tile masks.
The ground must read as one landscape at playing zoom. A valid connected catalog
can still fail through hard fringes, mirrored motifs and inconsistent pixel style.

## Set the contract before generating

- Choose grid projection, tile dimensions, surface height, transition or rim width, contact
  anchor, pixel density and lighting once for the family. Measure these in world
  units alongside the player. A padded sprite frame is not a footprint.
- When producing a reusable neighbor-driven tile family, choose topology:
  `cardinal16` for four-neighbor connections, `blob47` when
  diagonal occupancy must distinguish concave corners and holes. Both operate on
  the runtime's c/r axes. Mask numbers are not sequential atlas positions.
  A composed ground patch can instead export measured crops without building a
  generic 47-mask family.
  For an already composed image, use the optional offline
  [ground preparer](references/composed-ground.md): one plate or positioned chunks,
  with explicit masks and image transforms. Authored, supplied and generated inputs
  are equally supported; this does not replace reusable transition tiles.
- For natural ground, record actual material adjacencies and their edge treatment.
  Require separate terrain-composition and transition verdicts; approve a mixed
  patch with upright/optional props hidden before expanding the world. Retain
  ground-owned root beds, wear and contact shadows, then inspect the dressed
  [object-ground connection](../isometric-art-integration/references/grounded-assemblies.md).
- Keep structural parts separate from flowers, furniture and other decoration.
  A generated bed with flowers, soil and wall baked together is a composite prop,
  not automatically a reusable border tile. Do not hide failed joins with flowers.

## Use one compatible source family

When generated art is requested, obtain actual generated output using the
available provider; [game-asset-generation](../game-asset-generation/SKILL.md)
provides a portable route. Preserve the source, prompt and provider record.
Prefer one shared material sheet or a few reference-guided master parts over
47 independent text-to-image requests. Prompts alone cannot enforce pixel geometry.

For flat material workflows, generate orthographic material swatches with no
camera perspective, objects, cast shadows, labels or baked tile borders. Assign
each swatch a measured crop inside its useful area. Then map those materials onto
fixed geometry. Disclose this as **generated materials with deterministic assembly**;
do not claim the provider generated every finished sprite.

For artist-authored master parts, preserve shared contact edges when composing
variants. Do not mirror a lit prop or rotate a whole isometric sprite merely to
fill a missing direction: its projection and shading may cease to match.

## Raised-bed preparation helper

Use this tool only for the raised beds or rigid borders it represents. It is not
the default production path for grass, natural trails or stream banks. Use
[the recipe reference](references/bed-recipe.md) when that geometry is required:

```sh
node --experimental-strip-types skills/consistent-tileset-authoring/scripts/prepare-bed-tileset.mjs recipe.json output-art
```

This helper builds 47 raised-bed variants and one grass tile. It uses generated
material RGB on a fixed 2:1 plane, shared caps, exposed front walls and concave
corners. It is a bed assembler, not a general building, curved bridge or
multi-terrain transition generator. Those need their own compatible catalog or
the [multi-tile assembly workflow](../multi-tile-asset-assembly/SKILL.md).

The helper checks source dimensions/crops and alpha, prefilters all materials to
one resolution, then uses integer samples and mirrored repetition. Directly
sampling a large source sparsely can cause speckled aliasing.
Mirrored repetition matches boundary samples but can reveal repetitive motifs;
it does not guarantee natural-looking stonework or grass. Inspect at game scale.

Strict opacity is the default for these solid materials. If a supposedly opaque
sheet has uniform near-opacity, inspect it and explicitly select
`opaque-material-rgb` to retain RGB with opaque output. The helper rejects source
crop alpha below 200 even in that mode. Never apply this shortcut to cutout props,
water transparency, or baked checkerboards. Preserve the original either way.

## Integrate and check the result

1. Resolve host-owned cells with the public API. Treat missing variants as an
   incomplete catalog; do not substitute a straight or filled tile silently.
   Derive both rendered beds and blocking cells from the same edited cell set.
2. Inspect a strip, L, filled patch, hollow ring and diagonal-only pair for the
   applicable topology. For natural ground, also inspect a mixed-material bend
   and junction at playing zoom, close-up and overview, with optional props hidden.
   Check edge continuity, pixel treatment and repeated motifs. Restore props for
   final readability. A valid atlas or 47 distinct images is not visual acceptance.
3. Run the affected desktop/mobile journey using the host's collision policy:
   paths remain traversable and dry banks readable; water blocks entry when intended.
   For blocking beds, a closed ring blocks entry and an opening permits it. When
   editing is part of the host, verify neighbor updates and actor-cell protection.
4. Record source/recipe, geometry, missing variants, rendered evidence and limits.
   Expand to new families after this small assembly works. For water animation,
   keep the approved boundary geometry and contact fixed across frames; pair with
   [animated-environments](../animated-environments/SKILL.md).
