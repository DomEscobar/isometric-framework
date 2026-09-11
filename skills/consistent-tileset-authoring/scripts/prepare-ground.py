#!/usr/bin/env python3
"""Prepare a bounded PNG ground plate or lossless positioned chunks."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

from PIL import Image

MAX_PIXELS = 16_000_000
MAX_AXIS = 8192
MAX_BYTES = 64 * 1024 * 1024
MAX_RECIPE_BYTES = 1024 * 1024
MAX_CHUNKS = 4096
ROOT_FIELDS = {"version", "source", "coverageMask", "movingMask", "output", "outputToSource", "sampling", "provenance"}
OUTPUT_FIELDS = {"width", "height", "origin", "mode", "chunkSize", "gutter", "outOfBounds"}


class RecipeError(ValueError):
    pass


def error(message: str) -> None:
    raise RecipeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def encoded(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


def int_value(value: Any, name: str, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or (maximum is not None and value > maximum):
        error(f"{name} must be an integer in the declared bounds")
    return value


def local(root: Path, value: Any, name: str) -> Path:
    if not isinstance(value, str) or not value or "://" in value or value.startswith("file:"):
        error(f"{name} must be a local relative path")
    raw = Path(value)
    if raw.is_absolute():
        error(f"{name} must be relative to the recipe")
    path = (root / raw).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        error(f"{name} must stay inside the recipe directory")
    return path


def png(path: Path, name: str) -> Image.Image:
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        error(f"{name} is missing or exceeds the byte cap")
    try:
        with Image.open(path) as image:
            if image.format != "PNG" or getattr(image, "n_frames", 1) != 1:
                error(f"{name} must be a static PNG")
            if image.width > MAX_AXIS or image.height > MAX_AXIS or image.width * image.height > MAX_PIXELS:
                error(f"{name} exceeds image resource bounds")
            return image.copy()
    except OSError as exc:
        error(f"cannot read {name}: {exc}")


def mask(path: Path, name: str, size: tuple[int, int]) -> Image.Image:
    image = png(path, name)
    if image.size != size:
        error(f"{name} must be target-sized {size[0]}x{size[1]}")
    if image.mode not in ("1", "L"):
        error(f"{name} must be grayscale PNG mode L or 1")
    return image.convert("L")


def affine(value: Any) -> tuple[float, float, float, float, float, float]:
    if value is None:
        return (1., 0., 0., 0., 1., 0.)
    if not isinstance(value, list) or len(value) != 6 or any(type(v) not in (int, float) for v in value):
        error("outputToSource must contain six finite numbers")
    try:
        values = tuple(float(v) for v in value)
    except (TypeError, ValueError):
        error("outputToSource must contain six finite numbers")
    if not all(math.isfinite(v) for v in values) or abs(values[0] * values[4] - values[1] * values[3]) < 1e-12:
        error("outputToSource must be finite and invertible")
    return values  # type: ignore[return-value]


def in_bounds(matrix: tuple[float, ...], width: int, height: int, source: tuple[int, int]) -> bool:
    # Pillow evaluates affine input at output-pixel centres, not integer corners.
    for x, y in ((.5, .5), (width - .5, .5), (.5, height - .5), (width - .5, height - .5)):
        sx = matrix[0] * x + matrix[1] * y + matrix[2]
        sy = matrix[3] * x + matrix[4] * y + matrix[5]
        if sx < 0 or sy < 0 or sx >= source[0] or sy >= source[1]:
            return False
    return True


def save(image: Image.Image, path: Path) -> None:
    image.save(path, format="PNG", optimize=False, compress_level=9)


def info(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        return {"url": path.name, "sampling": "nearest", "width": image.width, "height": image.height, "sha256": sha256(path)}


def reject_unknown(value: dict[str, Any], allowed: set[str], name: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        error(f"{name} has unknown field: {unknown[0]}")


def run(recipe_path: Path, out_dir: Path) -> None:
    started = time.perf_counter()
    recipe_path = recipe_path.resolve()
    if not recipe_path.is_file() or recipe_path.stat().st_size > MAX_RECIPE_BYTES:
        error("recipe is missing or exceeds byte cap")
    try:
        recipe_bytes = recipe_path.read_bytes()
        recipe_hash = hashlib.sha256(recipe_bytes).hexdigest()
        recipe = json.loads(recipe_bytes.decode("utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        error(f"cannot parse recipe: {exc}")
    if not isinstance(recipe, dict) or type(recipe.get("version")) is not int or recipe.get("version") != 1:
        error("recipe version must be 1")
    reject_unknown(recipe, ROOT_FIELDS, "recipe")
    root = recipe_path.parent
    source_path = local(root, recipe.get("source"), "source")
    tool_path = Path(__file__).resolve()
    tool_hash = sha256(tool_path)
    input_paths = [recipe_path, source_path, tool_path]
    source_hash = sha256(source_path)
    source = png(source_path, "source").convert("RGBA")
    output = recipe.get("output", {})
    if not isinstance(output, dict):
        error("output must be an object")
    reject_unknown(output, OUTPUT_FIELDS, "output")
    width = int_value(output.get("width", source.width), "output.width", 1, MAX_AXIS)
    height = int_value(output.get("height", source.height), "output.height", 1, MAX_AXIS)
    if width * height > MAX_PIXELS:
        error("output exceeds pixel cap")
    origin = output.get("origin", [0, 0])
    if not isinstance(origin, list) or len(origin) != 2:
        error("output.origin must be [integer, integer]")
    if any(isinstance(v, bool) or not isinstance(v, int) for v in origin):
        error("output.origin must be [integer, integer]")
    if origin[0] < -1_000_000 or origin[1] < -1_000_000 or origin[0] + width - 1 > 1_000_000 or origin[1] + height - 1 > 1_000_000:
        error("output origin and extent must stay within placement bounds")
    mode = output.get("mode", "plate")
    if mode not in ("plate", "chunks"):
        error("output.mode must be plate or chunks")
    gutter = int_value(output.get("gutter", 0), "output.gutter", 0, MAX_AXIS)
    if mode == "chunks":
        chunk = output.get("chunkSize")
        if not isinstance(chunk, list) or len(chunk) != 2:
            error("output.chunkSize is required for chunks")
        chunk_width = int_value(chunk[0], "output.chunkSize[0]", 1, MAX_AXIS)
        chunk_height = int_value(chunk[1], "output.chunkSize[1]", 1, MAX_AXIS)
        if chunk_width + 2 * gutter > MAX_AXIS or chunk_height + 2 * gutter > MAX_AXIS:
            error("chunkSize plus gutter exceeds per-axis cap")
        if (chunk_width + 2 * gutter) * (chunk_height + 2 * gutter) > MAX_PIXELS:
            error("chunk padded pixel area exceeds cap")
        if math.ceil(width / chunk_width) * math.ceil(height / chunk_height) > MAX_CHUNKS:
            error("chunk count exceeds cap")
    elif output.get("chunkSize") is not None or gutter:
        error("chunkSize and gutter are only valid for chunks")
    if recipe.get("sampling", "nearest") != "nearest":
        error("only nearest sampling is supported")
    policy = output.get("outOfBounds", "reject")
    if policy not in ("reject", "transparent"):
        error("output.outOfBounds must be reject or transparent")
    matrix = affine(recipe.get("outputToSource"))
    if policy == "reject" and not in_bounds(matrix, width, height, source.size):
        error("outputToSource samples outside source; choose transparent explicitly")
    coverage_path = local(root, recipe["coverageMask"], "coverageMask") if "coverageMask" in recipe else None
    moving_path = local(root, recipe["movingMask"], "movingMask") if "movingMask" in recipe else None
    if coverage_path:
        input_paths.append(coverage_path)
    if moving_path:
        input_paths.append(moving_path)
    input_hashes = {path: sha256(path) for path in input_paths}
    input_hashes.update({recipe_path: recipe_hash, source_path: source_hash, tool_path: tool_hash})
    out_dir = out_dir.resolve()
    if out_dir == source_path or out_dir == recipe_path or source_path.is_relative_to(out_dir) or recipe_path.is_relative_to(out_dir):
        error("--out must not collide with or contain source or recipe")
    if out_dir.exists():
        error("--out must name a new directory; it will not be overwritten")

    composed = source.transform((width, height), Image.Transform.AFFINE, matrix, resample=Image.Resampling.NEAREST, fillcolor=(0, 0, 0, 0))
    coverage = mask(coverage_path, "coverageMask", (width, height)) if coverage_path else None
    if coverage is not None:
        alpha = bytes((a * b + 127) // 255 for a, b in zip(composed.getchannel("A").tobytes(), coverage.tobytes()))
        coverage = Image.frombytes("L", (width, height), alpha)
        composed.putalpha(coverage)
    moving = mask(moving_path, "movingMask", (width, height)) if moving_path else None
    if moving is not None and any(m and not a for m, a in zip(moving.tobytes(), composed.getchannel("A").tobytes())):
        error("movingMask must be inside final non-transparent support")

    out_dir.mkdir(parents=True)
    ground = out_dir / "ground.png"
    save(composed, ground)
    files = [ground]
    if coverage is not None:
        save(coverage, out_dir / "coverage.png")
        files.append(out_dir / "coverage.png")
    if moving is not None:
        save(moving, out_dir / "moving.png")
        files.append(out_dir / "moving.png")
    images: dict[str, Any] = {}
    textures: dict[str, Any] = {}
    placements: dict[str, Any] = {}
    if mode == "plate":
        images["ground"] = info(ground)
        textures["ground"] = {"image": "ground", "frame": {"x": 0, "y": 0, "width": width, "height": height}, "anchor": {"x": 0, "y": 0}}
        placements["ground"] = {"x": origin[0], "y": origin[1]}
    else:
        images["ground-reference"] = info(ground)
        for top in range(0, height, chunk_height):
            for left in range(0, width, chunk_width):
                actual_width = min(chunk_width, width - left)
                actual_height = min(chunk_height, height - top)
                identifier = f"ground-{left}-{top}"
                padded = Image.new("RGBA", (actual_width + 2 * gutter, actual_height + 2 * gutter), (0, 0, 0, 0))
                padded.paste(composed.crop((left, top, left + actual_width, top + actual_height)), (gutter, gutter))
                path = out_dir / f"{identifier}.png"
                save(padded, path)
                files.append(path)
                images[identifier] = info(path)
                textures[identifier] = {"image": identifier, "frame": {"x": gutter, "y": gutter, "width": actual_width, "height": actual_height}, "anchor": {"x": 0, "y": 0}}
                placements[identifier] = {"x": origin[0] + left, "y": origin[1] + top}
    packed = {"version": 1, "manifest": "manifest.json", "groups": [{"id": "ground", "kind": "surface", "textures": list(textures), "composition": {"reference": "ground.png", "origin": origin}, **({"coverageMask": "coverage.png"} if coverage_path else {})}]}
    packed_path = out_dir / "packed-art.json"
    packed_path.write_bytes(encoded(packed))
    files.append(packed_path)
    manifest = {"version": 1, "images": images, "textures": textures, "placements": placements}
    for path in files:
        if path.suffix == ".png":
            with Image.open(path) as image:
                image.load()
    rebuilt = Image.new("RGBA", (width, height))
    for identifier, placement in placements.items():
        texture = textures[identifier]
        frame = texture["frame"]
        with Image.open(out_dir / images[texture["image"]]["url"]) as image:
            rebuilt.paste(image.crop((frame["x"], frame["y"], frame["x"] + frame["width"], frame["y"] + frame["height"])), (placement["x"] - origin[0], placement["y"] - origin[1]))
    if rebuilt.tobytes() != composed.tobytes():
        error("emitted texture frames do not reconstruct ground RGBA exactly")
    if any(sha256(path) != expected for path, expected in input_hashes.items()):
        error("an input changed while preparing output")
    manifest_bytes = encoded(manifest)
    provenance = {"version": 1, "inputs": {"source": {"file": source_path.name, "sha256": source_hash}, "recipe": {"file": recipe_path.name, "sha256": recipe_hash}, "tool": {"file": Path(__file__).name, "sha256": sha256(Path(__file__))}, **({"coverageMask": {"file": coverage_path.name, "sha256": input_hashes[coverage_path]}} if coverage_path else {}), **({"movingMask": {"file": moving_path.name, "sha256": input_hashes[moving_path]}} if moving_path else {}), **({"caller": recipe["provenance"]} if "provenance" in recipe else {})}, "outputs": {**{path.name: sha256(path) for path in files}, "manifest.json": hashlib.sha256(manifest_bytes).hexdigest()}, "measurements": {"rgbaRecomposition": "exact", "width": width, "height": height}}
    (out_dir / "provenance.json").write_bytes(encoded(provenance))
    (out_dir / "timings.json").write_bytes(encoded({"seconds": round(time.perf_counter() - started, 6)}))
    (out_dir / "manifest.json").write_bytes(manifest_bytes)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a PNG ground plate or chunks from a version 1 recipe.")
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        run(args.recipe, args.out)
    except (RecipeError, OSError) as exc:
        print(f"prepare-ground: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
