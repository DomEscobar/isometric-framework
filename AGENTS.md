# Working with Isometric Framework

Decide which job is being done before editing.

## Building a game

The default is a clean, standalone project, created with the local scaffold:

```sh
npm ci
npm run build:package
node scripts/create-game.mjs <destination>
```

The scaffold vendors the local framework package, so it does not depend on a
published registry release. Work in the generated project and follow its README
plus [docs/CREATE_GAME.md](docs/CREATE_GAME.md). Do not modify the framework's
starter template or scaffold while implementing a game. The generated host is
your project: edit its package, entry point, and game files as the game requires.

Start with the player's desired experience. Ask up to three consequential
questions, draft one `PROJECT_CONTRACT.md`, and wait for approval before
implementation or paid generation. The contract is the sole source for user
requirements; technical plans derive from it and must not become a competing art
brief. Preserve decisions already supplied. New visible world and character art
must be generated; reuse accepted generated art with its provenance. Character
animation must use image-to-video, reviewed extraction and packing. Scenery/object
animation may use image-to-video or another suitable technique on generated art.
Blockout geometry, UI, masks and diagnostics are exempt. Use version 4 production
gates; missing provider access or budget blocks generation, not a silent fallback.
Once the contract is already approved, continue
from it without asking for approval again.

Read [the skill catalog](skills/README.md), then the selected `SKILL.md` files.
For rich worlds, begin with
[isometric-visual-loop](skills/isometric-visual-loop/SKILL.md). A small
calibration assembly proves the approach; it never limits the requested final
world. Complete connected traversal, atmosphere, animation, and the agreed game
loop when those are in scope.

`demo/` and `examples/` are references, never a starter asset library. Do not
copy their hosts, sprites, maps, palettes, characters, layouts, or asset URLs into
a new game. A supplied image is style-only by default, unless the user explicitly
requests layout reference or both. Reuse example material only when explicitly
requested or when modifying that same host; record provenance in that case.

## Maintaining the framework

Read [CONTRIBUTING.md](CONTRIBUTING.md) before changing `src/`, package scripts,
the scaffold, skills, or reference hosts. Keep game-specific rules in game hosts
and reusable capability in the engine. Historical trials support framework
evaluation only; they are not a game-production workflow.
