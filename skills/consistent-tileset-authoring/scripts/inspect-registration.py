#!/usr/bin/env python3
"""Inspect explicitly supplied registration landmarks in two static PNGs.

This tool only measures the coordinates written in a version 1 recipe.  It does
not detect landmarks, fit a transform, warp either image, or judge artwork.
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
MAX_BOARD_PIXELS = 64_000_000
MAX_LANDMARKS = 256
ROOT_FIELDS = {"version", "layoutGuide", "candidate", "pixelTolerance", "expectedLandmarks", "observedLandmarks", "provenance"}


class RegistrationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RegistrationError(message)


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
        raise RegistrationError(f"{name} must stay inside the recipe directory") from None
    return resolved


def png(path: Path, name: str) -> Image.Image:
    require(path.is_file() and path.stat().st_size <= MAX_PNG_BYTES, f"{name} is missing or exceeds the byte cap")
    before = sha256(path)
    try:
        with Image.open(path) as image:
            require(image.format == "PNG" and getattr(image, "n_frames", 1) == 1, f"{name} must be a static PNG")
            require(0 < image.width <= MAX_AXIS and 0 < image.height <= MAX_AXIS and image.width * image.height <= MAX_PIXELS, f"{name} exceeds image resource bounds")
            decoded = image.convert("RGBA")
    except OSError as exc:
        raise RegistrationError(f"cannot read {name}: {exc}") from None
    require(sha256(path) == before, f"{name} changed while decoding")
    return decoded


def number(value: Any, name: str, maximum: float) -> float:
    require(type(value) in (int, float) and math.isfinite(float(value)) and 0 <= float(value) <= maximum, f"{name} must be a finite number in 0..{maximum:g}")
    return float(value)


def finite_json(value: Any) -> bool:
    if type(value) is float:
        return math.isfinite(value)
    if isinstance(value, list):
        return all(finite_json(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and finite_json(item) for key, item in value.items())
    return True


def landmarks(value: Any, name: str, width: int, height: int) -> dict[str, tuple[float, float]]:
    require(isinstance(value, list) and 3 <= len(value) <= MAX_LANDMARKS, f"{name} must contain 3..{MAX_LANDMARKS} landmarks")
    parsed: dict[str, tuple[float, float]] = {}
    for index, landmark in enumerate(value):
        require(isinstance(landmark, dict) and set(landmark) == {"id", "x", "y"}, f"{name}[{index}] must contain only id, x, y")
        identifier = landmark["id"]
        require(isinstance(identifier, str) and identifier and len(identifier) <= 128, f"{name}[{index}].id must be a nonempty string")
        require(identifier not in parsed, f"{name} has duplicate landmark id: {identifier}")
        parsed[identifier] = (number(landmark["x"], f"{name}[{index}].x", width - 1), number(landmark["y"], f"{name}[{index}].y", height - 1))
    require(len(set(parsed.values())) >= 3, f"{name} must use at least three distinct coordinates")
    return parsed


def marker(draw: ImageDraw.ImageDraw, x: float, y: float, color: str) -> None:
    radius = 5
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=color, width=2)
    draw.line((x - radius - 3, y, x + radius + 3, y), fill=color, width=1)
    draw.line((x, y - radius - 3, x, y + radius + 3), fill=color, width=1)


def checkerboard(width: int, height: int) -> Image.Image:
    backing = Image.new("RGB", (width, height), "#e7e4dc")
    draw = ImageDraw.Draw(backing)
    step = 12
    for top in range(0, height, step):
        for left in range(0, width, step):
            if (left // step + top // step) % 2:
                draw.rectangle((left, top, left + step - 1, top + step - 1), fill="#cac7c0")
    return backing


def label(draw: ImageDraw.ImageDraw, text: str, x: float, y: float, left: int, right: int, bottom: int, color: str) -> None:
    available = max(1, right - left - 4)
    rendered = text
    while rendered and draw.textlength(rendered) > available:
        rendered = rendered[:-4] + "..." if len(rendered) > 4 else ""
    if not rendered:
        return
    box = draw.textbbox((0, 0), rendered)
    label_width, label_height = box[2] - box[0], box[3] - box[1]
    draw.text((min(max(x + 7, left + 2), right - label_width - 2), min(max(y + 7, 2), bottom - label_height - 2)), rendered, fill=color)


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
        raise RegistrationError(f"cannot parse recipe: {exc}") from None
    require(type(recipe) is dict and set(recipe) <= ROOT_FIELDS, "recipe has unknown fields")
    require(finite_json(recipe), "recipe must not contain NaN or infinity")
    require(type(recipe.get("version")) is int and recipe["version"] == 1, "recipe version must be 1")
    root = recipe_path.parent.resolve()
    guide_path = local(root, recipe.get("layoutGuide"), "layoutGuide")
    candidate_path = local(root, recipe.get("candidate"), "candidate")
    require(guide_path != candidate_path, "layoutGuide and candidate must be different files")
    guide, candidate = png(guide_path, "layoutGuide"), png(candidate_path, "candidate")
    require(guide.size == candidate.size, "layoutGuide and candidate image dimensions must match")
    width, height = guide.size
    require(width * 2 * (height + 64) <= MAX_BOARD_PIXELS, "registration board exceeds output resource bounds")
    tolerance = number(recipe.get("pixelTolerance"), "pixelTolerance", max(width, height))
    expected = landmarks(recipe.get("expectedLandmarks"), "expectedLandmarks", width, height)
    observed = landmarks(recipe.get("observedLandmarks"), "observedLandmarks", width, height)
    require(set(expected) == set(observed), "expectedLandmarks and observedLandmarks must have the same landmark IDs")
    # Corners alone can agree while an interior path, bridge, or junction has moved.
    require(any(0 < x < width - 1 and 0 < y < height - 1 for x, y in expected.values()), "expectedLandmarks must include an interior landmark")
    inputs = {"recipe": {"file": recipe_path.name, "sha256": recipe_hash}, "layoutGuide": {"file": guide_path.name, "sha256": sha256(guide_path), "dimensions": [width, height]}, "candidate": {"file": candidate_path.name, "sha256": sha256(candidate_path), "dimensions": [width, height]}, "tool": {"file": Path(__file__).name, "sha256": sha256(Path(__file__).resolve())}}
    require(not any(path.is_relative_to(out_dir) for path in (recipe_path, guide_path, candidate_path)), "--out must not contain an input")
    rows = []
    for identifier in sorted(expected):
        ex, ey = expected[identifier]
        ox, oy = observed[identifier]
        dx, dy = ox - ex, oy - ey
        residual = math.hypot(dx, dy)
        rows.append({"id": identifier, "expected": {"x": ex, "y": ey}, "observed": {"x": ox, "y": oy}, "residual": {"dx": dx, "dy": dy, "distance": residual}, "withinTolerance": residual <= tolerance})
    passed = all(row["withinTolerance"] for row in rows)
    board = Image.new("RGB", (width * 2, height + 64), "#20242a")
    guide_backing = checkerboard(width, height)
    candidate_backing = checkerboard(width, height)
    guide_backing.paste(guide, mask=guide.getchannel("A"))
    candidate_backing.paste(candidate, mask=candidate.getchannel("A"))
    board.paste(guide_backing, (0, 0))
    board.paste(candidate_backing, (width, 0))
    draw = ImageDraw.Draw(board)
    draw.text((4, height + 4), "Caller-supplied landmarks only; no automatic detection or fitting.", fill="white")
    draw.text((4, height + 21), f"Tolerance: {tolerance:g}px; max residual: {max(row['residual']['distance'] for row in rows):.3f}px.", fill="white")
    draw.text((4, height + 42), "Layout guide: expected landmarks", fill="white")
    draw.text((width + 4, height + 42), "Candidate: observed landmarks", fill="white")
    for row in rows:
        ex, ey = row["expected"]["x"], row["expected"]["y"]
        ox, oy = row["observed"]["x"], row["observed"]["y"]
        color = "#55dd88" if row["withinTolerance"] else "#ff5b5b"
        marker(draw, ex, ey, color)
        marker(draw, width + ox, oy, color)
        label(draw, row["id"], ex, ey, 0, width, height, color)
        label(draw, f"{row['id']} d={row['residual']['distance']:.3f}", width + ox, oy, width, width * 2, height, color)
    limit = ("Measurements compare only caller-supplied landmark coordinates. The tool does not detect landmarks, "
             "fit registration, warp pixels, compare image content, or certify geometry, perspective, style, seam quality, or gameplay.")
    measurements = {"version": 1, "passed": passed, "pixelTolerance": tolerance, "dimensions": [width, height], "landmarks": rows, "maximumResidual": max(row["residual"]["distance"] for row in rows), "limit": limit}
    require(sha256(recipe_path) == recipe_hash and sha256(guide_path) == inputs["layoutGuide"]["sha256"] and sha256(candidate_path) == inputs["candidate"]["sha256"], "an input changed during inspection")
    out_dir.mkdir(parents=True, exist_ok=False)
    board_path = out_dir / "registration-board.png"
    board.save(board_path, format="PNG", optimize=False, compress_level=9)
    provenance = {"version": 1, "inputs": inputs, "outputs": {"registration-board.png": sha256(board_path)}, "caller": recipe.get("provenance"), "toolLimit": limit}
    (out_dir / "measurements.json").write_text(json.dumps(measurements, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (out_dir / "provenance.json").write_text(json.dumps(provenance, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (out_dir / "timings.json").write_text(json.dumps({"elapsedSeconds": round(perf_counter() - started, 6)}, allow_nan=False) + "\n", encoding="utf-8")
    return measurements


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path, help="version 1 registration recipe")
    parser.add_argument("--out", type=Path, required=True, help="new output directory")
    args = parser.parse_args()
    try:
        result = inspect(args.recipe, args.out)
    except (RegistrationError, OSError, TypeError) as exc:
        print(f"inspect-registration: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"passed": result["passed"], "pixelTolerance": result["pixelTolerance"], "maximumResidual": result["maximumResidual"]}, indent=2))
    return 0 if result["passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
