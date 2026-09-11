---
name: game-asset-generation
description: Create game sprite and texture candidates using the project's chosen Retro Diffusion MCP, WaveSpeed Seedream, or other available provider; prepare transparent cutouts and inspect decoded alpha before art integration. Use for new raster assets or cutouts, not unrelated runtime work.
---

# Game asset generation

Produce local, reusable asset files with source provenance. This skill covers
generation and cutout preparation; the sibling
[isometric-art-integration skill](../isometric-art-integration/SKILL.md) covers
projection, scale, placement, and acceptance inside a game.
For turnarounds, walk/jump/attack phases, and sheet assembly, use
[directional sprite authoring](../directional-sprite-authoring/SKILL.md).

## Use the project's chosen production path

Read the host's existing brief or contract first. Preserve its chosen provider,
technique, style and spending limits. If these decisions are missing, present
relevant options and ask only for consequential choices before paid generation.
The user can delegate the choice; record the selected approach and its reason.
An available tool is not automatically the project's preferred art pipeline.

| Need | Option | Other supported approach |
| --- | --- | --- |
| Pixel sprites, animation or tileset candidates | [Retro Diffusion MCP](references/retro-diffusion.md), with a compatible selected style | Another project-approved provider or authored/supplied assets |
| General raster artwork | WaveSpeed `bytedance/seedream-v5.0-pro` | An already available image provider, local generator, or supplied/licensed art |
| Reference-guided variants | Selected provider's reference workflow, such as Seedream Pro Edit | Authored edits preserving the approved identity |
| Transparent prop/actor | Preserve valid existing alpha; otherwise WaveSpeed `wavespeed-ai/image-background-remover` | Local CPU `rembg` |
| Exact modular stone/terrain geometry | Host geometry and measured contact edges | Compatible authored, supplied or generated appearance on that geometry |

Neither provider is a universal default or benchmarked winner in this framework.
Generated PNGs need not contain usable alpha. Background
removal is a separate operation and cannot fix an incorrect perspective.

Read only the selected provider's recipe: [WaveSpeed usage](references/wavespeed.md)
for its API jobs, or the Retro Diffusion reference above for its MCP tools. Read
[local removal and alpha review](references/backgrounds.md) when removal is needed.
The Retro Diffusion path requires its MCP connection; the included WaveSpeed
client uses HTTP directly. These are authoring dependencies, not runtime services.

Provider choice and technique are separate decisions. A project may explicitly
choose generated materials with deterministic tile assembly and separately
authored character frames. Record which technique owns each asset family. Do not
silently change providers, mix styles or substitute example artwork after failure;
use an agreed fallback or raise the specific decision that needs changing.

Exact geometry does not require code-painted ground. When the selected technique
is a composed generated landscape, supply the host layout and style reference,
then measure alignment before using the optional
[ground preparer](../consistent-tileset-authoring/references/composed-ground.md).
Prompts do not guarantee matching banks or paths; topology and collision remain
host-owned. This is an alternative to modular tiles, not a provider default.

For a composed ground request, translate the scene reference into the requested
layer's materials. "Terrain only" is ambiguous when the same prompt asks for
dense vegetation: specify low grass/soil/contact details versus separate upright
trees, rocks and structures. Keep the host's elevation and doorway levels explicit;
a flat footprint must not become a raised building plot merely because the style
reference has cliffs. Supply a clean layout image with declared reference roles,
using explicit ordered image inputs when the provider supports them. Record actual
submitted inputs as well as the prompt; intended references alone are not provenance.

Illustrative ground-layer request: "Use the layout for positions and heights;
use the style image for pixel clusters, earth, grass and water treatment. Paths
and future building sites share one walking level with flush approaches. Keep
only low ground cover and contact detail in this layer. Upright trees, large
rocks and buildings will be separate assets. Show bank faces only where the
layout declares a drop." Adapt heights and layer ownership to the actual project.

Inspect raw candidates for invented elevation, blocked approaches and baked
upright objects before registration or another generation. If one fails, preserve
it and revise the specific conflicting constraint. Do not repaint a convincing
but unsupported ledge as a walkable path or assume slicing fixes layer ownership.

## Generate a representative candidate first

Use the host's established projection, palette, light direction, target actor/prop
proportions, and intended source pixel density. Create one asset before a large
pack. Favor separate assets or small controlled sets over an atlas whose exact
cell layout exists only in the prompt. Measure actual output dimensions.

Choose the asset's role before requesting a cutout. Rooted scenery may need a
small composed contact patch: roots, exposed soil, low grass and contact shadow
designed together. Follow [grounded assemblies](../isometric-art-integration/references/grounded-assemblies.md)
to separate ground/upright layers where depth or motion requires it. Removing
all ground context is not a universal quality rule. Preserve the material edge
needed to join a patch to its surroundings; avoid a repeated opaque dirt oval.

For a portable isolated cutout, request the object with complete silhouette, generous
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

For a grounded patch, an illustrative brief is: "A rooted shrub with exposed
earth between its stems, sparse grass entering the outer soil edge and a compact
upper-left-lit contact shadow. Match the supplied game's pixel clusters and
grass palette; irregular perimeter, no rectangular base or surrounding scene."
Use the current host's reference and intended layer split. A material swatch,
portable cutout and rooted patch solve different tasks.

For repeated characters, use an accepted reference and explicit pose/facing
instructions. Keep common canvas and contact origins across frames; do not
independently auto-trim poses. Generation does not guarantee animation continuity.

When a provider needs multiple exact references, prepare a reviewable input bundle
with the offline [request preparation helper](references/request-preparation.md).
It separates style, layout and explicitly approved identity crops, preserves their
source hashes and cannot send a generation request. Do not feed rejected identity
crops into a later request. For a directional action matrix, first review one
direction/action and record its self-reported calibration receipt; ordinary
multiasset generation does not require that receipt.

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
