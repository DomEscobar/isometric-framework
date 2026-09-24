# Generation Pipelines

Two pipelines: **terrain** and **character**. Flat imports; keep the tree as-is.

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

## Shared

`artifacts.py`, `provider.py`, `billing_settlement.py`, `layout_core.py`, `hybrid_layout.py`, `hybrid_painted_scene.py`, `hybrid_artifact.py`, `hybrid_models.py`, `hybrid_package.py`. Actor sprites: `assets/actor/`.
