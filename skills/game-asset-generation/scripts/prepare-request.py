#!/usr/bin/env python3
"""Prepare bounded, offline image references for one generation request.

The tool copies whole PNGs byte-for-byte or writes measured PNG crops.  It does
not call a provider, judge an image, or authorize a request.
"""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys

from PIL import Image, ImageDraw

MAX_SPEC_BYTES = 1_048_576
MAX_IMAGE_BYTES = 32 * 1024 * 1024
MAX_PIXELS = 16_777_216
MAX_REFERENCES = 32
MAX_TEXT = 8_192
ID = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
ROLES = frozenset(("style", "layout", "identity"))
RESERVED = frozenset(("__proto__", "prototype", "constructor"))
RESERVED_REFERENCE_IDS = frozenset(("board",))


def fail(message):
    raise ValueError(message)


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_bounded(path, maximum):
    with path.open("rb") as handle:
        value = handle.read(maximum + 1)
    if len(value) > maximum:
        fail(f"input exceeds {maximum} bytes: {path.name}")
    return value


def identifier(value, where):
    if not isinstance(value, str) or not ID.fullmatch(value) or value in RESERVED:
        fail(f"{where} must be a safe lowercase identifier")
    return value


def relative_path(base, value, suffix, where):
    if (not isinstance(value, str) or not 1 <= len(value) <= 1024 or "\\" in value
            or ":" in value or "\x00" in value):
        fail(f"{where} must be a relative forward-slash path")
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() != suffix:
        fail(f"invalid {where}: {value}")
    resolved = (base / Path(*relative.parts)).resolve()
    if not resolved.is_relative_to(base):
        fail(f"{where} escapes the specification directory: {value}")
    return resolved


def exact_keys(value, keys, where):
    if not isinstance(value, dict) or set(value) != set(keys):
        fail(f"{where} must have exactly these keys: {', '.join(keys)}")


def integer(value, low, high, where):
    if type(value) is not int or not low <= value <= high:
        fail(f"{where} must be an integer in [{low}, {high}]")


def load_png(path):
    raw = read_bounded(path, MAX_IMAGE_BYTES)
    with Image.open(io.BytesIO(raw)) as image:
        if image.format != "PNG" or getattr(image, "n_frames", 1) != 1:
            fail(f"reference must be a single PNG: {path.name}")
        if image.width * image.height > MAX_PIXELS:
            fail(f"reference exceeds {MAX_PIXELS} pixels: {path.name}")
        image.load()
        # Preserve the decoded PNG's native pixels for crops. Conversion is only
        # needed later to compose the review board.
        selected = image.copy()
    return raw, selected


def parse_reference(entry, base, seen):
    exact_keys(entry, ("id", "path", "role", "approval", "crop"), "reference")
    reference_id = identifier(entry["id"], "reference.id")
    if reference_id in RESERVED_REFERENCE_IDS:
        fail(f"reference.id is reserved for generated output: {reference_id}")
    if reference_id in seen:
        fail(f"duplicate reference id: {reference_id}")
    seen.add(reference_id)
    if entry["role"] not in ROLES:
        fail("reference.role must be style, layout, or identity")
    if entry["role"] == "identity":
        if entry["approval"] != "approved":
            fail("identity references must be explicitly approved; rejected identity is never emitted")
    elif entry["approval"] is not None:
        fail("style/layout reference approval must be null")
    crop = entry["crop"]
    if crop is not None:
        exact_keys(crop, ("x", "y", "width", "height"), f"reference {reference_id}.crop")
        for key in ("x", "y", "width", "height"):
            integer(crop[key], 0 if key in ("x", "y") else 1, MAX_PIXELS, f"reference {reference_id}.crop.{key}")
    return {"id": reference_id, "path": relative_path(base, entry["path"], ".png", "reference.path"),
            "role": entry["role"], "crop": crop}


def prepare(spec_path, output):
    spec_path = Path(spec_path).resolve()
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        fail(f"output already exists; choose a new directory: {output}")
    raw_spec = read_bounded(spec_path, MAX_SPEC_BYTES)
    spec = json.loads(raw_spec, object_pairs_hook=no_duplicate_keys,
                      parse_constant=lambda token: fail(f"invalid JSON number: {token}"))
    exact_keys(spec, ("version", "description", "references"), "spec")
    if spec["version"] != 2 or not isinstance(spec["description"], str) or not 1 <= len(spec["description"]) <= MAX_TEXT:
        fail("spec needs version 2 and a bounded nonempty description; matrix and calibration receipts were retired")
    if not isinstance(spec["references"], list) or not 1 <= len(spec["references"]) <= MAX_REFERENCES:
        fail(f"references must contain 1 to {MAX_REFERENCES} entries")
    seen = set()
    references = [parse_reference(entry, spec_path.parent, seen) for entry in spec["references"]]
    source_cache, rendered = {}, []
    for reference in references:
        path = reference["path"]
        if path not in source_cache:
            source_cache[path] = load_png(path)
        source_bytes, image = source_cache[path]
        crop = reference["crop"]
        if crop:
            if crop["x"] + crop["width"] > image.width or crop["y"] + crop["height"] > image.height:
                fail(f"crop is outside source image: {reference['id']}")
            selected = image.crop((crop["x"], crop["y"], crop["x"] + crop["width"], crop["y"] + crop["height"]))
        else:
            selected = image.copy()
        if selected.width * selected.height > MAX_PIXELS:
            fail("selected reference exceeds pixel limit")
        source_hash = hashlib.sha256(source_bytes).hexdigest()
        rendered.append((reference, source_bytes, source_hash, selected))
    label_height, padding = 22, 4
    label_canvas = Image.new("RGBA", (1, 1))
    label_measure = ImageDraw.Draw(label_canvas)
    board_width = max(
        max(selected.width for _, _, _, selected in rendered),
        max(label_measure.textbbox((0, 0), f"{reference['id']} [{reference['role']}]")[2]
            for reference, _, _, _ in rendered),
    ) + padding * 2
    board_height = sum(selected.height + label_height + padding for _, _, _, selected in rendered) + padding
    label_canvas.close()
    if board_width * board_height > MAX_PIXELS:
        fail("labeled board exceeds pixel limit")
    output.mkdir(parents=True, exist_ok=False)
    report_refs, board_images = [], []
    try:
        for reference, source_bytes, source_hash, selected in rendered:
            filename = f"{reference['id']}.png"
            target = output / filename
            if reference["crop"] is None:
                target.write_bytes(source_bytes)
            else:
                selected.save(target, format="PNG")
            report_refs.append({"id": reference["id"], "file": filename, "role": reference["role"],
                                "source": str(reference["path"].relative_to(spec_path.parent)).replace("\\", "/"),
                                "sourceSha256": source_hash, "crop": reference["crop"],
                                "outputSha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                                "pixelsSha256": hashlib.sha256(selected.tobytes()).hexdigest(),
                                "pixels": {"width": selected.width, "height": selected.height}})
            board_images.append((reference["id"], reference["role"], selected.copy()))
        board = Image.new("RGBA", (board_width, board_height), (238, 238, 238, 255))
        draw, y = ImageDraw.Draw(board), padding
        for ref_id, role, image in board_images:
            draw.text((padding, y), f"{ref_id} [{role}]", fill=(0, 0, 0, 255))
            y += label_height
            board.alpha_composite(image.convert("RGBA"), (padding, y))
            y += image.height + padding
            image.close()
        board.save(output / "board.png", format="PNG")
        board.close()
        board_hash = hashlib.sha256((output / "board.png").read_bytes()).hexdigest()
        report = {"version": 2, "description": spec["description"], "request": {"references": report_refs}, "sourceHashes": {str(path.relative_to(spec_path.parent)).replace("\\", "/"): hashlib.sha256(raw).hexdigest() for path, (raw, _) in source_cache.items()},
                  "provenance": {"specSha256": hashlib.sha256(raw_spec).hexdigest(), "boardSha256": board_hash},
                  "limits": {"judgement": "self-reported only; no automatic visual approval", "generatorAuthorization": "not enforced by this offline tool"}}
        with (output / "request.json").open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, indent=2, allow_nan=False)
            handle.write("\n")
        return report
    finally:
        for _, image in source_cache.values():
            image.close()
        for _, _, _, image in rendered:
            image.close()
        for _, _, image in board_images:
            image.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="version 2 JSON; paths resolve beside it")
    parser.add_argument("--out", type=Path, required=True, help="new output directory")
    args = parser.parse_args()
    try:
        result = prepare(args.spec, args.out)
    except (ValueError, OSError, Image.DecompressionBombError, json.JSONDecodeError) as error:
        print(f"prepare-request: {error}", file=sys.stderr)
        return 1
    print(f"Prepared {len(result['request']['references'])} references in {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
