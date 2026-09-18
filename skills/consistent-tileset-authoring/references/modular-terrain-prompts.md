# Worked prompt patterns: modular terrain

These are neutral, unvalidated prompt patterns for adapting to a real project.
They are not successful-generation evidence or a validated reusable tileset.
They apply only to a **reusable neighbor-tile family**. A composed ground plate
does not use this file; follow [composed ground](composed-ground.md) instead.

## Output and integration boundary

Request a compatible material source or a small family of transition candidates;
integration still owns fixed geometry, masks, world origins, collision and
variant registration. Independently generated tiles do not autojoin. A natural-
transition assembler is not implemented by this reference: there is no script
here that turns grass/path/bank prompts into a 47-mask catalog. The raised-bed
helper is limited to rigid beds; it does not solve grass, trail or stream edges.
That is not a hole in composed-ground preparation, registration or binding.

Use one material authority for the family. Declare the projection (for example,
2:1 isometric), cell dimensions, surface height, contact edge, pixel density,
lighting direction and transition width. Input image 1, when supplied, is a
style/material authority; input image 2 is a layout or boundary guide. State
which role each image has. A text-only endpoint cannot consume an image guide.
Do not treat a padded frame as the cell footprint.

## Initial prompt example

Example inputs: an approved grass/earth material image and a clean 256 x 128
boundary guide containing four 128 x 64 projected cells in separate slots.
The guide defines straight, inside-corner, outside-corner and end contacts,
with a four-pixel transition band. These are sample dimensions, not defaults.

```text
Create a neutral modular terrain candidate for a 2:1 isometric pixel-art game.
Keep the supplied 256 x 128 canvas and four guide slots. Each square world cell
projects to a 128 x 64 diamond; all surfaces are level. Use crisp two-pixel
clusters and warm upper-left light. Input image 1 is style-only: match its palette ramps and
material treatment. Input image 2 is the boundary guide: preserve its shared
grass-to-earth contact line, cell footprint and declared height; its flat colors
are labels, not colors to copy.

Provide the straight, inside-corner, outside-corner and end contacts in their
assigned slots. Keep the four-pixel transition band and contact positions from
the guide. Vary interior texture across candidates,
but do not move required edge samples. Use crisp interlocking clusters, broad
material patches and sparse wear. No objects, labels, atlas assumptions, baked
collision, or decorative border beyond the declared footprint. Use transparency
outside each diamond if supported; otherwise use the declared removable backdrop.
```

## Targeted correction example

```text
Edit input image 1, the terrain candidate, using input image 2 as the exact
boundary guide. Correct only the grass-to-earth contact on the marked bend and
its adjoining corners. Preserve canvas, 2:1 projection, cell dimensions,
surface height, lighting, palette, pixel density and all unmarked interiors.
Make the shared edge samples and transition width agree at both neighboring
cells. Do not add a new material, object, hard rim, mirrored motif or tile-grid
label. Return the corrected candidate with transparent pixels only outside the
declared footprint.
```

## Downstream checks

Inspect a strip, L, filled patch, hollow ring, diagonal pair and each real
material-pair bend at native, playing and overview scales. Compare shared
world-space edge samples, transition width, palette and texture rhythm; matching
corners alone is insufficient. Hide props for ground review, then restore them
and walk the route. Register only measured crops after alignment passes.

Use the optional [composed-ground preparer](composed-ground.md) for a plate or
positioned chunks, and the [registration inspector](registration-review.md) for
independent landmark measurements. Use the [runtime binding example](runtime-binding.md)
for host-owned neighbor masks. If rigid raised beds are actually in scope, the
[bed recipe](bed-recipe.md) documents that limited helper. Record missing
variants and mark visual, collision and traversal checks pass, fail or
unverified; a valid atlas is not acceptance.
