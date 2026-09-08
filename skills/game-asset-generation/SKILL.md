---
name: game-asset-generation
description: Create game sprite and texture candidates using WaveSpeed Seedream or an available image provider, remove backgrounds with WaveSpeed or local rembg, and inspect decoded alpha before art integration. Use when a game needs new raster assets or transparent cutouts; no GPT ImageGen dependency.
---

# Game asset generation

Produce local, reusable asset files with source provenance. This skill covers
generation and cutout preparation; the sibling
[isometric-art-integration skill](../isometric-art-integration/SKILL.md) covers
projection, scale, placement, and acceptance inside a game.
For turnarounds, walk/jump/attack phases, and sheet assembly, use
[directional sprite authoring](../directional-sprite-authoring/SKILL.md).

## Choose the available path

| Need | Recommended starting path | Alternative |
| --- | --- | --- |
| New artwork | WaveSpeed `bytedance/seedream-v5.0-pro` | An already available image provider, local generator, or supplied/licensed art |
| Reference-guided variants | Seedream Pro Edit with an accepted reference | Available provider's image-edit workflow |
| Transparent prop/actor | Preserve valid existing alpha; otherwise WaveSpeed `wavespeed-ai/image-background-remover` | Local CPU `rembg` |
| Exact modular stone/terrain geometry | Code/vector-authored geometry matching the host projection | Measured compatible sourced or generated art |

Seedream is the recommended provider path here, not a claim that it has been
benchmarked best for pixel art. Generated PNGs need not contain alpha. Background
removal is a separate operation and cannot fix an incorrect perspective.

Read [WaveSpeed usage](references/wavespeed.md) for API requests, resumable jobs,
reference editing, and downloads. Read [local removal and alpha review](references/backgrounds.md)
for the CPU fallback, its installation/model requirements, and inspection commands.
No provider tool, global skill installation, or runtime dependency is required.

## Generate a representative candidate first

Use the host's established projection, palette, light direction, target actor/prop
proportions, and intended source pixel density. Create one asset before a large
pack. Favor separate assets or small controlled sets over an atlas whose exact
cell layout exists only in the prompt. Measure actual output dimensions.

For a cutout, request one isolated object with complete silhouette, generous
margin, and a flat contrasting background color absent from the subject. Avoid
checkerboards, gradients, scenery, labels, and baked ground shadows. Do not choose
green behind foliage or white behind white petals. This is preparation for
segmentation, not a promise of perfect color-key removal. Terrain intended to fill
a tile does not need foreground segmentation; it can destroy the tile's edges.

Example brief: "One compact orange marigold clump for a 2:1 isometric pixel-art
garden. Warm upper-left lighting, crisp clustered pixels, complete fine stems and
leaves, no pot, soil or cast shadow. Centered with generous margins on a uniform
contrasting backdrop. No text or checkerboard. Match the host's approved palette."
Replace the subject and palette with the actual game brief; a text-to-image
endpoint cannot see an unprovided reference.

For repeated characters, use an accepted reference and explicit pose/facing
instructions. Keep common canvas and contact origins across frames; do not
independently auto-trim poses. Generation does not guarantee animation continuity.

## Prepare, inspect, then integrate

1. Keep the original generation. If it already has usable alpha, skip removal.
   Otherwise remove the background on a representative asset. For multi-object
   sheets, verify every object survives; segmentation can retain only the dominant
   subject. Prefer separately isolated crops with recorded atlas coordinates when
   the sheet fails. Preserve dimensions and contacts or explicitly recalibrate.
2. Decode alpha and make the supplied light/dark/magenta inspection board. An
   opaque checkerboard, an empty output, or an RGBA file with only opaque pixels
   is not a cutout. A numeric alpha pass still does not approve the mask.
3. Inspect fine petals, holes between leaves/chair legs, rigid edges, halos, and
   missing parts at native scale and intended game scale. Compare with the
   original. Do not erase similarly colored subject pixels just to clear a fringe.
4. If removal loses details or leaves background, change the background/source,
   isolation, or removal method based on that defect. After the same failure
   repeats, change the approach rather than blindly rerunning the same request.
   Keep unresolved defects visible in the handoff.
5. Save accepted files beside the host's art, hash them, then apply the integration
   skill. Keep original and processed hashes, exact prompt/request, provider/model,
   prediction ID, processing version/model, and any crop or canvas changes.

Run remote work within the user's existing provider and spending authorization;
do not ask again when it already covers the action. Creating this skill alone
does not require a paid request. Keep credentials in the environment, never in
scene JSON, source files, or browser code. Keep temporary jobs and inspection
boards in the host's ignored evidence directory. Download accepted outputs to
host-owned files; temporary provider URLs are not production game assets.

Report generation, decoded alpha, visual mask quality, and in-game acceptance
separately. A local fallback's availability does not establish its quality on the
current art, and mocked API tests do not establish a successful paid generation.
