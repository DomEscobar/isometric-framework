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
| Sunflower courtyard and small gameplay demos | [Main demo](http://127.0.0.1:4175/) |
| Autumn river and stone bridge | [Goldlaub](http://127.0.0.1:4175/examples/autumn-crossing/) |
| Shops and canal crossing | [Weidenkai](http://127.0.0.1:4175/examples/willow-quay/) |
| Animated scenery and multipart structures | [Environment lab](http://127.0.0.1:4175/examples/environment-lab/) |
| Connected terrain and borders | [Autotile lab](http://127.0.0.1:4175/examples/autotile-lab/) |

Click or tap to walk. **W ↗ · D ↘ · S ↙ · A ↖** follows the tile axes.
**Space** jumps. Mobile examples provide a directional pad. Drag to pan;
use the mouse wheel or available controls to zoom.

## Make your own game

Start with [the new-game guide](docs/CREATE_GAME.md). Put your map, artwork and
rules in `examples/my-game/`, or replace `demo/` for a project with one game.
Keep reusable engine code in `src/`.

For a coding agent, start with [AGENTS.md](AGENTS.md). Then describe the world:

> Create a lively autumn village with shops, a winding river, an old stone bridge
> and a large fountain. Make it explorable on desktop and mobile.

The bundled [world-production skill](skills/isometric-visual-loop/SKILL.md)
coordinates layout, consistent art, complex structures, animation and visual
checks. Asset generation uses an available provider; it is separate from running
the game. Small calibration scenes are milestones, not a limit on the final world.

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
