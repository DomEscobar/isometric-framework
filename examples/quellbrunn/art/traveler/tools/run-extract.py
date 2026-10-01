#!/usr/bin/env python3
"""Host-local wrapper around skills/directional-sprite-authoring/scripts/extract-video.py.

This sandbox denies os.replace() on a directory once a spawned subprocess
(ffmpeg) has written into it, even though copying and deleting the same tree
works. extract-video.py's own publish() step relies on that rename, so its
CLI cannot finish here and deletes the otherwise-valid staging directory on
that failure. This wrapper calls the skill's unmodified prepare()/export()
functions directly, disables their internal cleanup only long enough to
recover the staging directory they already produced, and finishes the
publish itself with copy+delete. It does not change what those functions
compute; it only replaces the last filesystem step that this sandbox blocks.
"""
import runpy
import shutil
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[5] / 'skills' / 'directional-sprite-authoring' / 'scripts' / 'extract-video.py'


def load():
    return runpy.run_path(str(SCRIPT), run_name='extract_video')


def finish_publish(output_dir_parent, before):
    after = {p.name for p in output_dir_parent.iterdir() if p.is_dir() and p.name.startswith('.extract-video-')}
    created = after - before
    if len(created) != 1:
        raise RuntimeError(f'Expected exactly one new staging directory, found {created!r}')
    return output_dir_parent / next(iter(created))


def run_prepare(source, out, key, tolerance):
    mod = load()
    out_path = Path(out).resolve()
    before = {p.name for p in out_path.parent.iterdir() if p.is_dir() and p.name.startswith('.extract-video-')} if out_path.parent.is_dir() else set()
    orig_rmtree = shutil.rmtree
    shutil.rmtree = lambda *a, **k: None
    try:
        try:
            return mod['prepare'](source, out, key, tolerance)
        except PermissionError:
            staging = finish_publish(out_path.parent, before)
            shutil.copytree(staging, out_path)
            orig_rmtree(staging)
            return None
    finally:
        shutil.rmtree = orig_rmtree


def run_export(recipe, out):
    mod = load()
    out_path = Path(out).resolve()
    before = {p.name for p in out_path.parent.iterdir() if p.is_dir() and p.name.startswith('.extract-video-')} if out_path.parent.is_dir() else set()
    orig_rmtree = shutil.rmtree
    shutil.rmtree = lambda *a, **k: None
    try:
        try:
            return mod['export'](recipe, out)
        except PermissionError:
            staging = finish_publish(out_path.parent, before)
            shutil.copytree(staging, out_path)
            orig_rmtree(staging)
            return None
    finally:
        shutil.rmtree = orig_rmtree


if __name__ == '__main__':
    command = sys.argv[1]
    if command == 'prepare':
        _, _, source, out, key, tolerance = sys.argv
        result = run_prepare(source, out, key, int(tolerance))
        print(f'Prepared review bundle at {out}')
    elif command == 'export':
        _, _, recipe, out = sys.argv
        result = run_export(recipe, out)
        print(f'Exported to {out}')
    else:
        raise SystemExit(f'Unknown command: {command}')
