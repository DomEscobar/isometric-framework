#!/usr/bin/env bash
# Run a pipelines script with the terrain venv: run-py.sh <script> [args...]
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.venvs/terrain-compare/bin:$PATH" PYTHONPATH=.
python "$@"
