# Sprite and texture module

Use this module to give a game its own art direction without changing engine
rendering code. The headless `isometric-framework/art` entry defines and
validates asset manifests. The runtime owns image loading, atlas regions, sprite
presentation, animation, and disposal. Game-specific art stays with the host.

## Give the art a consistent contract

For neighboring tiles and borders, pair [AUTOTILING.md](AUTOTILING.md) with
[consistent-tileset-authoring](../skills/consistent-tileset-authoring/SKILL.md).
The resolver chooses masks; the skill prepares compatible geometry and generated
materials. Test concave corners and holes before adding flowers or other props.
Independent full-tile generation is not a reliable shared-edge contract.

Choose ground assembly separately from its artwork source: reusable transition
tiles suit recombinable maps; composed plates or positioned chunks suit fixed
landscapes. Either can use authored, supplied, procedural or generated material.
The optional [offline ground preparer](../skills/consistent-tileset-authoring/references/composed-ground.md)
handles explicit image transforms, masks and extraction for the composed route.
Record the choice in the existing host brief; it adds no runtime API or provider.
For the public runtime on a flat ground plane, the recipe's `bind-ground.mjs`
adapter maps one registered plate to existing per-cell texture frames. Prepared
`placements` alone are not a runtime scene or a plate-placement interface.

For animated rivers, fountains or vegetation, apply
[animated-environments](../skills/animated-environments/SKILL.md). Pair it with
[multi-tile-asset-assembly](../skills/multi-tile-asset-assembly/SKILL.md) for large
props, buildings and bridges. The latter includes an executable assembly-plan
checker for contact placement, occupancy, solid heights, paths and slab clearance.
It complements the art calibration tools; neither static checker proves visible
quality or swept jump collision. The [workflow comparison](ENVIRONMENT_SKILL_COMPARISON.md)
records why a walking-only test missed two fountain collisions.

For new raster artwork or background removal, start with the portable
[game-asset-generation skill](../skills/game-asset-generation/SKILL.md).
It provides a WaveSpeed Seedream path, an explicit background-removal step,
local CPU rembg instructions, and decoded-alpha review. Any available provider
can supply candidates; GPT ImageGen is not required. Keep provider credentials
and authoring dependencies outside runtime code and exported scenes.

Apply the portable [isometric-art-integration skill](../skills/isometric-art-integration/SKILL.md)
when integrating a pack or diagnosing alignment and proportion defects. It
provides a measured authoring contract, a dependency-free checker, an overlay
board, and separate visual/gameplay acceptance checks. Metadata validation alone
cannot establish that sprite bases fit the tiles or that furniture fits a player.

Before drawing or choosing assets, record these decisions in the host game's art
directory. An agent should be able to add an asset without guessing its scale.

| Decision | Example |
| --- | --- |
| Projection | 2:1 isometric terrain, matching 72 by 36 world tiles |
| Palette and materials | Moss greens, warm limestone, amber highlights |
| Lighting | Upper-left light; consistent shaded faces on every prop |
| World scale | Shared height units with measured player, seat, tabletop, and door landmarks; do not use padded image widths as physical units |
| Ground contact | Character feet at frame anchor `(0.5, 1)`; use actual contact for props |
| Sampling | `nearest` for pixel art, `linear` for smooth illustrations |
| Animation cells | Equal canvas dimensions and consistent foot contact across frames |
| Source record | Asset origin, author, license, and source files kept with the game |

Use transparent backgrounds for characters and props. Avoid baked backgrounds or
inconsistent camera angles. Keep decorative shadows consistent with the lighting.
Image dimensions are presentation; occupied grid footprint and physical body
height are separate choices. A large tree crown does not need a large blocking
footprint, but its trunk should line up with the blocked cell.

## Define named resources

Raised terrain may set `sideTexture` to a named manifest texture. The renderer
repeats its vertical pixels down the side faces and applies the existing face
shading. It crops repeats within the named atlas frame; it does not stretch a
single frame over the full cliff height. This controls appearance only: tile
`elevation` and floor height still define the physical surface and slab.

An asset manifest contains image sources, named texture regions, and optional
animation clips. IDs are scoped to the scene. Paths resolve against the hosting
document; when using Vite, import local art with `?url` so production builds retain
the correct URL. Do not depend on another repository's asset server.

Scene exports preserve the manifest's references, not the image bytes. When moving
a saved scene to another host, also transfer its artwork and adapt URLs to that
host's asset paths. A development-server URL may differ from a bundled build URL.

```ts
import { validateAssetManifest } from 'isometric-framework/art';

const assets = validateAssetManifest({
  images: {
    ranger: { url: '/art/ranger.png', sampling: 'nearest' },
    grass: { url: '/art/grass.png', sampling: 'nearest' },
  },
  textures: {
    // ranger.png must contain at least two adjacent 32 by 48 frames.
    'ranger.still': {
      image: 'ranger', frame: { x: 0, y: 0, width: 32, height: 48 },
      anchor: { x: 0.5, y: 1 },
    },
    'ranger.step': {
      image: 'ranger', frame: { x: 32, y: 0, width: 32, height: 48 },
      anchor: { x: 0.5, y: 1 },
    },
    grass: { image: 'grass' }, // Entire image, no crop.
  },
  animations: {
    'ranger.idle': { frames: ['ranger.still'], fps: 1 },
    'ranger.walk': { frames: ['ranger.still', 'ranger.step'], fps: 8 },
    'ranger.jump': { frames: ['ranger.step'], fps: 1, loop: false },
  },
});
```

Frame rectangles use integer source pixels, with origin at the image's upper-left
corner. Omitted `frame` uses the whole image. No image downloads occur during
headless validation. Image bounds are checked after loading; a rectangle outside
its source image rejects the load.

The current module accepts explicit unrotated rectangles. It does not import
TexturePacker/Aseprite JSON, infer atlas grids, reverse trimming, or unpack rotated
frames. Convert such data into this manifest, preserving padding and anchors.
Use a small transparent gutter between atlas cells to avoid filtering bleed.

## Apply art to a scene

Assign the manifest to `scene.assets`. Tile definitions keep their existing color
for the base and slab sides; textures cover the diamond top. Top textures fit the
scene's tile width and height and are clipped to its diamond. Supply a diamond
image for deliberate isometric details, or a surface material for a simple fill.

```ts
// These definitions can be included in a complete Scene.
const grassTile = { color: 0x8ba575, texture: 'grass' };
const rangerType = {
  blocking: true,
  bodyHeight: 48,
  visual: {
    kind: 'sprite' as const,
    texture: 'ranger.still',
    width: 32,
    animations: {
      idle: 'ranger.idle', walk: 'ranger.walk', jump: 'ranger.jump',
    },
  },
};
```

Use `tile.textures: ['grass.a', 'grass.b', 'grass.c']` for terrain variation.
Selection is stable by cell coordinates and floor ID, including after reload and
export/import. It uses no random frame-time choices. Define either `texture` or
`textures`, not both. The public `selectTileTexture(tile, cell)` helper exposes
the same selection to host tools.

For a sprite, choose one base source: legacy `url`, legacy `frames`, named
`texture`, or named `animation`. Named sources use the scene manifest. Existing
URL/frame scenes remain supported. Optional state mappings require a named base.

- `width` sets display width while preserving the current frame's aspect ratio.
  `scale` then multiplies its visual size. Keep animation frame sizes consistent.
- `anchor` overrides the texture's normalized contact point. Entity textures
  default to bottom-center if neither provides one. It changes visual placement,
  not grid coordinates or pathfinding.
- `offset: {x, y}` is an additional visual offset in world pixels; do not use it
  to disguise incorrectly drawn feet. `tint` multiplies image color.
- `EntityType.bodyHeight` sets feet-to-head physical height in world pixels independently of
  sprite art. Choose it intentionally for projectile and ceiling collision.
  Grid `columns` and `rows` still define occupied cells.

## Animate in the correct direction

Use [directional sprite authoring](../skills/directional-sprite-authoring/SKILL.md)
to create and review turnarounds/action poses, then pack normalized frames into
explicit clips. The skill includes Seedream Pro Edit requests and a sheet packer;
neither filenames nor a generated row arrangement prove visible facing.

The runtime selects `idle`, `walk`, or `jump`. Add direction-specific clips under
`visual.animations.directions`, for example:

```ts
const directions = {
  ne: { walk: 'ranger.walk.ne' },
  se: { walk: 'ranger.walk.se' },
  sw: { walk: 'ranger.walk.sw' },
  nw: { walk: 'ranger.walk.nw' },
};
```

These IDs must also exist in `assets.animations`. Directions are screen compass
directions: W/Up moves northeast (`c+1`), D/Right southeast (`r+1`), S/Down southwest
(`c-1`), and A/Left northwest (`r-1`). Combined input can use `n`, `e`, `s`, and `w`
clips. Do not rotate this mapping to match a different sprite-sheet convention.

Selection falls back from directional state to general state, directional idle,
general idle, then the base animation. A named base texture remains available
when no animation resolves. Facing persists while idle. Use `resolveAnimation`
to check the mapping in headless authoring tools.

For host actions, `runtime.setAnimation(id, 'ranger.celebrate')` overrides automatic
selection. Pass `null` to return to movement-driven selection. A non-looping clip
holds its final frame; the host decides when its action ends. Animation follows
runtime elapsed seconds and pause, not a separate browser ticker. Temporary clip
overrides are not saved in scene JSON.

Requesting the same non-null clip again restarts it, so a host can replay an action.
Overrides apply to named-asset sprites; built-in and legacy URL/frame visuals return
`false`, as do missing entities. Unknown clip IDs reject before changing playback.

## Agent workflow and evidence

1. Establish the small art contract above and keep source/usage records.
2. Add one tile, one prop, and one actor first; validate their manifest and scene.
3. Check the character's feet and scale at rest, during all movement directions,
   and when jumping. Check foreground occlusion and floor cutaways.
4. Add clips and terrain variants only after placement is correct. Keep naming
   consistent; missing references should fail validation rather than render blank.
5. Play at desktop and mobile widths. Check pause, restart, art-scene export/import,
   failed asset loading, and another runtime instance surviving destruction.
6. Build the host and verify local asset URLs in its production output. A dev-only
   path is not a portable asset pack.

`demo/art-pack.ts` and the Woodland atelier scene provide a local SVG example.
`demo/pixel-cafe.ts` and Sunflower courtyard provide a richer bitmap example:
four local PNG atlases, 48 named textures, 12 directional clips, and a 9 × 9
map assembled from separate terrain and props. Prompts and source notes live in
`demo/art/pixel-cafe/README.md`. No engine changes were needed for that theme.
The initial courtyard's border-alignment and proportion failures are preserved in
`demo/art/pixel-cafe/art-contract.before.json`. The revision separates exact
code-authored stone bases from generated foliage and calibrates furniture using
seat/tabletop landmarks. Its measured contract and uncertainty notes sit beside
the assets; **07 — Art calibration** exposes joins and props for real playtests.
See `VERIFICATION.md` for the distinct metadata, visual, and gameplay verdicts.

Generated atlases need inspection: requested dimensions and equal grid spacing
are not guarantees. Measure the decoded image and each object's visible bounds.
Use consistently sized padded character frames so walking does not resize the
actor; put feet at explicit contact anchors. Terrain frames should tightly bound
their diamond because the renderer fits them to a cell. Set physical footprints
separately: the grouped café table/chairs occupy 2 × 2 cells even though they use
one sprite. Check the resulting ground contact and occlusion in the actual game.

Keep new themes in host-owned packs; extend `src/art.ts` for reusable data contracts,
`src/assets.ts` for image ownership, and `src/sprites.ts` for sprite presentation.
`SceneView` composes those pieces; game rules do not belong in those modules.
