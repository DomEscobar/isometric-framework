#!/usr/bin/env python3
"""Compile a host-owned material recipe into a continuous, binder-compatible cache."""
import argparse
from pathlib import Path
import sys

from quilt_materials import run

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args.recipe, args.out)
        print(f"quilt-materials: {result['cacheKey']}")
    except (ValueError, OSError) as exc:
        print(f'quilt-materials: {exc}', file=sys.stderr)
        sys.exit(1)
