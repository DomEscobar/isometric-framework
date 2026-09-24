"""Deterministic animation processing stages.

The public entry point is run_stage(stage, workdir, params). Provider-backed
stages use provider.WaveSpeedProvider and never accept client-supplied URLs.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

from PIL import Image

import provider

_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_STATUSES = {"completed", "needs_review", "needs_attention"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def _request_hash(stage: str, params: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical({"stage": stage, "params": params})).hexdigest()


def _atomic_json(path: Path, value: Any) -> None:
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _workdir(value: Path) -> Path:
    path = Path(value)
    if not path.is_dir() or path.is_symlink():
        raise ValueError("workdir must be an existing real directory")
    return path.resolve()


def _safe_path(root: Path, value: Any, *, must_exist: bool = True, suffixes: set[str] | None = None) -> Path:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError("input must be a safe relative path")
    relative = Path(value)
    if relative.is_absolute() or any(part in ("", ".", "..") or not _SAFE_COMPONENT.fullmatch(part) for part in relative.parts):
        raise ValueError("input must be a safe relative path")
    candidate = root.joinpath(relative)
    try:
        resolved = candidate.resolve(strict=must_exist)
    except OSError as error:
        raise ValueError("input does not exist") from error
    if resolved != root and root not in resolved.parents:
        raise ValueError("input must stay inside workdir")
    if candidate.is_symlink() or (must_exist and not resolved.is_file()):
        raise ValueError("input must be a regular job file")
    if suffixes is not None and resolved.suffix.lower() not in suffixes:
        raise ValueError("input has unsupported extension")
    return resolved


def _alpha_details(image: Image.Image) -> dict[str, Any]:
    alpha = image.getchannel("A")
    histogram = alpha.histogram()
    extrema = alpha.getextrema()
    return {
        "minimum": extrema[0],
        "maximum": extrema[1],
        "transparent_pixels": histogram[0],
        "semi_transparent_pixels": sum(histogram[1:255]),
        "opaque_pixels": histogram[255],
        "visible_bounds": list(alpha.getbbox()) if alpha.getbbox() else None,
        "has_true_alpha": histogram[0] > 0 and sum(histogram[1:]) > 0,
    }


def _result(status: str, artifacts: list[str], details: dict[str, Any]) -> dict[str, Any]:
    if status not in _STATUSES:
        raise ValueError("invalid internal stage status")
    return {"status": status, "artifacts": artifacts, "details": details}


def _inspect_reference(root: Path, params: dict[str, Any]) -> dict[str, Any]:
    if set(params) != {"input"}:
        raise ValueError("inspect_reference params must contain only input")
    source = _safe_path(root, params["input"], suffixes={".png", ".jpg", ".jpeg", ".webp"})
    try:
        with Image.open(source) as opened:
            opened.verify()
        with Image.open(source) as opened:
            source_format = opened.format
            source_mode = opened.mode
            rgba = opened.convert("RGBA")
    except (OSError, ValueError) as error:
        raise ValueError("input is not a valid supported image") from error
    details = {
        "input": source.relative_to(root).as_posix(),
        "sha256": _sha256(source),
        "bytes": source.stat().st_size,
        "format": source_format,
        "mode": source_mode,
        "width": rgba.width,
        "height": rgba.height,
        "alpha": _alpha_details(rgba),
        "visual_approval": False,
    }
    rgba.close()
    result = _result("completed", ["inspect-reference.json"], details)
    record = {"version": 1, "stage": "inspect_reference", "request_sha256": _request_hash("inspect_reference", params), "result": result}
    target = root / "inspect-reference.json"
    if target.exists():
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("existing inspect state is invalid") from error
        if existing != record:
            raise ValueError("inspect_reference state conflicts with this request or source")
        return existing["result"]
    _atomic_json(target, record)
    return result


def _integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer between {minimum} and {maximum}")
    return value


def _number(value: Any, name: str, minimum: float, maximum: float) -> float:
    if type(value) not in (int, float) or not minimum <= float(value) <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return float(value)


def _identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise ValueError(f"{name} must be a safe lowercase identifier")
    return value


def _rgba_source(root: Path, value: Any) -> tuple[Path, Image.Image, tuple[int, int, int, int]]:
    path = _safe_path(root, value, suffixes={".png"})
    try:
        with Image.open(path) as opened:
            if opened.format != "PNG":
                raise ValueError("pack inputs must be PNG")
            image = opened.convert("RGBA")
    except OSError as error:
        raise ValueError("pack input is not a valid PNG") from error
    box = image.getchannel("A").getbbox()
    if box is None:
        image.close()
        raise ValueError("pack input has empty alpha")
    return path, image, box


def _alpha_centroid_x(image: Image.Image) -> float:
    alpha = image.getchannel("A")
    total = 0
    weighted = 0
    for y in range(alpha.height):
        for x in range(alpha.width):
            value = alpha.getpixel((x, y))
            total += value
            weighted += x * value
    alpha.close()
    if total == 0:
        raise ValueError("pack input has empty alpha")
    return weighted / total


def _verify_cached(root: Path, state_name: str, request: dict[str, Any], required: list[str]) -> dict[str, Any] | None:
    state_path = root / state_name
    if not state_path.exists():
        return None
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"existing {state_name} is invalid") from error
    if state.get("request") != request:
        raise ValueError(f"existing {state_name} conflicts with this request or source")
    for name in required:
        target = _safe_path(root, name)
        expected = state.get("output_hashes", {}).get(name)
        if not isinstance(expected, str) or _sha256(target) != expected:
            raise ValueError(f"cached output hash mismatch: {name}")
    return state.get("result")


def _pack(root: Path, params: dict[str, Any]) -> dict[str, Any]:
    required_keys = {"inputs", "image_id", "action", "direction", "fps", "loop", "canvas", "target_visible_height", "target_root", "anchor", "gutter", "columns", "resample"}
    if set(params) not in {frozenset(required_keys), frozenset(required_keys | {"cleanup"})}:
        raise ValueError("pack params do not match the documented schema")
    inputs = params["inputs"]
    if not isinstance(inputs, list) or not 1 <= len(inputs) <= 512 or len(set(inputs)) != len(inputs):
        raise ValueError("inputs must be 1..512 unique PNG basenames")
    image_id = _identifier(params["image_id"], "image_id")
    action = _identifier(params["action"], "action")
    direction = _identifier(params["direction"], "direction")
    fps = _number(params["fps"], "fps", 0.01, 120)
    if type(params["loop"]) is not bool:
        raise ValueError("loop must be boolean")
    canvas = params["canvas"]
    root_target = params["target_root"]
    anchor = params["anchor"]
    if not all(isinstance(item, dict) for item in (canvas, root_target, anchor)):
        raise ValueError("canvas, target_root and anchor must be objects")
    if set(canvas) != {"width", "height"} or set(root_target) != {"x", "y"} or set(anchor) != {"x", "y"}:
        raise ValueError("invalid canvas, target_root or anchor fields")
    canvas_width = _integer(canvas["width"], "canvas.width", 1, 4096)
    canvas_height = _integer(canvas["height"], "canvas.height", 1, 4096)
    target_root = (_integer(root_target["x"], "target_root.x", 0, canvas_width - 1), _integer(root_target["y"], "target_root.y", 0, canvas_height - 1))
    target_height = _integer(params["target_visible_height"], "target_visible_height", 1, 4096)
    anchor_value = {"x": _number(anchor["x"], "anchor.x", 0, 1), "y": _number(anchor["y"], "anchor.y", 0, 1)}
    gutter = _integer(params["gutter"], "gutter", 0, 64)
    columns = _integer(params["columns"], "columns", 1, 512)
    if params["resample"] not in {"nearest", "lanczos"}:
        raise ValueError("resample must be nearest or lanczos")
    cleanup = params.get("cleanup")
    cleanup_recipe = None
    if cleanup is not None:
        if cleanup != {"recipe": "conservative-alpha-fringe-v1", "minimum_visible_alpha": 8}:
            raise ValueError("cleanup must select the pinned conservative-alpha-fringe-v1 recipe")
        cleanup_recipe = {
            "recipe": "conservative-alpha-fringe-v1",
            "minimum_visible_alpha": 8,
            "operation": "after shared transform, clear RGBA only where 0 < alpha < 8",
            "strong_pixels_unchanged": True,
            "component_removal": False,
            "hole_fill": False,
            "color_key": False,
        }
        cleanup_recipe["recipe_sha256"] = hashlib.sha256(_canonical(cleanup_recipe)).hexdigest()

    loaded = [_rgba_source(root, value) for value in inputs]
    try:
        sizes = {item[1].size for item in loaded}
        if len(sizes) != 1:
            raise ValueError("all pack inputs must have the same dimensions")
        source_hashes = {path.relative_to(root).as_posix(): _sha256(path) for path, _image, _box in loaded}
        request = {"stage": "pack", "params": params, "input_sha256": source_hashes}
        output_names = [f"normalized-frame-{index:04d}.png" for index in range(len(loaded))] + ["normalization.json", "atlas.png", "atlas-manifest.json", "pack-result.json"]
        cached = _verify_cached(root, "pack-state.json", request, output_names)
        if cached is not None:
            return cached

        heights = [box[3] - box[1] for _path, _image, box in loaded]
        centroids = [_alpha_centroid_x(image) for _path, image, _box in loaded]
        bottoms = [box[3] - 1 for _path, _image, box in loaded]
        shared_scale = target_height / float(median(heights))
        source_root = (float(median(centroids)), float(median(bottoms)))
        source_width, source_height = loaded[0][1].size
        scaled_size = (max(1, round(source_width * shared_scale)), max(1, round(source_height * shared_scale)))
        paste = (target_root[0] - round(source_root[0] * shared_scale), target_root[1] - round(source_root[1] * shared_scale))
        resampling = Image.Resampling.NEAREST if params["resample"] == "nearest" else Image.Resampling.LANCZOS
        normalized_records: list[dict[str, Any]] = []
        normalized_images: list[Image.Image] = []
        for index, (source_path, source, source_box) in enumerate(loaded):
            scaled = source.resize(scaled_size, resampling)
            target = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
            target.alpha_composite(scaled, paste)
            scaled.close()
            cleanup_record = None
            if cleanup_recipe is not None:
                before_hash = hashlib.sha256(target.tobytes()).hexdigest()
                pixels = list(target.get_flattened_data())
                cleared = sum(1 for _r, _g, _b, alpha in pixels if 0 < alpha < 8)
                rgb_cleared = sum(1 for red, green, blue, alpha in pixels if 0 < alpha < 8 and (red != 0 or green != 0 or blue != 0))
                if cleared:
                    target.putdata([(0, 0, 0, 0) if 0 < alpha < 8 else (red, green, blue, alpha) for red, green, blue, alpha in pixels])
                cleanup_record = {
                    "pre_cleanup_rgba_sha256": before_hash,
                    "post_cleanup_rgba_sha256": hashlib.sha256(target.tobytes()).hexdigest(),
                    "alpha_pixels_cleared": cleared,
                    "rgb_pixels_cleared": rgb_cleared,
                    "pixels_alpha_ge_8_changed": 0,
                }
            output_box = target.getchannel("A").getbbox()
            if output_box is None or output_box[0] <= 0 or output_box[1] <= 0 or output_box[2] >= canvas_width or output_box[3] >= canvas_height:
                target.close()
                raise ValueError(f"normalized frame {index} clips or touches canvas edge")
            output_name = f"normalized-frame-{index:04d}.png"
            target.save(root / output_name, format="PNG")
            normalized_images.append(target)
            normalized_records.append({
                "order": index,
                "input": source_path.relative_to(root).as_posix(),
                "input_sha256": source_hashes[source_path.relative_to(root).as_posix()],
                "input_alpha_bounds": list(source_box),
                "output": output_name,
                "output_sha256": _sha256(root / output_name),
                "output_alpha": _alpha_details(target),
                "scaled_full_canvas": list(scaled_size),
                "paste_offset": list(paste),
                "quality_cleanup": cleanup_record,
            })
        normalization = {
            "version": 1,
            "kind": "shared-scale-root-normalization",
            "shared_transform": {
                "scale": shared_scale,
                "source_root": list(source_root),
                "target_root": list(target_root),
                "scaled_full_canvas": list(scaled_size),
                "paste_offset": list(paste),
                "resample": params["resample"],
                "per_frame_recenter": False,
                "per_frame_scale": False,
                "alpha": (
                    "RGBA preserved except explicit conservative-alpha-fringe-v1 cleanup below"
                    if cleanup_recipe is not None
                    else "RGBA preserved; no threshold, key, recolor, or palette conversion"
                ),
            },
            "canvas": {"width": canvas_width, "height": canvas_height},
            "frames": normalized_records,
        }
        if cleanup_recipe is not None:
            normalization["quality_cleanup"] = {
                **cleanup_recipe,
                "total_pixels_cleared": sum(frame["quality_cleanup"]["alpha_pixels_cleared"] for frame in normalized_records),
                "total_rgb_pixels_cleared": sum(frame["quality_cleanup"]["rgb_pixels_cleared"] for frame in normalized_records),
            }
        _atomic_json(root / "normalization.json", normalization)

        used_columns = min(columns, len(normalized_images))
        rows = math.ceil(len(normalized_images) / used_columns)
        atlas_width = gutter + used_columns * (canvas_width + gutter)
        atlas_height = gutter + rows * (canvas_height + gutter)
        atlas = Image.new("RGBA", (atlas_width, atlas_height), (0, 0, 0, 0))
        frames: list[dict[str, Any]] = []
        frame_ids: list[str] = []
        for index, image in enumerate(normalized_images):
            x = gutter + (index % used_columns) * (canvas_width + gutter)
            y = gutter + (index // used_columns) * (canvas_height + gutter)
            atlas.alpha_composite(image, (x, y))
            frame_id = f"{image_id}.{action}.{direction}.{index:04d}"
            frame_ids.append(frame_id)
            frames.append({
                "id": frame_id,
                "order": index,
                "rect": {"x": x, "y": y, "width": canvas_width, "height": canvas_height},
                "anchor": anchor_value,
                "source": normalized_records[index],
            })
        atlas.save(root / "atlas.png", format="PNG")
        atlas.close()
        for image in normalized_images:
            image.close()
        atlas_hash = _sha256(root / "atlas.png")
        manifest = {
            "schema": "animation-pipeline-atlas-v1",
            "version": 1,
            "certification": {"stock_framework_v4_claimed": False, "note": "Generic deterministic row-major atlas; not the framework V4 provenance format."},
            "image": {"id": image_id, "file": "atlas.png", "sha256": atlas_hash, "width": atlas_width, "height": atlas_height, "sampling": params["resample"]},
            "packing": {"columns": used_columns, "rows": rows, "gutter": gutter, "cell": {"width": canvas_width, "height": canvas_height}},
            "clip": {"id": f"{image_id}.{action}.{direction}", "action": action, "direction": direction, "fps": fps, "loop": params["loop"], "frames": frame_ids},
            "frames": frames,
            "normalization": {"file": "normalization.json", "sha256": _sha256(root / "normalization.json")},
        }
        if cleanup_recipe is not None:
            manifest["quality_cleanup"] = normalization["quality_cleanup"]
        _atomic_json(root / "atlas-manifest.json", manifest)
        manifest_hash = _sha256(root / "atlas-manifest.json")
        details = {
            "schema": "animation-pipeline-atlas-v1",
            "frame_count": len(frames),
            "canvas": {"width": canvas_width, "height": canvas_height},
            "atlas": {"width": atlas_width, "height": atlas_height},
            "atlas_sha256": atlas_hash,
            "manifest_sha256": manifest_hash,
            "shared_scale": shared_scale,
            "shared_source_root": list(source_root),
            "target_root": list(target_root),
            "visual_approval": False,
            "stock_framework_v4_claimed": False,
        }
        artifacts = [f"normalized-frame-{index:04d}.png" for index in range(len(frames))] + ["normalization.json", "atlas.png", "atlas-manifest.json", "pack-result.json", "pack-state.json"]
        result = _result("needs_review", artifacts, details)
        _atomic_json(root / "pack-result.json", {"version": 1, "result": result, "atlas_sha256": atlas_hash, "manifest_sha256": manifest_hash})
        output_hashes = {name: _sha256(root / name) for name in output_names}
        _atomic_json(root / "pack-state.json", {"version": 1, "request": request, "output_hashes": output_hashes, "result": result})
        return result
    finally:
        for _path, image, _box in loaded:
            image.close()


def _extract_frames(root: Path, params: dict[str, Any]) -> dict[str, Any]:
    base_keys = {"input", "fps", "indices", "output_prefix"}
    if frozenset(params) not in {frozenset(base_keys), frozenset(base_keys | {"automatic_review"})}:
        raise ValueError("extract_frames params do not match the documented schema")
    automatic_review = params.get("automatic_review")
    if automatic_review is not None:
        required_review_keys = {"id", "model", "source_sha256"}
        density_keys = {"density_receipt", "density_receipt_sha256", "density_policy_sha256"}
        if not isinstance(automatic_review, dict) or frozenset(automatic_review) not in {
            frozenset(required_review_keys), frozenset(required_review_keys | density_keys)
        }:
            raise ValueError("automatic review receipt is invalid")
        if automatic_review["model"] != "google/gemini-3.8-flash":
            raise ValueError("automatic review model is invalid")
        if density_keys <= set(automatic_review):
            density_path = _safe_path(root, automatic_review["density_receipt"], suffixes={".json"})
            if _sha256(density_path) != automatic_review["density_receipt_sha256"]:
                raise ValueError("density selection receipt hash is stale")
    source = _safe_path(root, params["input"], suffixes={".mp4", ".mov", ".webm", ".mkv"})
    fps = _number(params["fps"], "fps", 0.01, 120)
    indices = params["indices"]
    if not isinstance(indices, list) or not indices or len(indices) > 512 or any(type(item) is not int or not 0 <= item <= 100000 for item in indices) or indices != sorted(set(indices)):
        raise ValueError("indices must be a non-empty sorted list of unique non-negative integers")
    prefix = _identifier(params["output_prefix"], "output_prefix")
    source_hash = _sha256(source)
    if automatic_review is not None and automatic_review["source_sha256"] != source_hash:
        raise ValueError("automatic review source hash is stale")

    request = {"stage": "extract_frames", "params": params, "input_sha256": source_hash}
    output_names = [f"{prefix}-frame-{order:04d}.png" for order in range(len(indices))] + ["extract-frames.json"]
    cached = _verify_cached(root, "extract-frames-state.json", request, output_names)
    if cached is not None:
        return cached
    decode_dir = Path(tempfile.mkdtemp(prefix=".extract-", dir=root))
    try:
        frame_filter = (
            "select=" + "+".join(f"eq(n\\,{index})" for index in indices)
            if automatic_review is not None
            else f"fps={fps:.12g}"
        )
        command = ["ffmpeg", "-v", "error", "-i", str(source), "-map", "0:v:0", "-vf", frame_filter, "-vsync", "0", "-start_number", "0", str(decode_dir / "frame-%08d.png")]
        try:
            subprocess.run(command, cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
        except (OSError, subprocess.SubprocessError) as error:
            raise ValueError("ffmpeg frame extraction failed") from error
        records = []
        for order, source_index in enumerate(indices):
            decoded_index = order if automatic_review is not None else source_index
            decoded = decode_dir / f"frame-{decoded_index:08d}.png"
            if not decoded.is_file():
                raise ValueError(f"selected frame index is unavailable: {source_index}")
            target_name = f"{prefix}-frame-{order:04d}.png"
            target = root / target_name
            with Image.open(decoded) as opened:
                frame = opened.convert("RGBA")
            frame.save(target, format="PNG")
            records.append({
                "order": order,
                "source_index": source_index,
                "timestamp_seconds": source_index / fps,
                "file": target_name,
                "sha256": _sha256(target),
                "width": frame.width,
                "height": frame.height,
                "alpha": _alpha_details(frame),
            })
            frame.close()
        record = {
            "version": 1,
            "source": {"file": source.relative_to(root).as_posix(), "sha256": source_hash},
            "decode": {
                "tool": "ffmpeg", "filter": frame_filter, "stream": "0:v:0",
                "selection": "exact_sparse_native_frame_indices" if automatic_review is not None else "fps_resampled_indices",
                "selected_indices_only_published": True,
            },
            "frames": records,
            "automatic_selection": automatic_review is not None,
            "automatic_review_id": automatic_review["id"] if automatic_review is not None else None,
            "density_selection": (
                {
                    "receipt": automatic_review["density_receipt"],
                    "receipt_sha256": automatic_review["density_receipt_sha256"],
                    "policy_sha256": automatic_review["density_policy_sha256"],
                }
                if automatic_review is not None and "density_receipt" in automatic_review
                else None
            ),
            "visual_approval": False,
        }
        _atomic_json(root / "extract-frames.json", record)
        artifacts = [item["file"] for item in records] + ["extract-frames.json", "extract-frames-state.json"]
        result = _result("needs_review", artifacts, {"source_sha256": source_hash, "fps": fps, "selected_indices": indices, "frame_count": len(records), "visual_approval": False})
        output_hashes = {name: _sha256(root / name) for name in output_names}
        _atomic_json(root / "extract-frames-state.json", {"version": 1, "request": request, "output_hashes": output_hashes, "result": result})
        return result
    finally:
        shutil.rmtree(decode_dir, ignore_errors=True)


def _read_json_file(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is invalid") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _mirror(root: Path, params: dict[str, Any]) -> dict[str, Any]:
    if set(params) != {"atlas", "manifest", "target_direction", "target_image_id"}:
        raise ValueError("mirror params do not match the documented schema")
    atlas_path = _safe_path(root, params["atlas"], suffixes={".png"})
    manifest_path = _safe_path(root, params["manifest"], suffixes={".json"})
    target_direction = _identifier(params["target_direction"], "target_direction")
    target_image_id = _identifier(params["target_image_id"], "target_image_id")
    manifest = _read_json_file(manifest_path, "atlas manifest")
    if manifest.get("schema") != "animation-pipeline-atlas-v1" or not isinstance(manifest.get("frames"), list) or not manifest["frames"]:
        raise ValueError("mirror requires animation-pipeline-atlas-v1 input")
    if manifest.get("image", {}).get("sha256") != _sha256(atlas_path):
        raise ValueError("source atlas hash does not match manifest")
    request = {"stage": "mirror", "params": params, "atlas_sha256": _sha256(atlas_path), "manifest_sha256": _sha256(manifest_path)}
    output_names = ["mirror-atlas.png", "mirror-manifest.json"]
    cached = _verify_cached(root, "mirror-state.json", request, output_names)
    if cached is not None:
        return cached
    try:
        with Image.open(atlas_path) as opened:
            source_atlas = opened.convert("RGBA")
    except OSError as error:
        raise ValueError("source atlas is invalid") from error
    target_atlas = source_atlas.copy()
    target_frames = []
    try:
        action = _identifier(manifest.get("clip", {}).get("action"), "source action")
        source_direction = _identifier(manifest.get("clip", {}).get("direction"), "source direction")
        for order, frame in enumerate(manifest["frames"]):
            rect = frame.get("rect")
            if not isinstance(rect, dict) or set(rect) != {"x", "y", "width", "height"} or any(type(rect[key]) is not int for key in rect):
                raise ValueError("source frame rectangle is invalid")
            x, y, width, height = rect["x"], rect["y"], rect["width"], rect["height"]
            if x < 0 or y < 0 or width < 1 or height < 1 or x + width > source_atlas.width or y + height > source_atlas.height:
                raise ValueError("source frame rectangle leaves atlas")
            source_frame = source_atlas.crop((x, y, x + width, y + height))
            mirrored = source_frame.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            target_atlas.paste(mirrored, (x, y))
            source_anchor = frame.get("anchor")
            if not isinstance(source_anchor, dict) or set(source_anchor) != {"x", "y"}:
                raise ValueError("source frame anchor is invalid")
            target_anchor = {"x": 1 - _number(source_anchor["x"], "source anchor.x", 0, 1), "y": _number(source_anchor["y"], "source anchor.y", 0, 1)}
            target_frames.append({
                "id": f"{target_image_id}.{action}.{target_direction}.{order:04d}",
                "order": order,
                "rect": dict(rect),
                "anchor": target_anchor,
                "source_frame_id": frame.get("id"),
                "source_rgba_sha256": hashlib.sha256(source_frame.tobytes()).hexdigest(),
                "derived_rgba_sha256": hashlib.sha256(mirrored.tobytes()).hexdigest(),
                "transform": "exact horizontal RGBA mirror; no resampling",
            })
            source_frame.close()
            mirrored.close()
        target_atlas.save(root / "mirror-atlas.png", format="PNG")
    finally:
        source_atlas.close()
        target_atlas.close()
    target_ids = [item["id"] for item in target_frames]
    derived = {
        "schema": "animation-pipeline-atlas-v1-derived-mirror",
        "version": 1,
        "derivation_status": "DERIVED_NOT_PROVIDER_GENERATED",
        "warning": "Horizontal mirroring changes the screen side of handed props such as lanterns; visual approval remains required.",
        "certification": {"stock_framework_v4_claimed": False},
        "source": {"atlas": params["atlas"], "atlas_sha256": request["atlas_sha256"], "manifest": params["manifest"], "manifest_sha256": request["manifest_sha256"], "direction": source_direction},
        "image": {"id": target_image_id, "file": "mirror-atlas.png", "sha256": _sha256(root / "mirror-atlas.png"), "width": manifest["image"]["width"], "height": manifest["image"]["height"]},
        "clip": {"id": f"{target_image_id}.{action}.{target_direction}", "action": action, "direction": target_direction, "fps": manifest["clip"]["fps"], "loop": manifest["clip"]["loop"], "frames": target_ids},
        "frames": target_frames,
    }
    _atomic_json(root / "mirror-manifest.json", derived)
    result = _result("needs_review", ["mirror-atlas.png", "mirror-manifest.json", "mirror-state.json"], {"derivation_status": "DERIVED_NOT_PROVIDER_GENERATED", "frame_count": len(target_frames), "atlas_sha256": _sha256(root / "mirror-atlas.png"), "manifest_sha256": _sha256(root / "mirror-manifest.json"), "visual_approval": False})
    output_hashes = {name: _sha256(root / name) for name in output_names}
    _atomic_json(root / "mirror-state.json", {"version": 1, "request": request, "output_hashes": output_hashes, "result": result})
    return result


def _authorized_budget(params: dict[str, Any], quoted_usd: float) -> None:
    budget = params.get("budget")
    if not isinstance(budget, dict) or set(budget) != {"authorized", "max_usd"} or budget.get("authorized") is not True:
        raise ValueError("paid stage requires an explicit authorized budget")
    maximum = _number(budget.get("max_usd"), "budget.max_usd", 0, 10000)
    if maximum + 1e-12 < quoted_usd:
        raise ValueError("authorized budget is below the recorded quote")


def _provider_for(name: str) -> Any:
    if name != "wavespeed":
        raise ValueError("provider adapter is not configured")
    key = os.environ.get("WAVESPEED_API_KEY")
    if not key:
        raise ValueError("configured provider credential is unavailable")
    return provider.WaveSpeedProvider(key)


def _finish_paid_single(root: Path, state_path: Path, state: dict[str, Any], adapter: Any, output_name: str, suffixes: set[str]) -> dict[str, Any]:
    prediction_id = state.get("prediction_id")
    if not isinstance(prediction_id, str):
        raise ValueError("paid stage has no safe prediction ID")
    poll_started = time.monotonic()
    poll_started_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    readback = adapter.poll(prediction_id)
    state.setdefault("timings", []).append({
        "phase": "poll", "started_utc": poll_started_utc,
        "finished_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "duration_seconds": round(time.monotonic() - poll_started, 6),
    })
    state["last_readback"] = readback
    status = readback.get("status")
    if status in {"created", "pending", "processing", "queued"}:
        result = _result("needs_attention", [state_path.name], {"prediction_id": prediction_id, "submission_status": "known_prediction_pending", "safe_resume": True})
        state["result"] = result
        state["submission_status"] = "known_prediction_pending"
        _atomic_json(state_path, state)
        return result
    if status != "completed":
        state["submission_status"] = "provider_failed"
        _atomic_json(state_path, state)
        raise ValueError("provider prediction failed")
    outputs = readback.get("outputs")
    if not isinstance(outputs, list) or len(outputs) != 1:
        state["submission_status"] = "invalid_completed_output"
        _atomic_json(state_path, state)
        raise ValueError("provider completed without exactly one output")
    target = root / output_name
    download_started = time.monotonic()
    download_started_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    adapter.download(outputs[0], target)
    state.setdefault("timings", []).append({
        "phase": "download", "started_utc": download_started_utc,
        "finished_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "duration_seconds": round(time.monotonic() - download_started, 6),
    })
    _safe_path(root, output_name, suffixes=suffixes)
    state["submission_status"] = "completed"
    state["output"] = {"file": output_name, "sha256": _sha256(target), "bytes": target.stat().st_size}
    details = {
        "provider": state["provider"], "model": state["model"], "preset": state["preset"], "preset_revision": state["preset_revision"],
        "prediction_id": prediction_id, "quote": state["quote"], "actual_charge_usd": None, "actual_charge_known": False,
        "output_sha256": state["output"]["sha256"], "visual_approval": False,
    }
    result = _result("needs_review", [output_name, state_path.name], details)
    state["result"] = result
    _atomic_json(state_path, state)
    return result


def _paid_single(root: Path, stage: str, params: dict[str, Any]) -> dict[str, Any]:
    if stage == "generate_facing":
        allowed = {"input", "prompt", "aspect_ratio", "output_format", "budget", "preset"}
        capability, default_preset, output_name, suffixes = "image_edit", "waldlicht-facing-v1", "facing-output.png", {".png"}
    else:
        allowed = {"input", "prompt", "negative_prompt", "duration", "seed", "resolution", "aspect_ratio", "budget", "preset"}
        capability, default_preset, output_name, suffixes = "image_to_video", "waldlicht-video-v1", "video-output.mp4", {".mp4"}
    if not set(params) <= allowed or not {"input", "prompt", "budget"} <= set(params):
        raise ValueError(f"{stage} params do not match the documented schema")
    source = _safe_path(root, params["input"], suffixes={".png", ".jpg", ".jpeg", ".webp"})
    preset = provider.get_preset(params.get("preset", default_preset), capability)
    options = {key: value for key, value in params.items() if key not in {"input", "budget", "preset"}}
    preset.build_payload(options, ["https://validation.invalid/job-owned-input"])
    quote = preset.quote(options)
    _authorized_budget(params, quote["quoted_usd"])
    request = {"stage": stage, "params": params, "input_sha256": _sha256(source), "preset": preset.name, "model": preset.model, "schema": provider.MODEL_SCHEMAS[preset.model]}
    state_path = root / f"{stage.replace('_', '-')}-state.json"
    if state_path.exists():
        state = _read_json_file(state_path, "paid stage state")
        if state.get("request") != request:
            raise ValueError("existing paid stage state conflicts with this request or source")
        if state.get("submission_status") == "submission_unknown":
            return state["result"]
        if state.get("submission_status") == "completed":
            output = state.get("output", {})
            target = _safe_path(root, output.get("file"), suffixes=suffixes)
            if _sha256(target) != output.get("sha256"):
                raise ValueError("cached provider output hash mismatch")
            return state["result"]
        adapter = _provider_for(preset.provider)
        return _finish_paid_single(root, state_path, state, adapter, output_name, suffixes)
    adapter = _provider_for(preset.provider)
    upload_started = time.monotonic()
    upload_started_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    uploaded_url = adapter.upload(source)
    upload_timing = {
        "phase": "upload", "started_utc": upload_started_utc,
        "finished_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "duration_seconds": round(time.monotonic() - upload_started, 6),
    }
    payload = preset.build_payload(options, [uploaded_url])
    state = {
        "version": 1, "request": request, "provider": preset.provider, "model": preset.model, "preset": preset.name,
        "preset_revision": preset.revision, "actual_request_schema": provider.MODEL_SCHEMAS[preset.model], "provider_request": payload,
        "quote": quote, "submission_status": "ready_to_submit", "prediction_id": None,
        "timings": [upload_timing],
    }
    _atomic_json(state_path, state)
    try:
        submit_started = time.monotonic()
        submit_started_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        submission = adapter.submit(preset.model, payload)
        state["timings"].append({
            "phase": "submit", "started_utc": submit_started_utc,
            "finished_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "duration_seconds": round(time.monotonic() - submit_started, 6),
        })
    except provider.AmbiguousSubmission:
        result = _result("needs_attention", [state_path.name], {"provider": preset.provider, "model": preset.model, "preset": preset.name, "quote": quote, "submission_status": "submission_unknown", "safe_to_resubmit": False})
        state["submission_status"] = "submission_unknown"
        state["result"] = result
        _atomic_json(state_path, state)
        return result
    prediction_id = submission.get("id")
    if not isinstance(prediction_id, str):
        raise ValueError("provider submission returned no prediction ID")
    state["prediction_id"] = prediction_id
    state["submission_status"] = "known_prediction"
    state["submission_response"] = submission
    _atomic_json(state_path, state)
    return _finish_paid_single(root, state_path, state, adapter, output_name, suffixes)


def _removal_maximum_inflight() -> int:
    try:
        maximum = int(os.environ.get("ANIMATION_REMOVAL_MAX_INFLIGHT", "5"))
    except ValueError as error:
        raise ValueError("ANIMATION_REMOVAL_MAX_INFLIGHT must be an integer") from error
    if not 1 <= maximum <= 5:
        raise ValueError("ANIMATION_REMOVAL_MAX_INFLIGHT must be between 1 and 5")
    return maximum


def _remove_background(root: Path, params: dict[str, Any]) -> dict[str, Any]:
    if not set(params) <= {"inputs", "budget", "preset"} or not {"inputs", "budget"} <= set(params):
        raise ValueError("remove_background params do not match the documented schema")
    inputs = params["inputs"]
    if not isinstance(inputs, list) or not 1 <= len(inputs) <= 128 or len(set(inputs)) != len(inputs):
        raise ValueError("inputs must be 1..128 unique PNG files")
    sources = [_safe_path(root, item, suffixes={".png"}) for item in inputs]
    preset = provider.get_preset(params.get("preset", "waldlicht-removal-v1"), "background_removal")
    quote = provider.recorded_quote(preset.model, units=len(sources))
    _authorized_budget(params, quote["quoted_usd"])
    request = {
        "stage": "remove_background", "params": params, "preset": preset.name, "model": preset.model,
        "schema": provider.MODEL_SCHEMAS[preset.model],
        "input_sha256": {path.relative_to(root).as_posix(): _sha256(path) for path in sources},
    }
    state_path = root / "remove-background-state.json"
    if state_path.exists():
        state = _read_json_file(state_path, "remove background state")
        if state.get("request") != request:
            raise ValueError("existing remove background state conflicts with this request or source")
        interrupted = [item for item in state.get("items", []) if item.get("status") == "ready_to_submit"]
        if interrupted:
            for item in interrupted:
                item["status"] = "submission_unknown"
            result = _result("needs_attention", [state_path.name], {
                "provider": preset.provider, "model": preset.model, "preset": preset.name, "quote": quote,
                "ambiguous_orders": [item["order"] for item in interrupted],
                "submission_status": "submission_unknown_after_interrupted_submit", "safe_to_resubmit": False,
            })
            state["status"] = "needs_attention"
            state["result"] = result
            _atomic_json(state_path, state)
            return result
        if any(item.get("status") == "submission_unknown" for item in state.get("items", [])):
            return state["result"]
        if state.get("status") == "completed":
            for item in state["items"]:
                target = _safe_path(root, item.get("output", {}).get("file"), suffixes={".png"})
                if _sha256(target) != item["output"].get("sha256"):
                    raise ValueError("cached remover output hash mismatch")
            return state["result"]
    else:
        state = {
            "version": 1, "request": request, "provider": preset.provider, "model": preset.model, "preset": preset.name,
            "preset_revision": preset.revision, "actual_request_schema": provider.MODEL_SCHEMAS[preset.model], "quote": quote,
            "status": "processing", "items": [
                {"order": order, "input": source.relative_to(root).as_posix(), "input_sha256": _sha256(source), "status": "not_submitted"}
                for order, source in enumerate(sources)
            ],
        }
        _atomic_json(state_path, state)
    maximum_inflight = _removal_maximum_inflight()
    if any(item.get("status") == "provider_failed" for item in state.get("items", [])):
        raise ValueError("remove background batch has a previous provider failure")
    state["maximum_inflight"] = maximum_inflight
    state.setdefault("observed_maximum_inflight", sum(item["status"] == "known_prediction" for item in state["items"]))
    state.setdefault("timings", [])
    adapter = _provider_for(preset.provider)

    def measured(item: dict[str, Any], phase: str, operation: Any) -> Any:
        started = time.monotonic()
        started_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        try:
            return operation()
        finally:
            state["timings"].append({
                "order": item["order"], "phase": phase, "started_utc": started_utc,
                "finished_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "duration_seconds": round(time.monotonic() - started, 6),
            })

    def finish_download(item: dict[str, Any]) -> None:
        output_name = f"cutout-frame-{item['order']:04d}.png"
        target = root / output_name
        validation_started = time.monotonic()
        validation_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        try:
            try:
                with Image.open(target) as opened:
                    if opened.format != "PNG":
                        raise ValueError("remover output is not PNG")
                    rgba = opened.convert("RGBA")
            except OSError as error:
                raise ValueError("remover output is not a valid PNG") from error
            alpha = _alpha_details(rgba)
            width, height = rgba.size
            rgba.close()
            if not alpha["has_true_alpha"]:
                raise ValueError("remover output has no non-empty true alpha")
            item["status"] = "completed"
            item["output"] = {"file": output_name, "sha256": _sha256(target), "bytes": target.stat().st_size, "width": width, "height": height, "alpha": alpha}
        finally:
            state["timings"].append({
                "order": item["order"], "phase": "normalize_verify", "started_utc": validation_utc,
                "finished_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "duration_seconds": round(time.monotonic() - validation_started, 6),
            })
        _atomic_json(state_path, state)

    def parallel_network(items: list[dict[str, Any]], phase: str, operation: Any) -> dict[int, Any]:
        """Run only independent network I/O in workers; the caller owns state."""
        if not items:
            return {}
        outcomes: dict[int, Any] = {}
        errors: dict[int, BaseException] = {}

        def timed(item: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
            started = time.monotonic()
            started_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            try:
                return operation(item), {
                    "order": item["order"], "phase": phase, "started_utc": started_utc,
                    "finished_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "duration_seconds": round(time.monotonic() - started, 6),
                }
            except BaseException as error:
                error._animation_timing = {  # type: ignore[attr-defined]
                    "order": item["order"], "phase": phase, "started_utc": started_utc,
                    "finished_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "duration_seconds": round(time.monotonic() - started, 6),
                }
                raise

        with ThreadPoolExecutor(max_workers=min(maximum_inflight, len(items)), thread_name_prefix=f"removal-{phase}") as executor:
            futures = {executor.submit(timed, item): item for item in items}
            for future in as_completed(futures):
                item = futures[future]
                try:
                    value, timing = future.result()
                    outcomes[item["order"]] = value
                    state["timings"].append(timing)
                except BaseException as error:
                    timing = getattr(error, "_animation_timing", None)
                    if isinstance(timing, dict):
                        state["timings"].append(timing)
                    errors[item["order"]] = error
        if errors:
            _atomic_json(state_path, state)
            raise errors[min(errors)]
        return outcomes

    def reconcile_known(items: list[dict[str, Any]]) -> None:
        readbacks = parallel_network(items, "poll", lambda item: adapter.poll(item["prediction_id"]))
        downloadable: list[dict[str, Any]] = []
        for item in sorted(items, key=lambda value: value["order"]):
            readback = readbacks[item["order"]]
            item["last_readback"] = readback
            status = readback.get("status")
            if status in {"created", "pending", "processing", "queued"}:
                continue
            outputs = readback.get("outputs")
            if status != "completed" or not isinstance(outputs, list) or len(outputs) != 1:
                item["status"] = "provider_failed"
                state["status"] = "failed"
                _atomic_json(state_path, state)
                raise ValueError("remover prediction failed or returned invalid outputs")
            item["completed_output_url"] = outputs[0]
            downloadable.append(item)
        _atomic_json(state_path, state)
        downloads = parallel_network(
            downloadable,
            "download",
            lambda item: adapter.download(item["completed_output_url"], root / f"cutout-frame-{item['order']:04d}.png"),
        )
        for item in sorted(downloadable, key=lambda value: value["order"]):
            if item["order"] in downloads:
                item.pop("completed_output_url", None)
                finish_download(item)

    # Always reconcile immutable known IDs first. Pending IDs consume slots and
    # are never replaced by fresh submissions.
    known = [item for item in state["items"] if item["status"] == "known_prediction"]
    reconcile_known(known)

    inflight = sum(item["status"] == "known_prediction" for item in state["items"])
    known_ids = {item.get("prediction_id") for item in state["items"] if isinstance(item.get("prediction_id"), str)}
    available = maximum_inflight - inflight
    upload_items = [item for item in state["items"] if item["status"] == "not_submitted"][:available]
    uploads = parallel_network(upload_items, "upload", lambda item: adapter.upload(sources[item["order"]]))
    for item in sorted(upload_items, key=lambda value: value["order"]):
        uploaded_url = uploads[item["order"]]
        payload = preset.build_payload({}, [uploaded_url])
        item["provider_request"] = payload
        item["status"] = "uploaded"
        _atomic_json(state_path, state)

    submitted: list[dict[str, Any]] = []
    for item in state["items"]:
        if item["status"] != "uploaded" or inflight >= maximum_inflight:
            continue
        payload = item["provider_request"]
        item["status"] = "ready_to_submit"
        _atomic_json(state_path, state)
        try:
            submission = measured(item, "submit", lambda: adapter.submit(preset.model, payload))
        except provider.AmbiguousSubmission:
            item["status"] = "submission_unknown"
            result = _result("needs_attention", [state_path.name], {"provider": preset.provider, "model": preset.model, "preset": preset.name, "quote": quote, "ambiguous_order": item["order"], "submission_status": "submission_unknown", "safe_to_resubmit": False})
            state["status"] = "needs_attention"
            state["result"] = result
            _atomic_json(state_path, state)
            return result
        prediction_id = submission.get("id")
        if not isinstance(prediction_id, str) or prediction_id in known_ids:
            item["status"] = "submission_unknown"
            state["status"] = "needs_attention"
            result = _result("needs_attention", [state_path.name], {"provider": preset.provider, "model": preset.model, "preset": preset.name, "quote": quote, "ambiguous_order": item["order"], "submission_status": "invalid_or_duplicate_prediction_id", "safe_to_resubmit": False})
            state["result"] = result
            _atomic_json(state_path, state)
            return result
        known_ids.add(prediction_id)
        item["prediction_id"] = prediction_id
        item["submission_response"] = submission
        item["status"] = "known_prediction"
        inflight += 1
        state["observed_maximum_inflight"] = max(state["observed_maximum_inflight"], inflight)
        _atomic_json(state_path, state)
        submitted.append(item)

    reconcile_known(submitted)

    pending = [item["order"] for item in state["items"] if item["status"] == "known_prediction"]
    not_submitted = [item["order"] for item in state["items"] if item["status"] == "not_submitted"]
    if pending or not_submitted:
        result = _result("needs_attention", [state_path.name], {
            "provider": preset.provider, "model": preset.model, "preset": preset.name, "quote": quote,
            "submission_status": "known_predictions_pending", "safe_resume": True,
            "inflight": len(pending), "pending_orders": pending, "not_submitted_orders": not_submitted,
            "maximum_inflight": maximum_inflight,
            "observed_maximum_inflight": state["observed_maximum_inflight"],
        })
        state["status"] = "needs_attention"
        state["result"] = result
        _atomic_json(state_path, state)
        return result
    frames = [item["output"] for item in state["items"]]
    details = {"provider": preset.provider, "model": preset.model, "preset": preset.name, "preset_revision": preset.revision, "quote": quote, "actual_charge_usd": None, "actual_charge_known": False, "frames": frames, "maximum_inflight": maximum_inflight, "observed_maximum_inflight": state["observed_maximum_inflight"], "visual_approval": False}
    result = _result("needs_review", [item["file"] for item in frames] + [state_path.name], details)
    state["status"] = "completed"
    state["result"] = result
    _atomic_json(state_path, state)
    return result


def run_stage(stage: str, workdir: Path, params: dict[str, Any]) -> dict[str, Any]:
    """Run one validated stage entirely inside workdir."""
    if not isinstance(stage, str) or not isinstance(params, dict):
        raise ValueError("stage must be a string and params must be an object")
    root = _workdir(workdir)
    if stage == "inspect_reference":
        return _inspect_reference(root, params)
    if stage == "pack":
        return _pack(root, params)
    if stage == "extract_frames":
        return _extract_frames(root, params)
    if stage == "mirror":
        return _mirror(root, params)
    if stage in {"generate_facing", "generate_video"}:
        return _paid_single(root, stage, params)
    if stage == "remove_background":
        return _remove_background(root, params)
    if stage == "spatial_export":
        import spatial_export
        return spatial_export.run_service_stage(root, params)
    raise ValueError(f"unsupported stage: {stage}")
