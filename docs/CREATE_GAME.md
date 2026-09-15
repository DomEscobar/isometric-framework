# Create a standalone game

This guide is for a new game, not for modifying the framework or cloning a
reference host. Use a clean destination so the game owns its code, assets, rules,
and release choices.

## 1. Scaffold the project

From the framework source checkout, with Node.js 22.18 or newer:

```sh
npm ci
npm run build:package
node scripts/create-game.mjs <destination>
```

The destination must be new, empty, or contain only an existing
`PROJECT_CONTRACT.md`, which the starter preserves. Other existing files cause
an error rather than being overwritten. The scaffold vendors the local framework package. It does not require a published
registry version. Change into `<destination>` and use the generated README for
that project's `npm install`, `npm run dev`, `npm run check`, and `npm run build`
commands.

Do not start by copying `demo/` or `examples/`. They are capability references,
and their art, maps, assets, and layouts stay there unless reuse was specifically
requested and recorded. An image reference guides style; it does not supply a
layout to reproduce by default. Follow an explicit request for a layout reference,
or for both style and layout.

## 2. Agree the project contract before production

Before implementation or paid generation, help the player decide the game. Ask at
most three consequential questions at a time, then create `PROJECT_CONTRACT.md`
in the game project for approval. It is the single source of user requirements:
player experience, scope, visual direction, asset choices, and acceptance needs.
Technical planning comes from that contract; do not maintain a separate competing
art brief.

If the contract is already approved, preserve it and proceed without requesting a
second approval.

Concept discussion may happen before scaffolding. Keep the approved contract in
the intended destination; the starter carries it forward without replacing it.
If scaffolding first for a setup check, its pending contract and neutral graphics
are placeholders, not approved product choices.

Choose world assembly (modular terrain, composed ground, layered scene or hybrid).
New visible world and character art must be generated through text-to-image or
image-to-image; accepted generated art may be reused with provenance. Character
animation must follow approved generated facing image -> image-to-video ->
reviewed extraction -> alpha review -> packing -> runtime review. Preserve usable
video alpha; otherwise inspect one color-key candidate. Halos, holes, lost subject
colors, flickering contours or uncertainty require the approved background remover
on selected unkeyed frames before packing. Scenery/object animation may
use image-to-video or another fitting method on generated material. UI, collision,
masks and technical blockouts are exempt. Follow the [asset policy](../skills/isometric-visual-loop/references/asset-policy.md).
Preserve existing decisions and budget approvals. Missing access or budget blocks
generation; do not replace required generated art with handmade substitutes.

Under the approved contract, resolve missing visual direction and rough layout
before freezing acceptance. Fixed gameplay geometry constrains art; a flexible
text-to-image concept may propose composition from which the host derives and checks
routes/supports. Record the selected image, role and provenance in host production
data; protect the image in acceptance comparisons. Do not edit a frozen contract
for routine asset attempts. Freeze before playable calibration implementation or
full-pack production. This bounded preparation still respects spending approval.

## 3. Select the relevant skills

Read [the skill catalog](../skills/README.md). For a complete environment or a
large visual change, start with
[isometric-visual-loop](../skills/isometric-visual-loop/SKILL.md), then add only
the specialists the contract requires:

- [art integration](../skills/isometric-art-integration/SKILL.md) for new art;
- [asset generation](../skills/game-asset-generation/SKILL.md) for generated or
  prepared raster art;
- [directional sprites](../skills/directional-sprite-authoring/SKILL.md) for
  actor movement and actions;
- [animated environments](../skills/animated-environments/SKILL.md) for water,
  foliage, and scenery loops;
- [multi-tile assembly](../skills/multi-tile-asset-assembly/SKILL.md) for large
  buildings, bridges, and collision surfaces;
- [consistent tilesets](../skills/consistent-tileset-authoring/SKILL.md) for
  connected terrain, paths, walls, and water.

## 4. Calibrate, then build the agreed world

Plan the whole scene and its connected areas before deriving the asset list; use
[environment composition](../skills/isometric-visual-loop/references/environment-composition.md).
Build one representative playable area with related objects, adjoining surfaces,
useful open space, the game's actor and required motion. Check proportions,
relationships, contacts, routes, clips and an observable rule. It is a technical
milestone, not the final scope. A request for
a lively connected town and forest, for example, still requires the full agreed
regions, traversal, atmosphere, animation, and creature loop.

Keep maps, rules, inventory, rewards, UI, and custom effects in the host. Use the
public runtime APIs for reusable movement, collision, rendering, input,
interactions, saves, and diagnostics. See [RUNTIME_API.md](RUNTIME_API.md),
[ART_PIPELINE.md](ART_PIPELINE.md), [INTERACTIONS.md](INTERACTIONS.md), and
[INVENTORY_AND_SAVES.md](INVENTORY_AND_SAVES.md) as needed.

## 5. Prove the actual game

Use the visual loop's [acceptance gate](../skills/isometric-visual-loop/references/acceptance.md)
and [production stages](../skills/isometric-visual-loop/references/production-flow.md)
with plan version 4 for world production. `production next` reports the next
allowed stage, pending checks and missing inputs. A layout needs both spatial
checks and actual blockout image review. Production acceptance verifies asset
provenance against the runtime export as well as completed stage evidence;
`npm run build` remains a separate technical check. Preserve the contract requirements, inspect current packed
actor clips and animated overlays, compare target/previous/current captures after
repairs, and keep visual, motion, gameplay, and performance verdicts separate.

Run the generated project's checks and play the actual game in a browser at desktop
and touch sizes where applicable. A passing type check or build does not prove the
playable journey, visual quality, motion, or performance. Report every unverified
requirement plainly.

The framework's historical trial recorder and trial documents are for framework
evaluation only. They are not required for a normal game project.
