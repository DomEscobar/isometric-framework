---
name: game-asset-generation
description: Create game sprite and texture candidates using the project's selected image or video provider; prepare transparent cutouts and inspect decoded alpha before art integration. Use for new raster assets or cutouts, not unrelated runtime work.
---

# Game asset generation

Follow the central [production asset policy](../isometric-visual-loop/references/asset-policy.md).
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
| Character motion | [Directional sprite workflow](../directional-sprite-authoring/SKILL.md): approved generated facing image, approved capable I2V tool, actual-video review, extraction and packing | No alternate production route |
| General production raster artwork | Approved T2I/I2I provider, such as WaveSpeed `bytedance/seedream-v5.0-pro` | No non-generated production route |
| Reference-guided production variants | Selected I2I provider workflow, such as Seedream Pro Edit | Masked I2I repair of approved generated art |
| Transparent generated prop/actor | Preserve valid generated alpha; otherwise WaveSpeed `wavespeed-ai/image-background-remover` | Local CPU `rembg` |
| Exact modular stone/terrain geometry | Host geometry and measured contact edges | Compatible generated materials assembled on that geometry |

No provider is a universal default or benchmarked winner in this framework.
Generated PNGs need not contain usable alpha. Background
removal is a separate operation and cannot fix an incorrect perspective.

Read [WaveSpeed usage](references/wavespeed.md) when that provider is selected. Read
[local removal and alpha review](references/backgrounds.md) when removal is needed.
The included WaveSpeed image client uses HTTP directly. Generation tools are
authoring dependencies, not runtime services.

World assembly, image source and provider are separate decisions. Select modular
terrain, composed ground, layered artwork or a hybrid with the
[visual loop](../isometric-visual-loop/SKILL.md) first. A project may explicitly
choose generated materials with deterministic tile assembly. Record which technique
owns each asset family. Character motion follows the directional I2V route; direct
generated sheets, individual gait frames and authored character animation are not
production alternatives. Do not
silently change providers, mix styles or substitute example artwork after failure;
use an agreed fallback or raise the specific decision that needs changing.

Text-to-image is an independent image source, with or without supplied style guidance.
Use it to establish a complete scene foundation or a coordinated asset
family, not as a sequence of unrelated one-off prompts. Generate a small candidate
set under the same projection, palette, light direction, pixel density and scale;
select one candidate as the visual authority in host production data, with its
path, reference role and provenance. Resolve this initial choice before acceptance
freeze; the approved contract authorizes the concept scope and any spending.
Protect the selected image through acceptance comparisons and the production record
through check inputs. Routine candidate attempts do not edit the frozen contract. Subsequent
text-to-image requests must repeat those constraints and compare against that
authority. An accepted output may be used directly, sliced or layered without an
image-to-image pass. A model endpoint that cannot accept images can still be used,
but the agent must expect more rejection and authored normalization work.

Image-to-image is optional. Use it when an approved image must constrain layout,
identity, materials or composition, and use masked editing for bounded repairs.
Do not introduce an image-to-image step merely because a text-to-image result was
generated. Prefer it when repeated text-only attempts drift in projection, palette,
object scale or terrain language. Preserve the original and record every submitted
reference and mask.

Exact geometry does not require code-painted ground. When the selected technique
is a composed generated landscape, supply the host layout and style reference,
then measure interior path, doorway and crossing alignment before using the optional
[ground preparer](../consistent-tileset-authoring/references/composed-ground.md).
Prompts do not guarantee matching banks or paths; topology and collision remain
host-owned. If composition is flexible, a text-only concept may instead propose
the layout before freeze; explicitly derive/check geometry from it. A text-only
endpoint cannot consume a layout image. Select a compatible control method or
measure/reject mismatches; slicing is not registration. This is an alternative to
modular tiles, not a provider default.

For a composed ground request, translate the scene reference into the requested
layer's materials. "Terrain only" is ambiguous when the same prompt asks for
dense vegetation: specify low grass/soil/contact details versus separate upright
trees, rocks and structures. Keep the host's elevation and doorway levels explicit;
a flat footprint must not become a raised building plot merely because the style
reference has cliffs. Supply a clean layout image with declared reference roles,
using explicit ordered image inputs when the provider supports them. Record actual
submitted inputs as well as the prompt; intended references alone are not provenance.
Validate the guide's supported routes before spending, and inspect the callable
tool schema before declaring references unavailable. A missing mask/control field
does not imply missing image input; omitting the guide changes the tested technique.

For worked prompts for fixed-layout ground, a text-only concept and a targeted
repair, use [the composed-ground examples](references/composed-ground-prompts.md).
They are prompt patterns with explicit input roles, not guaranteed model outputs.

Inspect raw candidates for invented elevation, blocked approaches and baked
upright objects before registration or another generation. If one fails, preserve
it and revise the specific conflicting constraint. Do not repaint a convincing
but unsupported ledge as a walkable path or assume slicing fixes layer ownership.

## Test a candidate, then its connected area

Use the host's established projection, palette, light direction, target actor/prop
proportions, and intended source pixel density. Create one asset before a large
pack to test the image route. For environment production, derive this candidate
and the needed family variants from the [planned areas](../isometric-visual-loop/references/environment-composition.md).
A successful isolated asset does not approve the family or scene: assemble its
related surfaces and neighboring objects in the host before expansion. Separate
generation requests may serve one jointly designed area; no single-image or atlas
output is required. Favor controlled sets over an atlas whose exact cell layout
exists only in the prompt. Measure actual output dimensions.

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

Portable-cutout example only: "One compact orange marigold clump for a 2:1 isometric pixel-art
garden. Warm upper-left lighting, crisp clustered pixels, complete fine stems and
leaves, no pot, soil or cast shadow. Centered with generous margins on a uniform
contrasting backdrop. No text or checkerboard. Match the host's approved palette."
Replace the subject and palette with the actual game brief; a text-to-image
endpoint cannot see an unprovided reference. Its no-soil instruction is unsuitable
for a rooted contact patch; use the connected-area and grounded-object guidance
for scenery that must join its surroundings.

For a grounded object with measured contact and a targeted repair, adapt the
[grounded prop prompt patterns](references/grounded-prop-prompts.md). These
unvalidated examples preserve the distinction between a material swatch,
portable cutout and rooted patch; use the current host's intended layer split.

For static character views, use an accepted generated reference and explicit
facing instructions. Keep common canvas and contact origins across directions;
do not independently auto-trim them. Animated character motion requires the
directional I2V workflow, not generated pose frames.

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
   prediction ID, processing version/model, and any crop or canvas changes. Once the
   outputs are bound to the host manifest, run the
   [packed-art and acceptance checks](../isometric-visual-loop/references/acceptance.md).

Run remote work within the user's existing provider and spending authorization;
do not ask again when it already covers the action. Creating this skill alone
does not require a paid request. Keep credentials in the environment, never in
scene JSON, source files, or browser code. Keep temporary jobs and inspection
boards in the host's ignored evidence directory. Download accepted outputs to
host-owned files; temporary provider URLs are not production game assets.

Report generation, decoded alpha, visual mask quality, and in-game acceptance
separately. A local fallback's availability does not establish its quality on the
current art, and mocked API tests do not establish a successful paid generation.
