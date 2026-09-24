# Generation Pipelines

Two pipelines: **terrain** and **character**. Flat imports; keep the tree as-is.
This tree is a framework-repo lab: it is not shipped in the npm package, and
skills never depend on paths under `pipelines/` from a generated game.

## Relation to skills

| Lab method | Skill owner (packaged) |
| --- | --- |
| Flat deco: numbered foot markers, SAM candidates, multimodal assign, cutouts | [in-situ scenery](../skills/game-asset-generation/references/in-situ-scenery.md) |
| Baked `scene.png` + depth stamping in the hybrid navigator | Lab preview only; framework hosts bind cutouts as runtime sprites |
| Character stages / automatic review / compact sampling | [animation service](../skills/directional-sprite-authoring/references/animation-service.md) plus [video-to-sprites](../skills/directional-sprite-authoring/references/video-to-sprites.md) |

Spec-route (`terrain_pipeline`), block assembly (`terrain_block` /
`terrain_materials` / `terrain_assemble`) and the hybrid navigator are lab
tooling. They are not alternate production routes beside composed ground or the
host runtime. Extract general methods into skills; do not link skills to run
directories under `pipelines/out/`.

## Terrain

Spec route — description → `TerrainSpec` → grid → guide → paint → review → artifact:

```sh
python3 terrain_pipeline.py init <run-dir> --description-file desc.txt --max-usd 0.10 --max-images 2
python3 terrain_pipeline.py run <run-dir> --paid
```

Block assembly — frozen heights/collision, plate tops, face strips:

```sh
bash tools/run-py.sh terrain_block.py guide <world.json> <flat-guide.png>
bash tools/run-py.sh terrain_materials.py <run-dir> <style.png> <flat-guide.png> --ledger <ledger.jsonl> --paid
bash tools/run-py.sh terrain_assemble.py buy <world.json> <style.png> <materials-dir> --ledger <ledger.jsonl> --paid
bash tools/run-py.sh terrain_assemble.py scene <world.json> <materials-dir> <plate.png> <out-dir>
```

Flat deco (SAM3 cutouts on a Muse plate):

```sh
# Paid probe (quote without --paid): Muse plate+deco, then SAM masks
python3 tools/sam3_deco_probe.py <run-dir> <simple|village|grove> [--paid|--resplit|--sam-retry]

# Productized post-process (free): candidates / assign map / place / walkable navigator
python3 terrain_deco.py candidates <run-dir>
python3 terrain_deco.py assign <run-dir>          # needs assign.json -> candidates/<file>
python3 terrain_deco.py place <run-dir>           # plate + sprite-*.png -> scene.png + preview.html
python3 terrain_deco.py navigate <run-dir>        # hybrid-navigator index.html (WASD)
python3 terrain_deco.py package <run-dir>         # assign (if map) + place + navigate
```

Open `index.html` in the run dir for WASD walking (flat collision from `world.json`). Text-SAM often returns class masks;
use `candidates` + AI assign, or `--sam-retry --points points.json` when Muse drifts off grid feet.
Numbered diamond markers + foot-lock prompt reduce Muse swap/drift on the next paid deco edit.

## Character

`character_provider.py` + `generation.py` via `tools/generate_character_once.py` (`GENERATED_CHARACTER_AUTHORIZATION.md`). Binding fixture: `assets/character/composed.png`.

Staged FastAPI service (facing → I2V → review → pack): see
[character-animations/README.md](character-animations/README.md). Framework hosts
bridge through the skill reference above, not by consuming `animation-pipeline-atlas-v1` as V4.

## Shared

`artifacts.py`, `provider.py`, `billing_settlement.py`, `layout_core.py`, `hybrid_layout.py`, `hybrid_painted_scene.py`, `hybrid_artifact.py`, `hybrid_models.py`, `hybrid_package.py`. Actor sprites: `assets/actor/`.
