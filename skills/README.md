# Agent skill catalog

Select skills from the requested outcome,
then read their `SKILL.md` files before starting. These seven main workflows are
bundled with the source folder and npm package; no global installation is required.
Individual authoring tools may require additional dependencies or provider setup.

Choose visual direction from the current brief and supplied references. Bundled
example sprites and themes are not default inputs for these skills, including
generation references. Each skill's supporting references use neutral examples
and measurements; replace illustrative values with the current host's own data.
Do not route production work through historical trial reports or example art.

For world production, use the [packed-art and acceptance gates](isometric-visual-loop/references/acceptance.md)
inside `isometric-visual-loop`. They check the delivered atlas, required reviews
and evidence freshness; they do not replace visual judgment. Focused art repairs
can use the same checks with a smaller requirement scope.

## Choose by task

| Requested work | Skill | Responsibility |
| --- | --- | --- |
| Create a complete world from a prompt or reference, or substantially refine an environment | [isometric-visual-loop](isometric-visual-loop/SKILL.md) | Overall scope, production brief, calibration, specialist coordination and playable visual review |
| Add an art pack or theme; fix pasted-on scenery, proportions, seams or occlusion | [isometric-art-integration](isometric-art-integration/SKILL.md) | Object-ground connections, shared scale, contact measurements and in-game acceptance |
| Generate raster sprites or textures; prepare transparent cutouts | [game-asset-generation](game-asset-generation/SKILL.md) | Project-selected Retro Diffusion MCP, WaveSpeed or other provider; background removal, decoded alpha and provenance |
| Create or repair character facings, walk/jump/attack poses or spritesheets | [directional-sprite-authoring](directional-sprite-authoring/SKILL.md) | Visible facing approval, coherent poses, stable frame contacts and explicit clip mapping |
| Animate rivers, fountains, waterfalls or wind-driven plants | [animated-environments](animated-environments/SKILL.md) | Stable scenery loops, matching joins and simulation timing |
| Build large or multipart props, buildings, bridges or raised passages | [multi-tile-asset-assembly](multi-tile-asset-assembly/SKILL.md) | Solid volumes, walkable surfaces, openings, sprite contacts and depth parts |
| Build connected beds, paths, walls or water with compatible edges | [consistent-tileset-authoring](consistent-tileset-authoring/SKILL.md) | Shared material geometry, neighbor variants, inner corners and rendered join checks |

## Choose the art technique

Make two separate decisions from the approved project contract: how the world is
assembled, then where each asset family's pixels come from. Select a provider only
when generation is needed. Text-to-image alone does not choose a world architecture.

| World assembly | Read first | Support and remaining work |
| --- | --- | --- |
| Reusable modular terrain | Tileset authoring | Suitable for editable/recombined maps. Neighbor selection exists; organic material-pair transitions need a compatible catalog or scoped host assembler. The raised-bed helper is not that assembler. |
| Composed ground plus separate actors/props | Tileset authoring: composed ground; art integration | Suitable when the ground layout is largely fixed and material transitions should be composed together. Flat-plane preparation/binding exist; crops remain position-specific. Registration, object contacts and motion need their own checks. |
| Layered scene artwork | Art integration; multi-tile assemblies | Suitable when selected occluders and moving regions can be separated. Extraction, hidden surfaces and depth bindings require host work. |
| Hybrid by region/family | Visual loop and relevant specialists | Declare the boundaries and shared coordinates; verify a representative join before expansion. |

For each family choose **supplied/licensed, authored, text-to-image, image-to-image,
or a combination**. All can feed the assembly choices above. Text-to-image can
establish a scene or material/asset family; image-to-image can preserve selected
reference properties. Neither guarantees registration, usable layers or animation.
Elevated/multiple-floor compositions and branching water require scoped host
integration beyond the flat-ground adapter and sprite clip support. Prove the
needed capability during calibration before producing a full pack.

Add asset generation only when new generated artwork is part of the chosen path.
Read one provider recipe when needed. The same visual, traversal and promised
motion outcomes apply to all techniques; tools do not select the art direction.
Text-to-image does not require an existing reference image. Once a candidate is
accepted, record it in host production data and use it with the contract as the visual authority for palette, projection,
scale, lighting and pixel treatment. Do not regenerate every family from unrelated
text prompts. Image-to-image is a control option for later consistency or repair,
not a prerequisite for generated art.

## Common combinations

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
- **Composed ground image:** use the optional
  [ground preparer](consistent-tileset-authoring/references/composed-ground.md)
  for a plate or positioned chunks from authored, supplied or generated artwork.
  Choose generation only when agreed; reusable transition tiles remain another path.

A focused task can start directly with its specialist. Unrelated gameplay or
engine fixes follow the project's module ownership
and do not require a world-production workflow. Follow explicit user constraints
on assets, motion, tools and scope. Generated-art requests require actual generated
outputs, and passing metadata checks alone does not establish visual quality.

When adding, renaming or retiring a main skill, update this table and keep both
entry points linked here. Keep operational instructions in the individual skills.
Keep reusable examples within their owning skill. Extract the general method from
an incident; do not link a skill to that incident's host, captures or art records.
