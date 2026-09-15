#!/usr/bin/env python3
"""Flip reviewed extraction frames into the opposite screen-left/right facing.

Python 3.12+, Pillow 11.3.0. This is an offline authoring tool, not a runtime
dependency. A valid flip is not proof that lighting, equipment, or the mirrored
facing still read correctly in play. Packer and runtime never perform this flip.
"""

import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
from uuid import uuid4

from PIL import Image

DIRECTIONS = frozenset(("n", "ne", "e", "se", "s", "sw", "w", "nw"))
HORIZONTAL_PAIRS = {"ne": "nw", "nw": "ne", "se": "sw", "sw": "se", "e": "w", "w": "e"}
MAX_SPEC_BYTES = 1_048_576
MAX_INPUT_BYTES = 32 * 1024 * 1024


def fail(message):
    raise ValueError(message)


def object_keys(value, keys, where):
    if not isinstance(value, dict) or set(value) != set(keys):
        fail(f"{where} must have exactly these keys: {', '.join(keys)}")


def number(value, minimum, maximum, where, integer=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or (isinstance(value, float) and not math.isfinite(value))
            or not minimum <= value <= maximum
            or (integer and not isinstance(value, int))):
        fail(f"{where} must be {'an integer' if integer else 'a number'} in [{minimum}, {maximum}]")


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_bounded(path, maximum):
    with path.open("rb") as source:
        data = source.read(maximum + 1)
    if len(data) > maximum:
        fail(f"input exceeds {maximum} bytes: {path.name}")
    return data


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def frame_path(base, value):
    if (not isinstance(value, str) or not 1 <= len(value) <= 1024
            or "\\" in value or ":" in value or "\x00" in value):
        fail("frame paths must be relative forward-slash PNG paths")
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() != ".png":
        fail(f"invalid relative PNG path: {value}")
    resolved = (base / Path(*relative.parts)).resolve()
    if not resolved.is_relative_to(base):
        fail(f"frame escapes the specification directory: {value}")
    return resolved


def json_path(base, value):
    if not isinstance(value, str) or not value.endswith(".json"):
        fail("origin.provenance must be a relative JSON path")
    return frame_path(base, value[:-5] + ".png").with_suffix(".json")


def load_spec(spec_path):
    spec_path = Path(spec_path).resolve()
    raw = read_bounded(spec_path, MAX_SPEC_BYTES)
    spec = json.loads(raw, object_pairs_hook=no_duplicate_keys,
                      parse_constant=lambda value: fail(f"invalid JSON number: {value}"))
    object_keys(spec, ("version", "origin", "imageId", "cell", "anchor",
                       "requiredDirections", "requiredActions", "clips"), "spec")
    if type(spec["version"]) is not int or spec["version"] != 2:
        fail("version must be 2")
    origin = spec["origin"]
    if not isinstance(origin, dict) or origin.get("kind") != "video-extraction":
        fail("source origin.kind must be video-extraction; do not chain mirrors")
    object_keys(origin, ("kind", "provenance"), "origin")
    object_keys(spec["cell"], ("width", "height"), "cell")
    object_keys(spec["anchor"], ("x", "y"), "anchor")
    for key in ("width", "height"):
        number(spec["cell"][key], 1, 1024, f"cell.{key}", integer=True)
    for key in ("x", "y"):
        number(spec["anchor"][key], 0, 1, f"anchor.{key}")
    clips = spec["clips"]
    if not isinstance(clips, list) or not clips:
        fail("source clips must be a nonempty list")
    directions = []
    files = []
    for index, clip in enumerate(clips):
        object_keys(clip, ("action", "direction", "fps", "loop", "frames"), f"clips[{index}]")
        if clip["direction"] not in DIRECTIONS:
            fail(f"clips[{index}].direction is unknown")
        directions.append(clip["direction"])
        if not isinstance(clip["frames"], list) or not clip["frames"]:
            fail(f"clips[{index}].frames must be a nonempty list")
        files.extend(clip["frames"])
    unique = set(directions)
    if len(unique) != 1:
        fail("source clips must share one direction")
    source_direction = directions[0]
    provenance_path = json_path(spec_path.parent, origin["provenance"])
    if not provenance_path.is_file():
        fail("video extraction provenance is missing")
    provenance_raw = read_bounded(provenance_path, MAX_SPEC_BYTES)
    try:
        provenance = json.loads(provenance_raw, object_pairs_hook=no_duplicate_keys)
    except json.JSONDecodeError:
        fail("video extraction provenance is invalid JSON")
    spec_hash = sha256_bytes(raw)
    if (not isinstance(provenance, dict) or provenance.get("version") != 2
            or provenance.get("spritePackSha256") != spec_hash
            or not isinstance(provenance.get("exportedFrames"), list)):
        fail("video extraction provenance is not a version 2 export")
    expected = {item.get("file"): item.get("sha256") for item in provenance["exportedFrames"]
                if isinstance(item, dict)}
    source_frames = []
    seen = set()
    for name in files:
        path = frame_path(spec_path.parent, name)
        digest = sha256_bytes(read_bounded(path, MAX_INPUT_BYTES))
        if expected.get(name) != digest:
            fail(f"video extraction provenance does not bind frame: {name}")
        if name not in seen:
            seen.add(name)
            source_frames.append({"file": name, "sha256": digest, "path": path})
    return spec, spec_hash, sha256_bytes(provenance_raw), source_direction, source_frames


def flip_png(path, size):
    data = read_bounded(path, MAX_INPUT_BYTES)
    with Image.open(io.BytesIO(data)) as original:
        if original.format != "PNG":
            fail(f"input must decode as PNG: {path.name}")
        if original.size != size:
            fail(f"input dimensions must equal cell {size}: {path.name}")
        rgba = original.convert("RGBA")
    flipped = rgba.transpose(Image.FLIP_LEFT_RIGHT)
    rgba.close()
    return flipped


def fresh_output(output):
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        fail(f"output already exists; choose a new directory: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.parent / f".mirror-frames-{uuid4().hex}"
    staging.mkdir(exist_ok=False)
    return output, staging


def mirror(spec_path, output, direction):
    if direction not in HORIZONTAL_PAIRS:
        fail("target direction is not a horizontal facing pair")
    spec, spec_hash, provenance_hash, source_direction, source_frames = load_spec(spec_path)
    expected = HORIZONTAL_PAIRS.get(source_direction)
    if expected is None:
        fail(f"source direction {source_direction} has no horizontal facing pair")
    if direction != expected:
        fail(f"horizontal pair of {source_direction} is {expected}, not {direction}")
    cell = (spec["cell"]["width"], spec["cell"]["height"])
    output, staging = fresh_output(output)
    try:
        exported = []
        for item in source_frames:
            flipped = flip_png(item["path"], cell)
            target = staging / Path(*PurePosixPath(item["file"]).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            flipped.save(target, format="PNG")
            flipped.close()
            exported.append({"file": item["file"], "sha256": sha256_bytes(read_bounded(target, MAX_INPUT_BYTES))})
        result = json.loads(json.dumps(spec))
        result["origin"] = {"kind": "mirrored-extraction", "provenance": "provenance.json"}
        result["anchor"] = {"x": 1 - spec["anchor"]["x"], "y": spec["anchor"]["y"]}
        result["requiredDirections"] = [direction]
        for clip in result["clips"]:
            clip["direction"] = direction
        spec_out = staging / "sprite-pack.json"
        spec_out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
        provenance = {
            "version": 2,
            "kind": "mirrored-extraction",
            "axis": "horizontal",
            "sourceDirection": source_direction,
            "direction": direction,
            "source": {
                "kind": "video-extraction",
                "spritePackSha256": spec_hash,
                "provenanceSha256": provenance_hash,
            },
            "spritePackSha256": sha256_bytes(read_bounded(spec_out, MAX_SPEC_BYTES)),
            "sourceFrames": [{"file": item["file"], "sha256": item["sha256"]} for item in source_frames],
            "exportedFrames": exported,
        }
        (staging / "provenance.json").write_text(
            json.dumps(provenance, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
        os.replace(staging, output)
        return result
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="version 2 video-extraction sprite-pack.json")
    parser.add_argument("--to", required=True, dest="direction", help="opposite screen-left/right facing")
    parser.add_argument("--out", type=Path, required=True, help="new output directory (must not exist)")
    args = parser.parse_args()
    try:
        result = mirror(args.spec, args.out, args.direction)
    except (ValueError, OSError, Image.DecompressionBombError) as error:
        print(f"mirror-frames: {error}", file=sys.stderr)
        return 1
    print(f"Mirrored {len(result['clips'])} clips to {args.direction} in {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
