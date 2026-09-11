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

Use existing, authored, generated, composed, or layered work according to the
contract. Preserve decisions already made. Ask about a provider and generation
budget only when generation is needed.

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

Build one small playable assembly with the game's own actor, terrain, prop, and
required motion. Use it to check proportions, contacts, routes, clips, and an
observable rule. It is a technical milestone, not the final scope. A request for
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
for world production. Preserve the contract requirements, inspect current packed
actor clips and animated overlays, compare target/previous/current captures after
repairs, and keep visual, motion, gameplay, and performance verdicts separate.

Run the generated project's checks and play the actual game in a browser at desktop
and touch sizes where applicable. A passing type check or build does not prove the
playable journey, visual quality, motion, or performance. Report every unverified
requirement plainly.

The framework's historical trial recorder and trial documents are for framework
evaluation only. They are not required for a normal game project.
