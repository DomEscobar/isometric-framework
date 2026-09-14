# Prompt examples: one continuous ground surface

Use after choosing composed ground as the world assembly. These are worked prompt
examples for the coding agent to adapt, not a universal model preset. Do not send
this entire document or unrelated examples as the image prompt. No example image,
host, palette or historical trial is an asset source. Prompts propose candidates;
decoded pixels and the playable host determine whether they work.
Treat these as starting prompts; acceptance applies to the measured assembly,
not to the prompt text or every possible use of the technique.

## Inputs and output boundary

Before a request, record the selected image source/provider, reference roles,
actual output/camera geometry, target pixel treatment and fixed gameplay features.
Use the existing approved contract; choose initial concept direction before the
acceptance freeze. Preserve the current provider and spending permissions.

Decide which features this layer owns: low grass, soil, wear, paving, bank lips and
contact beds can belong to ground. Buildings, tree crowns, rails and moving water
normally need separate layers when depth or motion requires it. A quiet future
building site is ground at the declared height, not permission to invent a cliff.
Inspect ground-only while retaining those owned contact details.

For fixed layout, provide the clean runtime-projected guide with named material
roles. Keep diagnostic grid/labels in a separate review image. A reference-capable
request can receive the guide; a text-only endpoint cannot. Do not invent image
fields for a text-only model. For flexible composition, text-to-image may propose
the scene before the host derives and checks its geometry.

Before spending on fixed-layout generation, inspect the guide itself: render it
from the host projection, verify that approaches and the full walking width fit
inside supported ground, and check that the brook does not cut the promised route.
A hand-drawn diamond or a list of coordinates is not runtime projection evidence.
Rasterize vector guides to a supported input format and inspect the actual raster.
Then inspect the callable tool schema and attach that file as the layout input.
Lacking a dedicated control or mask parameter does not imply lacking ordinary
image references; image references in turn do not guarantee geometric control.
Record the exact submitted reference paths/roles. If the guide was omitted, the
request did not test this fixed-layout recipe. Stop or explicitly change the
agreed route instead of treating text coordinates as an equivalent input.

Record exact submitted prompt and inputs, returned source, decoded dimensions,
request identity when exposed, elapsed time and transformations. Requested size
is not proof of returned size. Preserve the raw output before preparation.

## Example 1: fixed-layout ground with an irregular path and brook

Input situation: a clean projected guide defines a grass region, a widening path
bend with one junction, a continuous brook alongside it, and a reserved approach
for a later building. All walking surfaces share one height. There is no style
image; the approved style is described in text. The guide colors are material
labels, not a palette to copy. Replace dimensions and geometry with actual inputs.

```text
Asset: one continuous ground-only image for a fixed isometric game map.
Input image 1 is the layout authority: preserve its framing, outer footprint,
path centreline and width changes, brook course, junction and reserved entrance
approach. Its flat colors label materials; they are not the final art style.

Create crisp clustered pixel art with a consistent pixel scale, muted moss-green
grass, warm earth, restrained blue water and soft upper-left lighting. The path
widens at the junction and meets the future doorway approach flush at the same
walking height. Grass enters the path edge in irregular clumps; the centre stays
readable and open. Use broad quiet material patches and sparse wear, without a
texture pattern restarting at every cell.

The brook is one continuous channel following the guide. Grass, exposed wet earth
and water meet along joined banks; do not add terraces, retaining walls or raised
building platforms. Keep bank and doorway positions fixed. Keep upright trees,
buildings, fences, actors, text, labels and grid lines out of this ground layer.
Keep the water interior visually separable for later animation. This output is
static art, not an animated stream. Match the guide canvas and projection; do not
reframe the map or add a decorative island pedestal.
```

When there is an approved style image, add it as image 2 with an explicit style-only
role for clusters, materials, lighting and scale. Do not copy its layout. Request
real alpha outside the footprint only if the chosen route supports it; inspect
returned alpha instead of treating a painted checkerboard as transparency.

## Example 2: text-only concept when layout is still flexible

Input situation: no layout image or established visual source exists. The approved
scope allows selecting the composition, but still requires a route, junction,
brook and flush entrance approach. This is concept selection before layout freeze.

```text
Create an original ground-only concept for a compact isometric game clearing.
Use a consistent 2:1 ground projection and crisp clustered pixel art. Compose a
readable earth path that bends through grass, broadens at one junction, and reaches
a quiet flat building approach. Place a continuous narrow brook alongside part of
the route without severing access to the approach. All walking ground is level.

Use muted moss greens, warm earth and restrained blue water under upper-left light.
Integrate path edges through interlocking grass/soil clusters, broader material
patches and sparse wear. Connect both banks continuously around the brook bend.
Show only ground, low contact detail and water: no buildings, tall trees, actors,
labels, grid, tile atlas, cliff platforms or decorative pedestal. Keep the complete
ground footprint visible with margin, using a uniform contrasting outer background.
```

This prompt intentionally does not promise an exact navigable map. Choose a
candidate, derive semantic regions/routes/support from it, and reject infeasible
geometry before freezing production. If geometry is already fixed, use example 1
with a compatible control route instead of pretending this text-only path locks it.

## Example 3: targeted correction of a shifted internal feature

Input situation: the candidate has acceptable grass and path treatment but its
entrance approach has moved relative to the protected layout. The observed location
is measured from candidate pixels, not copied from the expected coordinates.

```text
Edit input image 1, the candidate ground. Input image 2 is the exact layout guide.
Correct only the entrance approach and its immediately adjoining path/grass edge
to meet the doorway landing shown by image 2. Keep the doorway approach flush with
the path at the same walking height. Preserve the candidate canvas, map footprint,
brook course and banks, other path branches, lighting, palette and pixel clusters.
Do not add a building, steps, cliff face, path obstruction or extra scenery.
```

If a mask is supported, limit it to the observed defect and enough adjoining ground
to rebuild the join. A mask is not automatically inferred by this recipe. If the
route cannot make local edits, choose the already agreed authored repair/fallback
or report the specific capability gap. Do not silently call a different provider.

## Inspect before cutting or expanding

1. Check raw canvas/projection and obvious invented heights or baked upright objects.
   A large mismatch changes strategy; more decoration is not a correction.
2. At native and playing scale, inspect the worst path/grass transition, brook bend,
   junction and future doorway approach. Natural edges use crisp clusters, not blur.
3. Choose evidence that is observable in the artwork. Compare identifiable internal
   landmarks with the layout, using the optional
   [registration inspector](../../consistent-tileset-authoring/references/registration-review.md).
   Choose tolerance from the promised path width/actor clearance before seeing the
   candidate. For a simple straight corridor, the lateral displacement allowance is
   at most `(path width - actor width) / 2 - retained safety margin`, all measured
   in the same cross-section and coordinate space; bends need full footprint checks.
   Record how any resize/origin transform maps guide to source pixels.
   Expected and observed coordinates must be independently obtained. The numeric
   result checks those annotations; it cannot certify matching image geometry.
   For traversability when semantic centers are not visibly identifiable, use a
   predeclared [route-support check](../../consistent-tileset-authoring/references/ground-support.md)
   with reviewed image-derived and planned support masks. Check full feet and
   clearance along the path, not only at endpoints. This does not prove exact layout
   reproduction or retroactively turn an unverified landmark test into a pass.
4. Only after alignment is acceptable, use the
   [ground preparer and flat runtime binder](../../consistent-tileset-authoring/references/composed-ground.md).
   Check prepared reconstruction, then inspect actual ground-only runtime views and
   walk the route to the approach. Keep collision derived from the semantic layout.
5. Record generation attempts, time spent generating versus alignment/integration,
   manual repairs and failed/unverified checks. For a bounded experiment, honor its
   agreed round limit. For production, use the visual loop's changed-strategy rule.

This recipe provides no general modular transition catalog, multi-floor binder,
automatic mask extraction or river animation. Those are separate capabilities.
An attractive still does not establish motion or game acceptance.
