# Isometric Framework

Build an isometric game in TypeScript with a portable runtime, browser controls,
and agent workflows for original worlds. The framework ships with playable
references for learning and maintenance; a new game starts as its own project.

## Create a clean game project

Use Node.js 22.18 or newer. From this framework checkout, build the local package
and scaffold a separate destination:

```sh
npm ci
npm run build:package
node scripts/create-game.mjs <destination>
```

The scaffold vendors this local package; it does not assume a package has been
published to a registry. Its generated README contains its own `npm install`,
`npm run dev`, `npm run check`, and `npm run build` commands. Follow
[the new-game guide](docs/CREATE_GAME.md) after scaffolding.

Keep your maps, rules, assets, and UI in that project. Use the framework through
its public API. Do not copy `demo/` or an `examples/` host into a new game unless
you intentionally want to extend that specific work and record its provenance.

## Copy this prompt into your coding agent

```text
Use https://github.com/DomEscobar/isometric-framework and its new-game guide
to build a standalone game. Read the relevant bundled skills before implementation.

I want an original playable isometric pixel-art game: a lively connected town
and forest with creature encounters, catching, and battles. Make the route
between both places clear, with expressive creatures, animated foliage and water,
and readable movement and battle actions.

Treat any attached image as a style reference by default, not a layout to copy.
If I explicitly request layout reference or both style and layout, follow that
request. Create this game's own identity and assets; do not reuse framework
examples.

Help me choose the concept before coding or paid asset generation. Ask no more
than three important questions at a time, then draft one PROJECT_CONTRACT.md for
me to approve. If I have already approved a contract, preserve it and continue;
do not request repeated approval. That contract is the source of truth for the
player experience, scope, style, asset approach, and acceptance requirements.
Derive technical plans from it; do not create a competing art brief. Once it is
approved, use the standalone starter and new-game guide to implement the game.

I may use existing, authored, generated, composed, or layered assets. Preserve
choices I have already made. Ask about provider and budget only when generation is
needed. Calibrate a small playable assembly, then complete the whole agreed world;
do not shrink a rich request to the calibration scene. Playtest the real game and
review visuals, motion, gameplay, and performance separately before declaring it
complete.
```

## Use the skills

Read [the skill catalog](skills/README.md) and select only the workflows the game
needs. For a complete world or substantial visual work, start with
[isometric-visual-loop](skills/isometric-visual-loop/SKILL.md); it coordinates
layout, asset integration, animation, and acceptance. Use specialist skills for
focused tasks. Treat references as style-only unless the user requests layout or both.

## Maintain the framework

This checkout also contains the runtime and historical reference hosts. For engine
development, package work, examples, and framework verification, read
[the contributor guide](https://github.com/DomEscobar/isometric-framework/blob/main/CONTRIBUTING.md). Public API usage is in
[docs/RUNTIME_API.md](docs/RUNTIME_API.md).

## License and notices

See [PROVENANCE.md](PROVENANCE.md).
