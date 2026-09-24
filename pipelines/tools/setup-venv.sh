#!/usr/bin/env bash
set -euo pipefail
VENV="$HOME/.venvs/terrain-compare"
command -v uv >/dev/null || [ -x "$HOME/.local/bin/uv" ] || curl -LsSf https://astral.sh/uv/install.sh | sh
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
[ -x "$VENV/bin/python" ] || "$UV" venv --python 3.12 "$VENV"
"$UV" pip install --python "$VENV/bin/python" -q numpy pillow pydantic httpx scipy jsonschema fastapi uvicorn pytest
"$VENV/bin/python" -c "import numpy, PIL, pydantic, httpx, scipy, jsonschema, fastapi, uvicorn, pytest; print('deps ok')"
