---
name: consistent-tileset-authoring
description: Prepare compatible isometric tilesets from shared generated materials or master parts, with fixed geometry, neighbor masks, inner corners, and rendered join checks. Use for connected beds, paths, walls, or water; includes a concrete 47-variant raised-bed assembler.
---

# Consistent tileset authoring

Use this when independently generated tiles disagree in perspective, scale or
edge position. Autotiling selects artwork; it cannot correct incompatible artwork.
Use the [neutral runtime binding example](references/runtime-binding.md) for
neighbor masks and host-owned catalogs.

## Set the contract before generating

- Choose grid projection, tile dimensions, surface height, rim thickness, contact
  anchor, pixel density and lighting once for the family. Measure these in world
  units alongside the player. A padded sprite frame is not a footprint.
- Choose topology: `cardinal16` for four-neighbor connections, `blob47` when
  diagonal occupancy must distinguish concave corners and holes. Both operate on
  the runtime's c/r axes. Mask numbers are not sequential atlas positions.
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

Use [the recipe reference](references/bed-recipe.md) for the included tool:

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
2. Inspect a strip, L, filled patch, hollow ring and diagonal-only pair in the
   renderer. Check cap width, inner corners, double walls, gaps and scale against
   the actor. A valid atlas or 47 distinct images is not visual acceptance.
3. Run one affected desktop/mobile journey: closed ring blocks walking; removing
   one edge permits walking inside; repainting updates neighboring corners;
   the actor's occupied tile stays protected. Inspect touch controls in play mode.
4. Record source/recipe, geometry, missing variants, rendered evidence and limits.
   Expand to new families after this small assembly works. For water animation,
   keep the approved boundary geometry and contact fixed across frames; pair with
   [animated-environments](../animated-environments/SKILL.md).
