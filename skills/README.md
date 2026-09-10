# Agent skill catalog

Use this catalog from both [the project README](../README.md) and
[the agent instructions](../AGENTS.md). Select skills from the requested outcome,
then read their `SKILL.md` files before starting. These seven main workflows are
bundled with the source folder and npm package; no global installation is required.
Individual authoring tools may require additional dependencies or provider setup.

Choose visual direction from the current brief and supplied references. Bundled
example sprites and themes are not default inputs for these skills, including
generation references. Consult example implementations only for a specific need;
follow the [example-content boundary](../AGENTS.md#keep-example-content-out-of-new-games-by-default)
before reusing their content.

## Choose by task

| Requested work | Skill | Responsibility |
| --- | --- | --- |
| Create a complete world from a prompt or reference, or substantially refine an environment | [isometric-visual-loop](isometric-visual-loop/SKILL.md) | Overall scope, production brief, calibration, specialist coordination and playable visual review |
| Add an art pack or theme; fix proportions, anchors, seams or occlusion | [isometric-art-integration](isometric-art-integration/SKILL.md) | Shared projection, physical scale, contact measurements and in-game art acceptance |
| Generate raster sprites or textures; prepare transparent cutouts | [game-asset-generation](game-asset-generation/SKILL.md) | Provider workflow, background removal, decoded alpha and provenance |
| Create or repair character facings, walk/jump/attack poses or spritesheets | [directional-sprite-authoring](directional-sprite-authoring/SKILL.md) | Visible facing approval, coherent poses, stable frame contacts and explicit clip mapping |
| Animate rivers, fountains, waterfalls or wind-driven plants | [animated-environments](animated-environments/SKILL.md) | Stable scenery loops, matching joins and simulation timing |
| Build large or multipart props, buildings, bridges or raised passages | [multi-tile-asset-assembly](multi-tile-asset-assembly/SKILL.md) | Solid volumes, walkable surfaces, openings, sprite contacts and depth parts |
| Build connected beds, paths, walls or water with compatible edges | [consistent-tileset-authoring](consistent-tileset-authoring/SKILL.md) | Shared material geometry, neighbor variants, inner corners and rendered join checks |

## Combine only what the task needs

- **Complete village:** start with `isometric-visual-loop`; select specialists for
  its buildings, terrain, characters and motion. Calibration is a milestone toward
  the requested world, not the final scope.
- **Generated animated fountain:** define its structure with
  `multi-tile-asset-assembly`, calibrate with `isometric-art-integration`, produce
  candidates with `game-asset-generation`, and build the loop with
  `animated-environments`.
- **Character facing repair:** start with `directional-sprite-authoring`; use
  generation only if new artwork is needed and art integration for scale checks.
- **Connected river:** combine `consistent-tileset-authoring` for banks and joins
  with `animated-environments` for flowing water; add generation if requested.

A focused task can start directly with its specialist. Unrelated gameplay or
engine fixes follow [module ownership](../AGENTS.md#choose-the-owner-before-editing)
and do not require a world-production workflow. Follow explicit user constraints
on assets, motion, tools and scope. Generated-art requests require actual generated
outputs, and passing metadata checks alone does not establish visual quality.

## Historical trial variants

These nested `SKILL.md` files are comparison workflows retained under
`animated-environments/references/variants/`, not additional default production
skills. Read them when reproducing or studying the historical trials:

- [environment-animation-first](animated-environments/references/variants/environment-animation-first/SKILL.md)
- [environment-contract-first](animated-environments/references/variants/environment-contract-first/SKILL.md)
- [environment-topology-first](animated-environments/references/variants/environment-topology-first/SKILL.md)

For current environment work, use the main skills above. See
[the generated environment trial](../docs/GENERATED_ENVIRONMENT_TRIAL.md) and
[verification instructions](../AGENTS.md#work-and-verification) for evidence and
the historical comparison's known limitations.

When adding, renaming or retiring a main skill, update this table and keep both
entry points linked here. Keep operational instructions in the individual skills.
