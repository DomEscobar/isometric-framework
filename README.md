# Isometric Framework

Build isometric games with TypeScript. Includes a standalone runtime, playable
examples, local artwork and skills that help coding agents create complete worlds.
No backend or account is needed to run the examples.

## Start

Install **Node.js 22.18 or newer**, then run from this folder:

```sh
npm ci
npm run dev
```

Open **[localhost:4175](http://127.0.0.1:4175)**.
If that port is busy, use `npm run dev -- --port 4177` and open port 4177 instead.

## Try the examples

| Example | Address after starting the server |
| --- | --- |
| Generated-sprite town and visual comparison trial | [Pixel Borough](http://127.0.0.1:4175/examples/pixel-borough/) |
| Generated village with connected ground, brook and crossing (final acceptance open) | [Larkspur Crossing](http://127.0.0.1:4175/examples/new-village/) |
| Sunflower courtyard and small gameplay demos | [Main demo](http://127.0.0.1:4175/) |
| Twilight town and connected enchanted forest | [Mossbell](http://127.0.0.1:4175/examples/mossbell/) |
| Autumn river and stone bridge | [Goldlaub](http://127.0.0.1:4175/examples/autumn-crossing/) |
| Shops and canal crossing | [Weidenkai](http://127.0.0.1:4175/examples/willow-quay/) |
| Animated scenery and multipart structures | [Environment lab](http://127.0.0.1:4175/examples/environment-lab/) |
| Connected terrain and borders | [Autotile lab](http://127.0.0.1:4175/examples/autotile-lab/) |

Click or tap to walk. **W ↗ · D ↘ · S ↙ · A ↖** follows the tile axes.
**Space** jumps. Mobile examples provide a directional pad. Drag to pan;
use the mouse wheel or available controls to zoom.

## Make your own game

Bundled examples demonstrate capabilities; their sprites and visual themes are
not defaults for your game. Agents should follow your brief and supplied references,
consult example code only as needed, and reuse example artwork only when requested.
See [the example-content boundary](AGENTS.md#keep-example-content-out-of-new-games-by-default).

Start with [the new-game guide](docs/CREATE_GAME.md). Put your map, artwork and
rules in `examples/my-game/`, or replace `demo/` for a project with one game.
Keep reusable engine code in `src/`.

### Copy this prompt into your coding agent

Attach a style-reference image with the prompt, or let the agent help you choose
a direction. Change the world idea below to suit your game.

```text
Use https://github.com/DomEscobar/isometric-framework to create a beautiful,
playable isometric pixel-art game. Read its AGENTS.md, new-game guide and relevant
bundled skills first.

Let's decide what to build together before coding or generating assets.
My idea: two tiny connected worlds, a little town and a forest where I can
encounter, catch and battle original Pokémon-like monsters. Make both places
feel alive, with expressive creatures, animated foliage, flowing water where
appropriate, and readable movement and battle actions. Keep the maps compact
and thoughtfully detailed, with a clear route between them.

Compose the ground as a continuous landscape: naturally worn paths blending into
grass, coherent stream banks, and material variation spanning several tiles.
Avoid obvious repeating diamonds, mirrored texture stamps and mismatched pixel
styles. Review a connected ground patch before adding decorative props.

Use my attached image as the pixel-art style reference, not a layout to copy.
If no image is attached, help me choose the style before producing art. Create
this game's own identity and assets; don't inherit bundled example artwork.

Start with a short concept and a manageable exploration/catching/battle loop.
Ask up to three important questions at a time, offering concrete choices and
recommendations. Help me choose the pixel style, environment detail, asset
technique and provider (Retro Diffusion MCP, WaveSpeed, or another available
option), including a generation budget. Reuse decisions I've already supplied.
Draft a short project contract for me to confirm; don't make me write it.
Wait for agreement before implementation or paid generation.

Once agreed, record the contract in the new host and follow it. Calibrate a small
scene with our own actor, terrain, prop and animation, then finish both worlds
and the agreed gameplay. Playtest in the browser, inspect actual sprite clips
and environmental motion, and repair visual defects before calling it done.
Use the framework's acceptance checks and report any unverified requirements.
Compare our visual target with actual game screenshots after each repair; include
the previous version and require concrete, image-located feedback.
```

The bundled [world-production skill](skills/isometric-visual-loop/SKILL.md)
coordinates layout, consistent art, complex structures, animation and visual
checks. Choose an asset production path with the agent: Retro Diffusion MCP,
WaveSpeed Seedream, another available provider, or authored/supplied assets.
The [generation skill](skills/game-asset-generation/SKILL.md) documents these
options; generation is separate from running the game. Small calibration scenes
are milestones, not a limit on the final world.

## Choose an agent skill

The [skill catalog](skills/README.md) lists all seven bundled workflows with task
triggers and combinations: world production, art integration, asset generation,
directional sprites, animated scenery, multi-tile assemblies and connected tilesets.
Start with world production for a complete environment; use a specialist directly
for a focused task. Agents should infer relevant skills from your request.

Open the linked `SKILL.md` files even if your agent does not discover them
automatically. No global skill installation is required. Authoring dependencies
and provider setup are described in each skill; they are separate from running
the game. Skill references use neutral examples owned by their workflow.

World production includes a [visual acceptance gate](skills/isometric-visual-loop/references/acceptance.md):
decoded atlas checks, a browser preview, protected requirements, and separate
visual/motion/gameplay/performance reviews tied to the current files. It rejects
missing or stale evidence; artistic quality still requires actual review. A passing
build alone does not mean a world's visuals are accepted.
The [image comparison loop](skills/isometric-visual-loop/references/visual-comparison.md)
assembles target, previous and current captures for actual visual review, then
checks that located defects were revisited after repairs. It does not score beauty.
New worlds use [six production stages](skills/isometric-visual-loop/references/production-flow.md):
technical preflight, spatial layout, representative assembly, complete scene,
motion and final review. Failed prerequisites block the tool's next stage; placement
checks catch roots on paths, blocked entrances and broken bridge support.

## What's included

- Tile-axis movement, click paths, jumping, stacked floors and collision.
- Sprites, animation clips, terrain connections and depth ordering.
- Optional interactions, inventory, saves and debug tools.
- Source artwork, authoring scripts, agent skills and tests.

| Folder | Contents |
| --- | --- |
| `src/` | Reusable engine |
| `demo/`, `examples/` | Games, scene data and artwork |
| `skills/` | Agent workflows and asset tools |
| `docs/` | API, guides and recorded limitations |
| `scripts/`, `tests/` | Development tools and checks |

## Useful commands

```sh
npm run check   # TypeScript and module boundaries
npm test        # Headless tests
npm run build  # Library + all browser examples
npm run preview
```

For browser tests, install Chromium once with `npx playwright install chromium`,
then run `npm run test:browser`.

This is an evolving 2.5D framework, not a full editor or 3D physics engine.
Art examples are experiments; they do not promise finished production quality.
See [API usage](docs/RUNTIME_API.md), [architecture](docs/ARCHITECTURE.md),
[example controls](APP_GUIDE.md) and [source/license notices](PROVENANCE.md).
