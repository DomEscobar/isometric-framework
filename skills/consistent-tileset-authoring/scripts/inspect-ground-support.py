#!/usr/bin/env python3
"""Check caller-reviewed binary support masks along projected routes.

This version 1 helper does no image segmentation or projection.  Recipe paths
are local to the recipe; callers own mask review and public projection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

from PIL import Image, ImageDraw

MAX_RECIPE_BYTES = 1_048_576
MAX_PNG_BYTES = 64 * 1024 * 1024
MAX_AXIS = 8192
MAX_PIXELS = 16_000_000
MAX_MASKS = 16
MAX_ROUTES = 128
MAX_POINTS_PER_ROUTE = 512
MAX_SAMPLES = 100_000
MAX_FOOTPRINT_PIXELS = 65_536
MAX_CHECKS = 20_000_000
ROOT_FIELDS = {"version", "overlay", "supportMasks", "footprint", "routes"}
MASK_FIELDS = {"id", "image"}
FOOTPRINT_FIELDS = {"halfWidthPx", "halfHeightPx"}
ROUTE_FIELDS = {"id", "points", "clearancePx"}


class GroundSupportError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GroundSupportError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def local(root: Path, value: Any, name: str) -> Path:
    require(isinstance(value, str) and value and ":" not in value and "\\" not in value, f"{name} must be a local relative forward-slash path")
    raw = Path(value)
    require(not raw.is_absolute(), f"{name} must be relative to the recipe")
    resolved = (root / raw).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise GroundSupportError(f"{name} must stay inside the recipe directory") from None
    return resolved


def static_png(path: Path, name: str) -> tuple[Image.Image, str]:
    require(path.is_file() and path.stat().st_size <= MAX_PNG_BYTES, f"{name} is missing or exceeds the byte cap")
    before = sha256(path)
    try:
        with Image.open(path) as image:
            require(image.format == "PNG" and getattr(image, "n_frames", 1) == 1, f"{name} must be a static PNG")
            require(0 < image.width <= MAX_AXIS and 0 < image.height <= MAX_AXIS and image.width * image.height <= MAX_PIXELS, f"{name} exceeds image resource bounds")
            decoded = image.convert("RGBA")
    except OSError as exc:
        raise GroundSupportError(f"cannot read {name}: {exc}") from None
    require(sha256(path) == before, f"{name} changed while decoding")
    return decoded, before


def binary_mask(path: Path, name: str) -> tuple[Image.Image, str]:
    image, digest = static_png(path, name)
    # RGB/L masks are accepted only when every decoded pixel is opaque black or white.
    for pixel in image.getdata():
        require(pixel in ((0, 0, 0, 255), (255, 255, 255, 255)), f"{name} must be a binary opaque black/white PNG")
    return image.getchannel("R"), digest


def number(value: Any, name: str, maximum: float) -> float:
    try:
        parsed = float(value) if type(value) in (int, float) else None
    except OverflowError:
        parsed = None
    require(parsed is not None and math.isfinite(parsed) and 0 <= parsed <= maximum, f"{name} must be a finite number in 0..{maximum:g}")
    return parsed


def finite_json(value: Any) -> bool:
    if type(value) is float:
        return math.isfinite(value)
    if isinstance(value, list):
        return all(finite_json(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and finite_json(item) for key, item in value.items())
    return True


def parse_routes(value: Any, width: int, height: int) -> list[dict[str, Any]]:
    require(isinstance(value, list) and 1 <= len(value) <= MAX_ROUTES, f"routes must contain 1..{MAX_ROUTES} routes")
    parsed, ids = [], set()
    for index, route in enumerate(value):
        require(type(route) is dict and set(route) == ROUTE_FIELDS, f"routes[{index}] must contain only id, points, clearancePx")
        identifier = route["id"]
        require(isinstance(identifier, str) and identifier and len(identifier) <= 128 and identifier not in ids, f"routes[{index}].id must be a unique nonempty string")
        ids.add(identifier)
        points = route["points"]
        require(isinstance(points, list) and 2 <= len(points) <= MAX_POINTS_PER_ROUTE, f"routes[{index}].points must contain 2..{MAX_POINTS_PER_ROUTE} points")
        parsed_points = []
        for point_index, point in enumerate(points):
            require(isinstance(point, list) and len(point) == 2, f"routes[{index}].points[{point_index}] must be [x, y]")
            parsed_points.append((number(point[0], f"routes[{index}].points[{point_index}][0]", MAX_AXIS * 4), number(point[1], f"routes[{index}].points[{point_index}][1]", MAX_AXIS * 4)))
        clearance = number(route["clearancePx"], f"routes[{index}].clearancePx", max(width, height))
        parsed.append({"id": identifier, "points": parsed_points, "clearancePx": clearance})
    return parsed


def footprint_offsets(half_width: float, half_height: float, clearance: float) -> list[tuple[int, int]]:
    # A filled diamond, expanded with a square clearance margin, is intentionally conservative.
    extent_x = math.ceil(half_width + clearance + 1)
    extent_y = math.ceil(half_height + clearance + 1)
    require((extent_x * 2 + 1) * (extent_y * 2 + 1) <= MAX_FOOTPRINT_PIXELS, "footprint search exceeds resource bounds")
    result = []
    for dy in range(-extent_y, extent_y + 1):
        for dx in range(-extent_x, extent_x + 1):
            if max(0.0, abs(dx) - clearance) / max(half_width, 0.5) + max(0.0, abs(dy) - clearance) / max(half_height, 0.5) <= 1:
                result.append((dx, dy))
    require(len(result) <= MAX_FOOTPRINT_PIXELS, "footprint exceeds resource bounds")
    return result


def samples(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    result = []
    for start, end in zip(points, points[1:]):
        distance = math.dist(start, end)
        steps = max(1, math.ceil(distance))
        for step in range(steps + 1):
            if result and step == 0:
                continue
            fraction = step / steps
            result.append((start[0] + (end[0] - start[0]) * fraction, start[1] + (end[1] - start[1]) * fraction))
    return result


def sample_count(points: list[tuple[float, float]]) -> int:
    return 1 + sum(max(1, math.ceil(math.dist(start, end))) for start, end in zip(points, points[1:]))


def footprint_search_pixels(half_width: float, half_height: float, clearance: float) -> int:
    extent_x = math.ceil(half_width + clearance + 1)
    extent_y = math.ceil(half_height + clearance + 1)
    return (extent_x * 2 + 1) * (extent_y * 2 + 1)


def covered(mask: Image.Image, x: float, y: float, offsets: list[tuple[int, int]]) -> tuple[bool, list[int] | None]:
    # floor/ceil both participate: a subpixel footprint cannot slip between pixels.
    bases_x = {math.floor(x), math.ceil(x)}
    bases_y = {math.floor(y), math.ceil(y)}
    width, height = mask.size
    pixels = mask.load()
    for base_y in bases_y:
        for base_x in bases_x:
            for dx, dy in offsets:
                px, py = base_x + dx, base_y + dy
                if not (0 <= px < width and 0 <= py < height) or pixels[px, py] != 255:
                    return False, [px, py]
    return True, None


def inspect(recipe_path: Path, out_dir: Path) -> dict[str, Any]:
    started = perf_counter()
    recipe_path, out_dir = Path(recipe_path).resolve(), Path(out_dir).resolve()
    require(recipe_path.is_file() and recipe_path.stat().st_size <= MAX_RECIPE_BYTES, "recipe is missing or exceeds the byte cap")
    require(not out_dir.exists(), "--out must name a new directory; it will not be overwritten")
    recipe_bytes = recipe_path.read_bytes()
    recipe_hash = hashlib.sha256(recipe_bytes).hexdigest()
    try:
        recipe = json.loads(recipe_bytes.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GroundSupportError(f"cannot parse recipe: {exc}") from None
    require(type(recipe) is dict and set(recipe) == ROOT_FIELDS and finite_json(recipe), "recipe must contain only version, overlay, supportMasks, footprint, routes with finite JSON")
    require(type(recipe["version"]) is int and recipe["version"] == 1, "recipe version must be 1")
    root = recipe_path.parent.resolve()
    overlay_path = local(root, recipe["overlay"], "overlay")
    overlay, overlay_hash = static_png(overlay_path, "overlay")
    width, height = overlay.size
    masks_value = recipe["supportMasks"]
    require(isinstance(masks_value, list) and 1 <= len(masks_value) <= MAX_MASKS, f"supportMasks must contain 1..{MAX_MASKS} masks")
    masks, mask_ids, mask_paths = [], set(), []
    for index, item in enumerate(masks_value):
        require(type(item) is dict and set(item) == MASK_FIELDS, f"supportMasks[{index}] must contain only id, image")
        identifier = item["id"]
        require(isinstance(identifier, str) and identifier and len(identifier) <= 128 and identifier not in mask_ids, f"supportMasks[{index}].id must be a unique nonempty string")
        mask_ids.add(identifier)
        path = local(root, item["image"], f"supportMasks[{index}].image")
        require(path not in mask_paths and path != overlay_path, "mask images must be distinct from each other and overlay")
        mask_paths.append(path)
        mask, mask_hash = binary_mask(path, f"supportMasks[{index}].image")
        require(mask.size == (width, height), "support mask dimensions must match overlay")
        masks.append((identifier, mask, path, mask_hash))
    require(type(recipe["footprint"]) is dict and set(recipe["footprint"]) == FOOTPRINT_FIELDS, "footprint must contain only halfWidthPx, halfHeightPx")
    half_width = number(recipe["footprint"]["halfWidthPx"], "footprint.halfWidthPx", 512)
    half_height = number(recipe["footprint"]["halfHeightPx"], "footprint.halfHeightPx", 512)
    require(half_width > 0 and half_height > 0, "footprint dimensions must be greater than zero")
    routes = parse_routes(recipe["routes"], width, height)
    route_sample_counts = [(route, sample_count(route["points"])) for route in routes]
    total_samples = sum(count for _, count in route_sample_counts)
    require(total_samples <= MAX_SAMPLES, "route samples exceed resource bounds")
    route_search_pixels = {route["id"]: footprint_search_pixels(half_width, half_height, route["clearancePx"]) for route in routes}
    require(all(pixels <= MAX_FOOTPRINT_PIXELS for pixels in route_search_pixels.values()), "footprint search exceeds resource bounds")
    require(sum(count * route_search_pixels[route["id"]] * len(masks) * 4 for route, count in route_sample_counts) <= MAX_CHECKS, "support checks exceed resource bounds")
    offsets = {route["id"]: footprint_offsets(half_width, half_height, route["clearancePx"]) for route in routes}
    route_samples = [(route, samples(route["points"])) for route in routes]
    require(not any(path.is_relative_to(out_dir) for path in [recipe_path, overlay_path, *mask_paths]), "--out must not contain an input")
    inputs = {"recipe": {"file": recipe_path.name, "sha256": recipe_hash}, "overlay": {"file": overlay_path.name, "sha256": overlay_hash, "dimensions": [width, height]}, "supportMasks": [{"id": ident, "file": path.name, "sha256": digest, "dimensions": [width, height]} for ident, _, path, digest in masks], "tool": {"file": Path(__file__).name, "sha256": sha256(Path(__file__).resolve())}}
    route_rows, failures = [], []
    for route, points in route_samples:
        per_mask = {ident: {"failedSamples": 0, "firstDefect": None} for ident, _, _, _ in masks}
        route_failed = 0
        for sample_index, (x, y) in enumerate(points):
            failed_here = False
            for ident, mask, _, _ in masks:
                ok, defect = covered(mask, x, y, offsets[route["id"]])
                if not ok:
                    failed_here = True
                    per_mask[ident]["failedSamples"] += 1
                    if per_mask[ident]["firstDefect"] is None:
                        per_mask[ident]["firstDefect"] = {"sampleIndex": sample_index, "center": [x, y], "pixel": defect}
            if failed_here:
                route_failed += 1
                failures.append((x, y, route["id"]))
        route_rows.append({"id": route["id"], "clearancePx": route["clearancePx"], "sampleCount": len(points), "failedSamples": route_failed, "masks": per_mask})
    passed = not failures
    review = overlay.copy()
    draw = ImageDraw.Draw(review)
    for route, points in route_samples:
        draw.line(points, fill="#00e878", width=2)
    for x, y, _ in failures:
        draw.polygon([(x - half_width, y), (x, y - half_height), (x + half_width, y), (x, y + half_height)], outline="#ff3030", width=2)
        draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill="#ff3030")
    limit = "Checks only caller-reviewed, same-size binary support masks against declared projected routes and footprint. It does not segment images, validate masks or authorship, establish public projection, or certify browser behavior, motion, gameplay, or artwork."
    measurements = {"version": 1, "passed": passed, "dimensions": [width, height], "footprint": {"halfWidthPx": half_width, "halfHeightPx": half_height, "shape": "diamond expanded by square clearance"}, "routes": route_rows, "totalSamples": total_samples, "failedSamples": len(failures), "inputs": inputs, "limit": limit}
    require(sha256(recipe_path) == recipe_hash and sha256(overlay_path) == overlay_hash and all(sha256(path) == digest for _, _, path, digest in masks), "an input changed during inspection")
    out_dir.mkdir(parents=True, exist_ok=False)
    review_path = out_dir / "ground-support-review.png"
    review.save(review_path, format="PNG", optimize=False, compress_level=9)
    (out_dir / "measurements.json").write_text(json.dumps(measurements, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (out_dir / "provenance.json").write_text(json.dumps({"version": 1, "inputs": inputs, "outputs": {"ground-support-review.png": sha256(review_path)}, "toolLimit": limit}, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (out_dir / "timings.json").write_text(json.dumps({"elapsedSeconds": round(perf_counter() - started, 6)}, allow_nan=False) + "\n", encoding="utf-8")
    return measurements


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path, help="version 1 ground support recipe")
    parser.add_argument("--out", type=Path, required=True, help="new output directory")
    args = parser.parse_args()
    try:
        result = inspect(args.recipe, args.out)
    except (GroundSupportError, OSError, TypeError) as exc:
        print(f"inspect-ground-support: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"passed": result["passed"], "totalSamples": result["totalSamples"], "failedSamples": result["failedSamples"]}, indent=2))
    return 0 if result["passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
