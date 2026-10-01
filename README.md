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

Replace the brief and reference fields with your project. Existing decisions and
an approved contract take precedence over these placeholders.

```text
Build an original standalone isometric pixel-art game using
https://github.com/DomEscobar/isometric-framework.

My brief: [player experience, setting, requested world size and features]
Visual references: [attached images or paths; style-only unless stated otherwise]
Current scope and exclusions: [for example: landscape first; no residents, pets or sound]

1. Establish the project and contract.
Use the current local framework checkout when supplied; read AGENTS.md,
docs/CREATE_GAME.md and skills/README.md there. Preserve my existing decisions.
Ask at most three consequential unanswered questions, then draft one
PROJECT_CONTRACT.md for approval before implementation or paid generation.
If it is already approved, continue without asking again. Use the standalone
starter and public runtime API; keep game code and assets in the game project.
References guide style unless I explicitly request their layout. Create an
original composition and assets rather than borrowing framework examples.

2. Follow the bundled workflow.
Read skills/isometric-visual-loop/SKILL.md and its references/landscape-iteration.md,
references/landscape-verification.md and references/asset-policy.md. For ground,
also read skills/consistent-tileset-authoring/SKILL.md and its
references/landscape-ground-assembly.md. In a scaffolded host, these paths are
under node_modules/isometric-framework/. Use acceptance-plan v5 / production v2
for a new landscape and production next to follow the existing six stages.
Preserve an approved older plan until an explicit migration establishes a fresh baseline.

3. Calibrate before producing the asset collection.
Plan the complete requested world first. Establish source/export pixel density,
world scale, playing zoom, viewport/DPR and renderer limits. Prove a connected
pilot with representative ground and differently sized objects. Distinguish
visible sprite bounds, physical footprint, collision, build reserve, entrance,
contact anchor and depth sorting. Record user choices, delegated agent selections,
recommendations and rejected/stopped studies separately. Continue routine work
within the approved scope; do not silently restart canceled experiments.

4. Build terrain from one host-owned geometry export.
Derive semantic masks, routes, water, supports and object transforms from the
same world definition used by placement checks. For continuous natural ground,
prefer generated-material quilting unless another approach is already approved.
Use this order: continuous materials -> regional path surfaces -> outer path
edges and water/land contacts -> object-specific underlays -> upright objects
-> bind-ground.mjs. Use compose-landscape-ground.py for the composition passes.
Keep routes clear; vary materials by region without changing their walkability.
Border the exterior of the combined path, including junctions. Use local contact
art and masks for soft transitions. Protect road/water pixels during the object
underlay pass. Match each underlay to its object's anchor and scale; avoid universal
oval pads or global blur. Preserve host collision and bridge/floor semantics.

5. Produce only the agreed content.
Generate visible world/character art or reuse accepted generated sources with
provenance. Follow the asset policy's approved facing -> image-to-video -> reviewed
video -> extraction/alpha review -> packing -> runtime-review chain for character animation.
Technical blockouts, masks, collision and UI are exempt. Preserve spending
permissions; missing provider access or budget blocks generation. Expand the
successful pilot to the full contracted dimensions, regions and asset families.
A calibration scene is a milestone, not completion of the requested world.

6. Verify independently against the rubric.
Capture registered ground-only/dressed pairs at the same camera and world/time
state, plus whole-map views and representative details at playing scale. Bind
actual image hashes and capture metadata to current geometry and sources.
Delegate visual review to a subagent that did not build the scene. It must open
the images and apply the landscape rubric: reference/pixel treatment, composition,
route clarity, material continuity/outer edges, water-bank-grass transitions,
object grounding, scale/footprint/blocking, access/bridges, deliberate variation,
and full requested extent. Record localized observations and pass/fail/unverified
per criterion and required view; repair failures and capture fresh evidence.
If independent image review is unavailable, leave it unverified.

Playtest the actual host within scope. Keep build/geometry, visual, motion,
gameplay/input, touch and performance verdicts separate. Label emulated touch
accurately. Report remaining failures and unverified requirements; neither a
passing build nor synthetic fixtures constitute acceptance of the game's art.
```

## Use the skills

Read [the skill catalog](skills/README.md) and select only the workflows the game
needs. For a complete world or substantial visual work, start with
[isometric-visual-loop](skills/isometric-visual-loop/SKILL.md); it coordinates
layout, asset integration, animation, and acceptance. Its
[landscape iteration recipe](skills/isometric-visual-loop/references/landscape-iteration.md)
covers early density/scale checks, controlled variants, grounded placement and
whole-map review. Use specialist skills for
focused tasks. Treat references as style-only unless the user requests layout or both.

For new landscapes, follow [v5 landscape verification](skills/isometric-visual-loop/references/landscape-verification.md)
and [offline ground assembly](skills/consistent-tileset-authoring/references/landscape-ground-assembly.md).
Existing approved v4 plans remain supported; a v5 migration needs a new baseline
and fresh evidence for added or changed checks.


## Maintain the framework

This checkout also contains the runtime and historical reference hosts. For engine
development, package work, examples, and framework verification, read
[the contributor guide](https://github.com/DomEscobar/isometric-framework/blob/main/CONTRIBUTING.md). Public API usage is in
[docs/RUNTIME_API.md](docs/RUNTIME_API.md).

## License and notices

See [PROVENANCE.md](PROVENANCE.md).
