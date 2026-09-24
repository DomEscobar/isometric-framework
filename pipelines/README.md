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

## Character

`character_provider.py` + `generation.py` via `tools/generate_character_once.py` (`GENERATED_CHARACTER_AUTHORIZATION.md`). Binding fixture: `assets/character/composed.png`.

## Shared

`artifacts.py`, `provider.py`, `billing_settlement.py`, `layout_core.py`, `hybrid_layout.py`, `hybrid_painted_scene.py`, `hybrid_artifact.py`, `hybrid_models.py`, `hybrid_package.py`. Actor sprites: `assets/actor/`.
