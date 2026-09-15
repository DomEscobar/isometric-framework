#!/usr/bin/env python3
"""Pack approved, equal-cell PNG cutouts without changing their pixels.

Python 3.12+, Pillow 11.3.0. This is an offline authoring tool, not a runtime
dependency. A valid sheet is not proof of correct facing, action or alignment.
"""

import argparse
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys

from PIL import Image

DIRECTIONS = frozenset(("n", "ne", "e", "se", "s", "sw", "w", "nw"))
NATIVE_ACTIONS = frozenset(("idle", "walk", "jump"))
ID = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
RESERVED = frozenset(("__proto__", "prototype", "constructor"))
MAX_SPEC_BYTES = 1_048_576
MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_PIXELS = 16_777_216
MAX_CLIPS = 128
MAX_FRAMES_PER_CLIP = 256
MAX_TOTAL_FRAMES = 4096
MAX_AXIS = 16384
GUTTER = 2


def fail(message):
    raise ValueError(message)


def object_keys(value, keys, where):
    if not isinstance(value, dict) or set(value) != set(keys):
        fail(f"{where} must have exactly these keys: {', '.join(keys)}")


def identifier(value, where):
    if not isinstance(value, str) or not ID.fullmatch(value) or value in RESERVED:
        fail(f"{where} must be a safe lowercase identifier (1 to 64 characters)")
    return value


def number(value, minimum, maximum, where, integer=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or (isinstance(value, float) and not math.isfinite(value))
            or not minimum <= value <= maximum
            or (integer and not isinstance(value, int))):
        fail(f"{where} must be {'an integer' if integer else 'a number'} in [{minimum}, {maximum}]")


def unique_list(value, where, direction=False):
    if not isinstance(value, list) or not 1 <= len(value) <= (8 if direction else MAX_CLIPS):
        fail(f"{where} must be a nonempty bounded list")
    for item in value:
        identifier(item, where)
        if direction and item not in DIRECTIONS:
            fail(f"{where} contains unknown direction {item}")
    if len(set(value)) != len(value):
        fail(f"{where} contains duplicates")


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


def bind_export_provenance(manifest, spec_sha256, kind):
    label = "video extraction" if kind == "video-extraction" else "mirrored extraction"
    if (not isinstance(manifest, dict) or manifest.get("version") != 2
            or manifest.get("spritePackSha256") != spec_sha256
            or not isinstance(manifest.get("exportedFrames"), list)):
        fail(f"{label} provenance is not a version 2 export")
    if kind == "mirrored-extraction" and manifest.get("kind") != "mirrored-extraction":
        fail("mirrored extraction provenance is not a version 2 export")
    return manifest


def validate(spec, base, spec_sha256):
    object_keys(spec, ("version", "origin", "imageId", "cell", "anchor", "requiredDirections", "requiredActions", "clips"), "spec")
    if type(spec["version"]) is not int or spec["version"] != 2:
        fail("version must be 2; direct character sheets are retired")
    if not isinstance(spec["origin"], dict) or spec["origin"].get("kind") not in ("video-extraction", "static-facing", "mirrored-extraction"):
        fail("origin.kind must be video-extraction, static-facing, or mirrored-extraction")
    identifier(spec["imageId"], "imageId")
    object_keys(spec["cell"], ("width", "height"), "cell")
    for key in ("width", "height"):
        number(spec["cell"][key], 1, 1024, f"cell.{key}", integer=True)
    object_keys(spec["anchor"], ("x", "y"), "anchor")
    for key in ("x", "y"):
        number(spec["anchor"][key], 0, 1, f"anchor.{key}")
    unique_list(spec["requiredDirections"], "requiredDirections", direction=True)
    unique_list(spec["requiredActions"], "requiredActions")
    clips = spec["clips"]
    if not isinstance(clips, list) or not 1 <= len(clips) <= MAX_CLIPS:
        fail(f"clips must contain 1 to {MAX_CLIPS} entries")
    pairs = set()
    total = 0
    for index, clip in enumerate(clips):
        where = f"clips[{index}]"
        object_keys(clip, ("action", "direction", "fps", "loop", "frames"), where)
        identifier(clip["action"], f"{where}.action")
        identifier(clip["direction"], f"{where}.direction")
        if clip["direction"] not in DIRECTIONS:
            fail(f"{where}.direction is unknown")
        pair = (clip["action"], clip["direction"])
        if pair in pairs:
            fail(f"duplicate action/direction: {pair}")
        pairs.add(pair)
        number(clip["fps"], 0.1, 120, f"{where}.fps")
        if type(clip["loop"]) is not bool:
            fail(f"{where}.loop must be a boolean")
        frames = clip["frames"]
        if not isinstance(frames, list) or not 1 <= len(frames) <= MAX_FRAMES_PER_CLIP:
            fail(f"{where}.frames must contain 1 to {MAX_FRAMES_PER_CLIP} paths")
        total += len(frames)
        for frame in frames:
            frame_path(base, frame)
    if total > MAX_TOTAL_FRAMES:
        fail(f"total frames exceeds {MAX_TOTAL_FRAMES}")
    origin = spec["origin"]
    if origin["kind"] == "static-facing":
        object_keys(origin, ("kind",), "origin")
        if total != 1 or len(clips) != 1 or clips[0]["action"] != "idle":
            fail("static-facing origin is only valid for one-frame idle clips")
        provenance_hash = None
    else:
        object_keys(origin, ("kind", "provenance"), "origin")
        provenance = json_path(base, origin["provenance"])
        if not provenance.is_file():
            fail("video extraction provenance is missing")
        provenance_raw = read_bounded(provenance, MAX_SPEC_BYTES)
        try:
            manifest = json.loads(provenance_raw, object_pairs_hook=no_duplicate_keys)
        except json.JSONDecodeError:
            fail("video extraction provenance is invalid JSON")
        bound = bind_export_provenance(manifest, spec_sha256, origin["kind"])
        expected = {item.get("file"): item.get("sha256") for item in bound["exportedFrames"] if isinstance(item, dict)}
        for clip in clips:
            for frame in clip["frames"]:
                candidate = frame_path(base, frame)
                if expected.get(frame) != hashlib.sha256(read_bounded(candidate, MAX_INPUT_BYTES)).hexdigest():
                    fail(f"{origin['kind']} provenance does not bind frame: {frame}")
        provenance_hash = hashlib.sha256(provenance_raw).hexdigest()
    required = {(action, direction) for action in spec["requiredActions"] for direction in spec["requiredDirections"]}
    missing = required - pairs
    if missing:
        fail(f"missing required action/direction clips: {sorted(missing)}")
    width = max(len(clip["frames"]) for clip in clips) * (spec["cell"]["width"] + GUTTER) + GUTTER
    height = len(clips) * (spec["cell"]["height"] + GUTTER) + GUTTER
    if width > MAX_AXIS or height > MAX_AXIS or width * height > MAX_PIXELS:
        fail(f"sheet exceeds allocation limits ({MAX_AXIS} per axis, {MAX_PIXELS} pixels)")
    return width, height, provenance_hash


def load_cutout(path, size):
    data = read_bounded(path, MAX_INPUT_BYTES)
    with Image.open(io.BytesIO(data)) as original:
        if original.format != "PNG":
            fail(f"input must decode as PNG: {path.name}")
        if data[24] > 8:
            fail(f"PNG bit depth above 8 would lose precision when packed: {path.name}")
        if original.size != size:
            fail(f"input dimensions must equal cell {size}: {path.name}")
        if getattr(original, "n_frames", 1) != 1:
            fail(f"animated PNG inputs are unsupported: {path.name}")
        if "A" not in original.getbands() and "transparency" not in original.info:
            fail(f"input has no real alpha/transparency: {path.name}")
        rgba = original.convert("RGBA")
    minimum, maximum = rgba.getchannel("A").getextrema()
    if minimum != 0 or maximum == 0:
        fail(f"input needs both fully transparent and visible pixels: {path.name}")
    return rgba, hashlib.sha256(data).hexdigest()


def pack(spec_path, output):
    spec_path, output = Path(spec_path).resolve(), Path(output).absolute()
    if output.exists() or output.is_symlink():
        fail(f"output already exists; choose a new directory: {output}")
    raw = read_bounded(spec_path, MAX_SPEC_BYTES)
    spec = json.loads(raw, object_pairs_hook=no_duplicate_keys,
                      parse_constant=lambda value: fail(f"invalid JSON number: {value}"))
    spec_hash = hashlib.sha256(raw).hexdigest()
    width, height, provenance_hash = validate(spec, spec_path.parent, spec_hash)
    cell = spec["cell"]
    image_id = spec["imageId"]
    sheet = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    textures, animations, visual, custom, hashes, rows = {}, {}, {"directions": {}}, {}, {}, []
    for row, clip in enumerate(spec["clips"]):
        action, direction = clip["action"], clip["direction"]
        clip_id = f"{image_id}.{action}.{direction}"
        frame_ids = []
        for column, source in enumerate(clip["frames"]):
            rgba, digest = load_cutout(frame_path(spec_path.parent, source), (cell["width"], cell["height"]))
            if source in hashes and hashes[source] != digest:
                fail(f"input changed during packing: {source}")
            hashes[source] = digest
            x, y = GUTTER + column * (cell["width"] + GUTTER), GUTTER + row * (cell["height"] + GUTTER)
            # No mask: alpha compositing would alter partially transparent pixels.
            sheet.paste(rgba, (x, y))
            rgba.close()
            texture_id = f"{clip_id}.{column:04d}"
            textures[texture_id] = {"image": image_id, "frame": {"x": x, "y": y, **cell}, "anchor": spec["anchor"]}
            frame_ids.append(texture_id)
        animations[clip_id] = {"frames": frame_ids, "fps": clip["fps"], "loop": clip["loop"]}
        rows.append({"row": row, "clip": clip_id, "action": action, "direction": direction})
        if action in NATIVE_ACTIONS:
            visual.setdefault(action, clip_id)
            visual["directions"].setdefault(direction, {})[action] = clip_id
        else:
            custom.setdefault(action, {})[direction] = clip_id
    result = {
        "version": 1,
        "assets": {"images": {image_id: {"url": "sheet.png", "sampling": "nearest"}},
                   "textures": textures, "animations": animations},
        "visualAnimations": visual,
        "customActions": custom,
        "sourceHashes": {"spec": spec_hash, "provenance": provenance_hash, "frames": hashes},
        "packing": {"width": width, "height": height, "cell": cell,
                    "anchor": spec["anchor"], "gutter": GUTTER, "rows": rows},
    }
    # Reserve exclusively after all validation succeeds. Existing folders are never reused.
    output.mkdir(parents=True, exist_ok=False)
    with (output / "sheet.png").open("xb") as target:
        sheet.save(target, format="PNG")
    sheet.close()
    with (output / "runtime.json").open("x", encoding="utf-8", newline="\n") as target:
        json.dump(result, target, indent=2, allow_nan=False)
        target.write("\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="version 2 JSON; frame paths resolve against its directory")
    parser.add_argument("--out", type=Path, required=True, help="new output directory (must not exist)")
    args = parser.parse_args()
    try:
        result = pack(args.spec, args.out)
    except (ValueError, OSError, Image.DecompressionBombError) as error:
        print(f"pack-sprites: {error}", file=sys.stderr)
        return 1
    print(f"Packed {len(result['assets']['animations'])} clips into {args.out / 'sheet.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
