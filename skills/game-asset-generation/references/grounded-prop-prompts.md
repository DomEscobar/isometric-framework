# Worked prompt patterns: grounded static props

These are neutral, unvalidated worked prompt patterns, not successful-generation
evidence. They describe the requested output; projection, placement, collision and acceptance remain host
integration work.

## Output and input roles

Request one grounded static object with a complete silhouette, real alpha or a
declared removable backdrop, generous margin, a measured contact origin and the
host's projection, scale, pixel density, palette and light. Input image 1 may be
style-only; input image 2 may be a placement or ground guide. Name each role and
do not let a style image silently determine layout. Split ground/contact patch
from the upright object when depth, actor passage or motion requires it. Keep
roots, soil and low contact detail with the ground layer when they belong there.
Directional actors and action sheets use their separate skill; generation gives
no sheet-perfection guarantee.

## Initial prompt example

Example inputs: approved material/style art and a clean placement guide showing
a shrub contact point at (64, 96) on a 128 x 128 canvas. The host uses 64 x 32
ground cells and a 32-pixel-tall actor. Adapt these numbers to the actual host.

```text
Create one compact static leafy shrub for a 2:1 isometric pixel-art game.
Keep the 128 x 128 canvas. The shrub is 24 pixels tall above its ground contact
at (64, 96), with a 32 x 16 projected footprint. Use crisp one-pixel clusters.
Input image 1 is style-only: match its pixel cluster scale, palette ramps,
outline treatment and upper-left lighting. Input image 2 is placement/ground
authority: preserve its declared contact origin, supported surface height and
scale relative to the actor; do not copy unrelated layout.

Show the complete upright silhouette with a clear base contact and generous
margin. Keep low root and shadow details visually separable for later extraction;
do not include a lawn tile around the shrub. Keep the surrounding route clear.
Use genuine transparency outside the silhouette (or a flat contrasting
background suitable for removal). No checkerboard, text, labels, scenery,
duplicate objects, cast shadow detached from the contact, or baked collision.
```

## Targeted correction example

```text
Edit input image 1, the prop candidate, using input image 2 as the original
placement guide. Preserve the candidate's approved style. Correct only the floating
base and missing contact pixels. Preserve the object's silhouette, canvas,
projection, scale, palette, lighting and all upper details. Remove only contact
detail that intrudes into the guide's walking route; retain
the measured contact origin and a restrained joined shadow. Keep low contact
detail separable; the host will extract layers if needed. Do not add scenery,
text, a second object or directional animation frames.
```

## Downstream checks

Decode alpha and inspect a light/dark/magenta board; verify holes, thin parts,
halos and lost pixels at native and playing scale. Measure the contact origin,
footprint and actor-relative height. Place the upright and ground layers in the
host, then inspect the base with props hidden and dressed with an actor from each
reachable approach. Reject floating or pasted contacts even when coordinates
are valid, and mark visual, depth, collision and interaction checks separately.

For the integration contract, use the [grounded assemblies guidance](../../isometric-art-integration/references/grounded-assemblies.md).
For cutout inspection, use [background and alpha review](backgrounds.md); for
input provenance, use [request preparation](request-preparation.md). Preserve
raw and processed files, prompt, input roles, dimensions, transforms and any
provider request identity. A clean alpha pass does not establish in-game
acceptance.
