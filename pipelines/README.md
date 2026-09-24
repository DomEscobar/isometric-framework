# Generation Pipelines

Python source for the two paid generation pipelines, moved here as the
canonical project home. Flat module layout (imports are `from hybrid_models
import ...` / `from character_provider import ...`), keep the tree as-is.

## Terrain pipeline (`hybrid_*`)

Planner -> independent layout review -> frozen layout -> painted flat terrain
atlas (image-to-image) -> deterministic isometric render -> artifact with
source-pixel replay.

| Area | Files |
| --- | --- |
| Service/API + ledger | `hybrid_api.py`, `hybrid_worker.py`, `hybrid_store.py` (if present), `billing_settlement.py` |
| Layout + review | `hybrid_layout.py`, `hybrid_layout_review.py`, `hybrid_target_layout.py` |
| Painting + sampling | `hybrid_painted_terrain.py`, `hybrid_material_repair.py`, `hybrid_sampling*.py`, `hybrid_recovery.py` |
| Render + artifact | `hybrid_render.py`, `hybrid_artifact.py`, `hybrid_export.py`, `hybrid_package.py` |
| Providers | `hybrid_models.py` (OpenRouter text/review), `provider.py` (image provider adapter) |

Operational notes live in `HYBRID_SERVICE.md`; authorization contracts are the
`*_AUTHORIZATION.md` files.

## Character pipeline (`character_provider.py`, `generation.py`)

Static generated character art with binding/provenance, run via
`tools/generate_character_once.py` (see `GENERATED_CHARACTER_AUTHORIZATION.md`).

## Shared infrastructure

`artifacts.py` (canonical JSON + digests + immutable writes), `evaluations.py`,
`corrections.py`, `constrained_adapter.py`, `auto_adapter.py`,
`transport_reconciliation.py`, `generation_api.py`, style/candidate modules.

## Tests

```sh
python3 -m pytest tests -q
```

Read-only fixtures referenced by code/tests are vendored under `evidence/` and
`experiments/` (style reference, replay source, character artifact). Runtime
state (`data/`: runs ledger, uploads, authorizations) and generated evidence
stay at the deployment (`/root/services/layout-terrain-pipeline`); provider
credentials are never stored here.
