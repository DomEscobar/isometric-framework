"""Reusable, deterministic spatial export with verified cutout caching.

This private runner intentionally distinguishes explicit human-reviewed indices from
automatic selection. It performs no provider submission and never treats file
existence alone as a cache hit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterator

from PIL import Image

import pipeline
import quality_gates

CACHE_SCHEMA = "animation-cutout-cache-v1"
EXPORT_SCHEMA = "animation-pipeline-atlas-v1"
BG = {"light": (238, 239, 234), "dark": (25, 29, 34), "petrol": (18, 68, 72)}
SERVICE_SPATIAL_PRESETS = {
    "accepted-native-160-80-v1": {
        "geometry": {"source_root": [395.5, 652.0]},
        "variants": [
            {"canvas": 160, "scale": 0.22524271844660193, "target_root": [80, 144]},
            {"canvas": 80, "scale": 0.11262135922330097, "target_root": [40, 72]},
        ],
    },
    "derived-native-160-80-v1": {
        "derive_geometry": True,
        "variants": [
            {"canvas": 160, "target_visible_height": 116, "target_root": [80, 144]},
            {"canvas": 80, "target_visible_height": 58, "target_root": [40, 72]},
        ],
    },
    "derived-native-160-v1": {
        "derive_geometry": True,
        "variants": [{"canvas": 160, "target_visible_height": 116, "target_root": [80, 144]}],
    },
    "derived-native-80-v1": {
        "derive_geometry": True,
        "variants": [{"canvas": 80, "target_visible_height": 58, "target_root": [40, 72]}],
    },
}


def utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(value, output, indent=2, sort_keys=True, allow_nan=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_name, path)
    finally:
        Path(temporary_name).unlink(missing_ok=True)


def cache_key(input_sha256: str, provider_preset: str, removal_recipe: str) -> str:
    if len(input_sha256) != 64 or not provider_preset or not removal_recipe:
        raise ValueError("invalid cutout cache identity")
    return hashlib.sha256(_canonical({
        "input_sha256": input_sha256,
        "provider_preset": provider_preset,
        "removal_recipe": removal_recipe,
    })).hexdigest()


def import_cached_cutout(source: Path, master: Path, cache_dir: Path, provider_preset: str, removal_recipe: str) -> dict[str, Any]:
    source, master, cache_dir = Path(source), Path(master), Path(cache_dir)
    if not source.is_file() or source.is_symlink() or not master.is_file() or master.is_symlink():
        raise ValueError("cache import requires regular source and master files")
    source_hash = sha256(source)
    master_hash = sha256(master)
    key = cache_key(source_hash, provider_preset, removal_recipe)
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"{key}.png"
    receipt_path = cache_dir / f"{key}.json"
    receipt = {
        "schema": CACHE_SCHEMA,
        "key": key,
        "input_sha256": source_hash,
        "provider_preset": provider_preset,
        "removal_recipe": removal_recipe,
        "output_file": target.name,
        "output_sha256": master_hash,
        "imported_from": {"file": master.name, "sha256": master_hash},
    }
    if target.exists() or receipt_path.exists():
        if not target.is_file() or not receipt_path.is_file():
            raise ValueError("incomplete cutout cache entry")
        try:
            existing = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("cutout cache receipt is invalid") from error
        if existing != receipt or sha256(target) != master_hash:
            raise ValueError("cache output hash mismatch")
        return {"key": key, "path": target, "receipt": receipt_path, "imported": False}
    temporary = cache_dir / f".{key}.{os.getpid()}.tmp"
    shutil.copyfile(master, temporary)
    if sha256(temporary) != master_hash:
        temporary.unlink(missing_ok=True)
        raise ValueError("cache import copy hash mismatch")
    os.replace(temporary, target)
    target.chmod(0o444)
    _atomic_json(receipt_path, receipt)
    receipt_path.chmod(0o444)
    return {"key": key, "path": target, "receipt": receipt_path, "imported": True}


def lookup_cached_cutout(source: Path, cache_dir: Path, provider_preset: str, removal_recipe: str) -> Path | None:
    source, cache_dir = Path(source), Path(cache_dir)
    key = cache_key(sha256(source), provider_preset, removal_recipe)
    target, receipt_path = cache_dir / f"{key}.png", cache_dir / f"{key}.json"
    if not target.exists() and not receipt_path.exists():
        return None
    if not target.is_file() or target.is_symlink() or not receipt_path.is_file() or receipt_path.is_symlink():
        raise ValueError("incomplete cutout cache entry")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("cutout cache receipt is invalid") from error
    expected = {
        "schema": CACHE_SCHEMA,
        "key": key,
        "input_sha256": sha256(source),
        "provider_preset": provider_preset,
        "removal_recipe": removal_recipe,
        "output_file": target.name,
    }
    if any(receipt.get(name) != value for name, value in expected.items()):
        raise ValueError("cutout cache receipt identity mismatch")
    if sha256(target) != receipt.get("output_sha256"):
        raise ValueError("cache output hash mismatch")
    return target


def ingest_completed_removal_batch(
    workdir: Path,
    cache_dir: Path,
    provider_preset: str,
    removal_recipe: str,
) -> dict[str, Any]:
    """Verify a completed remover state and ingest its exact input/output pairs."""
    root = Path(workdir).resolve(strict=True)
    state_path = root / "remove-background-state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("completed remover state is unavailable") from error
    if state.get("status") != "completed" or state.get("preset") != provider_preset:
        raise ValueError("remover state is not a completed matching batch")
    items = state.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("completed remover state contains no items")
    records = []
    for expected_order, item in enumerate(items):
        if item.get("order") != expected_order or item.get("status") != "completed":
            raise ValueError("remover item order/status is invalid")
        source = pipeline._safe_path(root, item.get("input"), suffixes={".png"})
        output_record = item.get("output")
        if not isinstance(output_record, dict):
            raise ValueError("remover item output receipt is absent")
        master = pipeline._safe_path(root, output_record.get("file"), suffixes={".png"})
        if sha256(source) != item.get("input_sha256") or sha256(master) != output_record.get("sha256"):
            raise ValueError("remover input/output hash does not match its receipt")
        prediction_id = item.get("prediction_id")
        if not isinstance(prediction_id, str) or not prediction_id:
            raise ValueError("completed remover item lacks a prediction ID")
        imported = import_cached_cutout(source, master, cache_dir, provider_preset, removal_recipe)
        records.append({
            "order": expected_order,
            "input": source.name,
            "input_sha256": item["input_sha256"],
            "output": master.name,
            "output_sha256": output_record["sha256"],
            "prediction_id": prediction_id,
            "cache_key": imported["key"],
            "cache_receipt_sha256": sha256(imported["receipt"]),
            "new_cache_entry": imported["imported"],
        })
    receipt = {
        "schema": "animation-cutout-cache-ingest-v1",
        "provider": state.get("provider"),
        "model": state.get("model"),
        "provider_preset": provider_preset,
        "preset_revision": state.get("preset_revision"),
        "removal_recipe": removal_recipe,
        "remover_state": {"file": state_path.name, "sha256": sha256(state_path)},
        "items": records,
    }
    receipt_path = root / "cutout-cache-ingest.json"
    _atomic_json(receipt_path, receipt)
    return {"receipt": receipt_path.name, "receipt_sha256": sha256(receipt_path), "items": records}


def derive_shared_geometry(masters: list[Path], variants: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive one root and one scale per output size from the whole cutout batch."""
    if not masters:
        raise ValueError("cannot derive geometry from an empty cutout batch")
    centroids: list[float] = []
    bottoms: list[float] = []
    heights: list[int] = []
    alpha_bounds: list[tuple[int, int, int, int]] = []
    dimensions: set[tuple[int, int]] = set()
    for path in masters:
        with Image.open(path) as opened:
            rgba = opened.convert("RGBA")
        alpha = rgba.getchannel("A")
        bounds = alpha.getbbox()
        if bounds is None:
            rgba.close(); alpha.close()
            raise ValueError("cannot derive geometry from a blank cutout")
        values = list(alpha.get_flattened_data())
        total = sum(values)
        if total <= 0:
            rgba.close(); alpha.close()
            raise ValueError("cannot derive geometry from empty alpha")
        width, height = rgba.size
        centroids.append(sum((index % width) * opacity for index, opacity in enumerate(values)) / total)
        bottoms.append(float(bounds[3] - 1))
        heights.append(bounds[3] - bounds[1])
        alpha_bounds.append(bounds)
        dimensions.add((width, height))
        rgba.close(); alpha.close()
    if len(dimensions) != 1:
        raise ValueError("cutout dimensions differ across the selected cycle")
    source_root = [median(centroids), median(bottoms)]
    median_height = float(median(heights))
    left_extent = max(source_root[0] - bounds[0] for bounds in alpha_bounds)
    right_extent = max((bounds[2] - 1) - source_root[0] for bounds in alpha_bounds)
    top_extent = max(source_root[1] - bounds[1] for bounds in alpha_bounds)
    bottom_extent = max((bounds[3] - 1) - source_root[1] for bounds in alpha_bounds)
    derived_variants = []
    for variant in variants:
        target_height = int(variant["target_visible_height"])
        canvas = int(variant["canvas"])
        target_root = list(variant["target_root"])
        desired_scale = target_height / median_height
        fit_limits = [desired_scale]
        for pixels, extent in (
            (target_root[0] - 2, left_extent),
            (canvas - 2 - target_root[0], right_extent),
            (target_root[1] - 2, top_extent),
            (canvas - 2 - target_root[1], bottom_extent),
        ):
            if extent > 0:
                fit_limits.append(max(0.0, pixels) / extent)
        scale = min(fit_limits)
        if scale <= 0:
            raise ValueError("shared action geometry cannot fit the target canvas")
        derived_variants.append({
            "canvas": canvas,
            "scale": scale,
            "target_root": target_root,
        })
    return {
        "geometry": {"source_root": source_root},
        "variants": derived_variants,
        "evidence": {
            "method": "median_alpha_weighted_x_centroid_and_visible_bottom; scale_from_median_visible_height",
            "source_dimensions": list(next(iter(dimensions))),
            "median_visible_height": median_height,
            "frame_count": len(masters),
            "fit_extents_from_shared_root": {
                "left": left_extent, "right": right_extent, "top": top_extent, "bottom": bottom_extent,
            },
            "scale_limited_by_batch_bounds": any(
                variant["scale"] + 1e-12 < source["target_visible_height"] / median_height
                for variant, source in zip(derived_variants, variants)
            ),
        },
    }


def _prepare_master(source: Image.Image) -> tuple[tuple[int, int], Image.Image, list[Image.Image]]:
    """Decode and integer-premultiply one master for reuse across output sizes."""
    rgba = source.convert("RGBA")
    red, green, blue, alpha = rgba.split()
    premult = [Image.new("L", rgba.size), Image.new("L", rgba.size), Image.new("L", rgba.size)]
    for target, channel in zip(premult, (red, green, blue)):
        target.putdata([(color * opacity + 127) // 255 for color, opacity in zip(channel.get_flattened_data(), alpha.get_flattened_data())])
    size = rgba.size
    for image in [rgba, red, green, blue]:
        image.close()
    return size, alpha, premult


def _close_prepared_master(prepared: tuple[tuple[int, int], Image.Image, list[Image.Image]]) -> None:
    _size, alpha, premult = prepared
    for image in [alpha, *premult]:
        image.close()


def _resize_prepared_master(
    prepared: tuple[tuple[int, int], Image.Image, list[Image.Image]],
    size: tuple[int, int],
) -> Image.Image:
    _source_size, alpha, premult = prepared
    resized_alpha = alpha.resize(size, Image.Resampling.LANCZOS)
    resized_premult = [channel.resize(size, Image.Resampling.LANCZOS) for channel in premult]
    alpha_values = list(resized_alpha.get_flattened_data())
    colors = [list(channel.get_flattened_data()) for channel in resized_premult]
    pixels = []
    for index, opacity in enumerate(alpha_values):
        if opacity == 0:
            pixels.append((0, 0, 0, 0))
        else:
            values = [min(255, (channel[index] * 255 + opacity // 2) // opacity) for channel in colors]
            pixels.append((values[0], values[1], values[2], opacity))
    result = Image.new("RGBA", size)
    result.putdata(pixels)
    for image in [resized_alpha, *resized_premult]:
        image.close()
    return result


def _premultiplied_resize(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    prepared = _prepare_master(source)
    try:
        return _resize_prepared_master(prepared, size)
    finally:
        _close_prepared_master(prepared)


def _normalize_prepared(
    prepared: tuple[tuple[int, int], Image.Image, list[Image.Image]],
    canvas: int,
    scale: float,
    source_root: list[float],
    target_root: list[int],
) -> tuple[Image.Image, dict[str, Any]]:
    source_size = prepared[0]
    scaled_size = (max(1, round(source_size[0] * scale)), max(1, round(source_size[1] * scale)))
    scaled = _resize_prepared_master(prepared, scaled_size)
    paste = (target_root[0] - round(source_root[0] * scale), target_root[1] - round(source_root[1] * scale))
    target = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    target.alpha_composite(scaled, paste)
    pixels = list(target.get_flattened_data())
    cleared = sum(1 for pixel in pixels if 0 < pixel[3] < 8)
    if cleared:
        target.putdata([(0, 0, 0, 0) if 0 < a < 8 else (r, g, b, a) for r, g, b, a in pixels])
    bounds = target.getchannel("A").getbbox()
    scaled.close()
    if bounds is None or bounds[0] <= 0 or bounds[1] <= 0 or bounds[2] >= canvas or bounds[3] >= canvas:
        target.close()
        raise ValueError(f"normalized {canvas}px frame clips or touches edge")
    return target, {
        "scale": scale,
        "source_root": source_root,
        "target_root": target_root,
        "scaled_full_canvas": list(scaled_size),
        "paste_offset": list(paste),
        "alpha_1_7_pixels_cleared": cleared,
        "bounds": list(bounds),
    }


def _normalize(master: Path, canvas: int, scale: float, source_root: list[float], target_root: list[int]) -> tuple[Image.Image, dict[str, Any]]:
    with Image.open(master) as opened:
        prepared = _prepare_master(opened)
    try:
        return _normalize_prepared(prepared, canvas, scale, source_root, target_root)
    finally:
        _close_prepared_master(prepared)


def export_variants(masters: list[Path], output: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    indices = config["selected_indices"]
    if config.get("selection_mode") not in {"explicit_human_reviewed", "automatic_model_validated"}:
        raise ValueError("selection_mode must honestly identify explicit or validated automatic selection")
    if len(masters) != len(indices) or not masters:
        raise ValueError("master count must equal selected frame count")
    if indices != sorted(set(indices)) or config["cycle_end_exclusive"] <= indices[-1]:
        raise ValueError("selected indices or cycle bound are invalid")
    source_root = config["geometry"]["source_root"]
    duration = (config["cycle_end_exclusive"] - config["cycle_start"]) / float(config["native_fps"])
    playback_fps = len(indices) / duration
    frame_durations = config.get("frame_durations_seconds")
    if frame_durations is None:
        frame_durations = [duration / len(indices)] * len(indices)
    if (
        not isinstance(frame_durations, list) or len(frame_durations) != len(indices)
        or any(type(value) not in (int, float) or value <= 0 for value in frame_durations)
        or abs(sum(float(value) for value in frame_durations) - duration) > 1e-9
    ):
        raise ValueError("frame durations must be positive and conserve the selected interval")
    frame_durations = [float(value) for value in frame_durations]
    results = []
    prepare_utc, prepare_started = utc(), time.monotonic()
    prepared_masters = []
    try:
        for master in masters:
            with Image.open(master) as opened:
                prepared_masters.append(_prepare_master(opened))
        prepare_timing = {"stage": "prepare_masters", "started_utc": prepare_utc, "finished_utc": utc(), "duration_seconds": round(time.monotonic() - prepare_started, 6)}
        for variant_index, variant in enumerate(config["variants"]):
            canvas = int(variant["canvas"])
            scale = float(variant["scale"])
            target_root = list(variant["target_root"])
            frame_dir = output / f"export-{canvas}"
            frame_dir.mkdir(exist_ok=True)
            frames, records = [], []
            normalize_utc, normalize_started = utc(), time.monotonic()
            for order, (master, prepared) in enumerate(zip(masters, prepared_masters)):
                frame, transform = _normalize_prepared(prepared, canvas, scale, source_root, target_root)
                name = f"frame-{order:04d}.png"
                frame.save(frame_dir / name)
                frames.append(frame)
                records.append({
                    "id": f"{config['job_id']}.{config['action']}.{config['direction']}.{canvas}.{order:04d}",
                    "order": order,
                    "native_source_index": indices[order],
                    "timestamp_seconds": indices[order] / float(config["native_fps"]),
                    "duration_seconds": frame_durations[order],
                    "source_master": Path(master).name,
                    "source_master_sha256": sha256(Path(master)),
                    "file": name,
                    "sha256": sha256(frame_dir / name),
                    "rect": {},
                    "anchor": {"x": 0.5, "y": 0.9},
                    "transform": transform,
                })
            normalize_timing = {"stage": f"normalize_{canvas}", "started_utc": normalize_utc, "finished_utc": utc(), "duration_seconds": round(time.monotonic() - normalize_started, 6)}
            pack_utc, pack_started = utc(), time.monotonic()
            columns, gutter = 8, 2
            rows = (len(frames) + columns - 1) // columns
            atlas = Image.new("RGBA", (gutter + min(columns, len(frames)) * (canvas + gutter), gutter + rows * (canvas + gutter)), (0, 0, 0, 0))
            for order, frame in enumerate(frames):
                x = gutter + (order % columns) * (canvas + gutter)
                y = gutter + (order // columns) * (canvas + gutter)
                atlas.alpha_composite(frame, (x, y))
                records[order]["rect"] = {"x": x, "y": y, "width": canvas, "height": canvas}
            atlas_name = f"atlas-{canvas}.png"
            atlas.save(output / atlas_name)
            manifest = {
                "schema": EXPORT_SCHEMA,
                "version": 1,
                "source": config["source"],
                "selection": {
                    "mode": config["selection_mode"],
                    "indices": indices,
                    "cycle_start": config["cycle_start"],
                    "cycle_end_exclusive": config["cycle_end_exclusive"],
                    "receipt": config.get("selection_receipt"),
                    "frame_policy": config.get("frame_policy"),
                },
                "image": {"id": f"{config['job_id']}-{canvas}", "file": atlas_name, "sha256": sha256(output / atlas_name), "width": atlas.width, "height": atlas.height, "sampling": "premultiplied-alpha-lanczos"},
                "packing": {"columns": min(columns, len(frames)), "rows": rows, "gutter": gutter, "cell": {"width": canvas, "height": canvas}},
                "clip": {"id": f"{config['job_id']}.{config['action']}.{config['direction']}.{canvas}", "action": config["action"], "direction": config["direction"], "fps": playback_fps, "loop": bool(config.get("loop", True)), "duration_seconds": duration, "frame_durations_seconds": frame_durations, "timing": "source-intervals-v1", "frames": [record["id"] for record in records]},
                "display": {"native_css_pixels": [canvas, canvas], "allowed_sampling": "nearest-neighbour", "allowed_scale": "integer only", "fractional_css_scaling": False},
                "processing": {"full_resolution_masters_preserved": True, "direct_from_master": True, "upscaled_from_other_variant": False, "premultiplied_alpha_resample": True, "cleanup": {"alpha_min": 1, "alpha_max": 7, "component_removal": False}},
                "frames": records,
            }
            manifest_name = f"atlas-{canvas}-manifest.json"
            _atomic_json(output / manifest_name, manifest)
            for frame in frames:
                frame.close()
            atlas.close()
            pack_timing = {"stage": f"pack_{canvas}", "started_utc": pack_utc, "finished_utc": utc(), "duration_seconds": round(time.monotonic() - pack_started, 6)}
            timings = [normalize_timing, pack_timing]
            if variant_index == 0:
                timings.insert(0, prepare_timing)
            results.append({"canvas": canvas, "atlas": atlas_name, "manifest": manifest_name, "_timings": timings})
    finally:
        for prepared in prepared_masters:
            _close_prepared_master(prepared)
    return results


class Timings:
    def __init__(self) -> None:
        self.started_utc = utc()
        self.started = time.monotonic()
        self.stages: list[dict[str, Any]] = []

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        started_utc, started = utc(), time.monotonic()
        try:
            yield
        finally:
            self.stages.append({"stage": name, "started_utc": started_utc, "finished_utc": utc(), "duration_seconds": round(time.monotonic() - started, 6)})

    def record(self, artifact_ready: bool = False) -> dict[str, Any]:
        return {
            "schema": "animation-pipeline-timings-v1",
            "started_utc": self.started_utc,
            "finished_utc": utc(),
            "total_seconds": round(time.monotonic() - self.started, 6),
            "stages": self.stages,
            "artifact_ready": artifact_ready,
            "ci_included": False,
            "source_generation_included": False,
        }


def _encode_preview(
    output: Path, canvas: int, fps: float, frame_count: int, *, loop: bool = True,
    frame_durations_seconds: list[float] | None = None,
) -> str:
    source_dir = output / f"export-{canvas}"
    preview_dir = source_dir / "preview-petrol"
    preview_dir.mkdir(exist_ok=True)
    for order in range(frame_count):
        with Image.open(source_dir / f"frame-{order:04d}.png") as opened:
            sprite = opened.convert("RGBA")
        background = Image.new("RGBA", sprite.size, BG["petrol"] + (255,))
        background.alpha_composite(sprite)
        background.convert("RGB").save(preview_dir / f"frame-{order:04d}.png")
        sprite.close()
        background.close()
    name = f"preview-{canvas}-native-petrol-{'3loops' if loop else 'repeated-3x'}.mp4"
    durations = frame_durations_seconds or [1.0 / fps] * frame_count
    if len(durations) != frame_count or any(value <= 0 for value in durations):
        raise ValueError("preview frame durations are invalid")
    concat = preview_dir / "timed-preview.concat.txt"
    lines = []
    for _repeat in range(3):
        for order, duration in enumerate(durations):
            lines.extend((f"file 'frame-{order:04d}.png'", "option framerate 120", f"duration {duration:.12f}"))
    lines.extend((f"file 'frame-{frame_count - 1:04d}.png'", "option framerate 120"))
    concat.write_text("\n".join(lines) + "\n", encoding="utf-8")
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
        # Quantize presentation timestamps to 1/120 s, then hold the final
        # pose through the full manifest duration despite concat EOF handling.
        "-vf", "fps=120,tpad=stop_mode=clone:stop_duration=1",
        "-frames:v", str(round(sum(durations) * 3 * 120)),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-video_track_timescale", "24000",
        "-movflags", "+faststart", str(output / name),
    ], check=True, timeout=180)
    return name


def write_player(output: Path, canvas: int = 160) -> None:
    Path(output).mkdir(parents=True, exist_ok=True)
    (Path(output) / "preview.html").write_text(f"""<!doctype html>
<meta charset="utf-8"><link rel="icon" href="data:,"><title>Animation pipeline manifest player</title>
<style>body{{background:#124448;color:#fff;font:14px system-ui}}canvas{{width:{canvas}px;height:{canvas}px;image-rendering:pixelated}}</style>
<canvas id="player" width="{canvas}" height="{canvas}"></canvas>
<script>
window.__animationVerification={{loaded:false,textureDecoded:false,rectanglesInBounds:false,frameAdvanceCount:0,errors:[]}};
const state=window.__animationVerification;
Promise.all([
  fetch('atlas-{canvas}-manifest.json').then(r=>{{if(!r.ok)throw Error('manifest HTTP '+r.status);return r.json()}}),
  new Promise((resolve,reject)=>{{const image=new Image;image.onload=()=>resolve(image);image.onerror=()=>reject(Error('texture decode failed'));image.src='atlas-{canvas}.png'}})
]).then(([manifest,image])=>{{
  state.textureDecoded=image.naturalWidth>0&&image.naturalHeight>0;
  state.rectanglesInBounds=manifest.frames.every(frame=>{{const r=frame.rect;return r.x>=0&&r.y>=0&&r.width>0&&r.height>0&&r.x+r.width<=image.naturalWidth&&r.y+r.height<=image.naturalHeight}});
  if(!state.rectanglesInBounds)throw Error('manifest rectangle outside texture');
  const canvas=document.getElementById('player'),context=canvas.getContext('2d');context.imageSmoothingEnabled=false;
  const durations=(manifest.clip.frame_durations_seconds||manifest.frames.map(()=>1/manifest.clip.fps)).map(value=>value*1000);
  let frame=0,last=performance.now(),elapsed=0,ended=false;
  function draw(now){{
    elapsed+=now-last;last=now;
    while(!ended&&elapsed>=durations[frame]){{elapsed-=durations[frame];state.frameAdvanceCount++;
      if(frame===manifest.frames.length-1){{if(manifest.clip.loop)frame=0;else{{ended=true;elapsed=0}}}}else frame++;
    }}
    const r=manifest.frames[frame].rect;context.clearRect(0,0,canvas.width,canvas.height);context.drawImage(image,r.x,r.y,r.width,r.height,0,0,canvas.width,canvas.height);requestAnimationFrame(draw)
  }}
  state.loaded=true;requestAnimationFrame(draw);
}}).catch(error=>state.errors.push(String(error)));
window.addEventListener('error',event=>state.errors.push(String(event.error||event.message)));
</script>""", encoding="utf-8")


def _verify_all_frames(output: Path, variants: list[dict[str, Any]]) -> dict[str, Any]:
    records = []
    for variant in variants:
        manifest_path = output / variant["manifest"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        atlas_result = quality_gates.evaluate_atlas(output, variant["atlas"], variant["manifest"])
        if atlas_result["status"] != "passed":
            raise ValueError(f"atlas verification rejected {variant['canvas']}px output: {atlas_result['rejection_reasons']}")
        with Image.open(output / variant["atlas"]) as opened:
            atlas = opened.convert("RGBA")
        backgrounds: dict[str, str] = {}
        for background_name, color in BG.items():
            board = Image.new("RGB", (variant["canvas"] * len(manifest["frames"]), variant["canvas"]), color)
            for order, frame in enumerate(manifest["frames"]):
                rect = frame["rect"]
                sprite = atlas.crop((rect["x"], rect["y"], rect["x"] + rect["width"], rect["y"] + rect["height"]))
                if sprite.getchannel("A").getbbox() is None:
                    raise ValueError("blank atlas frame")
                rgba_background = Image.new("RGBA", sprite.size, color + (255,))
                rgba_background.alpha_composite(sprite)
                board.paste(rgba_background.convert("RGB"), (order * variant["canvas"], 0))
                sprite.close()
                rgba_background.close()
            name = f"all-frames-{variant['canvas']}-{background_name}.png"
            board.save(output / name)
            board.close()
            backgrounds[background_name] = sha256(output / name)
        atlas.close()
        records.append({"canvas": variant["canvas"], "gate": atlas_result, "background_evidence": backgrounds})
    return {"status": "passed", "variants": records, "visual_quality_certified": False}


def _service_selection(root: Path, source: Path, params: dict[str, Any]) -> tuple[dict[str, Any], list[Path]]:
    receipt_path = pipeline._safe_path(root, params["selection_receipt"], suffixes={".json"})
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("selection receipt is invalid") from error
    source_hash = sha256(source)
    mode = params["selection_mode"]
    if mode == "explicit_human_reviewed":
        if receipt.get("schema") != "animation-spatial-selection-v1" or receipt.get("mode") != mode:
            raise ValueError("selection provenance does not match explicit mode")
        if receipt.get("source", {}).get("file") != source.name or receipt.get("source", {}).get("sha256") != source_hash:
            raise ValueError("selection receipt source is stale")
        indices = receipt.get("selected_indices")
        native_fps = receipt.get("native_fps")
        cycle_start = receipt.get("cycle_start")
        cycle_end = receipt.get("cycle_end_exclusive")
        extraction = pipeline.run_stage("extract_frames", root, {
            "input": source.name, "fps": native_fps, "indices": indices, "output_prefix": "spatial",
        })
        if extraction["status"] != "needs_review":
            raise ValueError("selected-frame extraction did not complete")
        originals = [root / f"spatial-frame-{order:04d}.png" for order in range(len(indices))]
    elif mode == "automatic_model_validated":
        if receipt.get("status") != "approved" or receipt.get("approved") is not True or receipt.get("model") != "google/gemini-3.8-flash":
            raise ValueError("selection provenance does not contain a validated automatic approval")
        if receipt.get("source_sha256") != source_hash or not isinstance(receipt.get("selected_candidate"), dict):
            raise ValueError("automatic selection receipt source is stale")
        extraction_path = root / "extract-frames.json"
        analysis_path = root / "automatic-review-analysis.json"
        try:
            extraction_record = json.loads(extraction_path.read_text(encoding="utf-8"))
            analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("automatic selection extraction evidence is unavailable") from error
        if extraction_record.get("automatic_selection") is not True or extraction_record.get("source", {}).get("sha256") != source_hash:
            raise ValueError("automatic extraction provenance is invalid")
        density_binding = extraction_record.get("density_selection")
        if not isinstance(density_binding, dict):
            raise ValueError("automatic extraction lacks density policy provenance")
        density_path = pipeline._safe_path(root, density_binding.get("receipt"), suffixes={".json"})
        try:
            density_receipt = json.loads(density_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("density selection receipt is invalid") from error
        if (
            sha256(density_path) != density_binding.get("receipt_sha256")
            or density_receipt.get("schema") != "animation-selection-density-v1"
            or density_receipt.get("reviewer_receipt", {}).get("sha256") != sha256(receipt_path)
            or density_receipt.get("source", {}).get("sha256") != source_hash
        ):
            raise ValueError("density selection receipt provenance is stale")
        candidate = receipt["selected_candidate"]
        cycle_start = candidate.get("start_source_frame_index")
        cycle_end = candidate.get("end_source_frame_index")
        native_fps = analysis.get("source", {}).get("native_fps")
        frames = extraction_record.get("frames")
        if not isinstance(frames, list) or not frames:
            raise ValueError("automatic extraction contains no frames")
        indices = [frame.get("source_index") for frame in frames]
        if density_receipt.get("sampling", {}).get("indices") != indices:
            raise ValueError("automatic extraction indices do not match density receipt")
        frame_policy_receipt = density_receipt.get("policy")
        if not isinstance(frame_policy_receipt, dict) or density_binding.get("policy_sha256") != frame_policy_receipt.get("sha256"):
            raise ValueError("automatic extraction frame policy provenance is stale")
        originals = [pipeline._safe_path(root, frame.get("file"), suffixes={".png"}) for frame in frames]
    else:
        raise ValueError("selection provenance mode is unsupported")
    if (
        type(native_fps) not in (int, float) or native_fps <= 0
        or type(cycle_start) is not int or type(cycle_end) is not int or not 0 <= cycle_start < cycle_end
        or not isinstance(indices, list) or not indices or indices != sorted(set(indices))
        or any(type(index) is not int or not cycle_start <= index < cycle_end for index in indices)
    ):
        raise ValueError("selection receipt timeline is invalid")
    return {
        "native_fps": float(native_fps), "cycle_start": cycle_start, "cycle_end_exclusive": cycle_end,
        "selected_indices": indices, "selection_receipt": {"file": receipt_path.name, "sha256": sha256(receipt_path)},
        "frame_policy": frame_policy_receipt if mode == "automatic_model_validated" else None,
        "frame_durations_seconds": (
            density_receipt.get("sampling", {}).get("frame_durations_seconds")
            if mode == "automatic_model_validated" else None
        ),
        "action": density_receipt.get("action", "walk") if mode == "automatic_model_validated" else receipt.get("action", "walk"),
        "loop": density_receipt.get("loop", True) if mode == "automatic_model_validated" else receipt.get("loop", True),
    }, originals


def server_cutout_cache_dir(workdir: Path, *, create: bool = False) -> Path:
    """Resolve the private server cache, with a job-root default for zero-config API runs."""
    root = Path(workdir).resolve(strict=True)
    configured = os.environ.get("ANIMATION_CUTOUT_CACHE_DIR")
    cache = Path(configured).resolve() if configured else root.parent / ".cutout-cache"
    if cache.is_symlink():
        raise ValueError("server cutout cache is invalid")
    if create:
        cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    cache = cache.resolve(strict=True)
    if not cache.is_dir() or cache.is_symlink():
        raise ValueError("server cutout cache is invalid")
    return cache


def run_service_stage(workdir: Path, params: dict[str, Any]) -> dict[str, Any]:
    """Run the cache-backed final spatial path inside an authenticated API job."""
    required = {"source", "selection_receipt", "selection_mode", "export_preset", "removal_preset", "removal_recipe"}
    if set(params) != required:
        raise ValueError("spatial_export params do not match the documented schema")
    root = pipeline._workdir(workdir)
    source = pipeline._safe_path(root, params["source"], suffixes={".mp4", ".mov", ".webm", ".mkv"})
    preset = SERVICE_SPATIAL_PRESETS.get(params["export_preset"])
    if preset is None:
        raise ValueError("unknown server spatial export preset")
    if params["removal_preset"] != "waldlicht-removal-v1" or params["removal_recipe"] != "wavespeed-image-background-remover-output-v1":
        raise ValueError("unsupported server removal cache recipe")
    cache_dir = server_cutout_cache_dir(root)
    timing = Timings()
    try:
        with timing.stage("selection_and_extraction"):
            selection, originals = _service_selection(root, source, params)
        with timing.stage("cutout_cache_lookup"):
            masters = [lookup_cached_cutout(path, cache_dir, params["removal_preset"], params["removal_recipe"]) for path in originals]
            missing = [order for order, master in enumerate(masters) if master is None]
            if missing:
                raise ValueError(f"cutout cache miss for frame orders {missing}; run the separately budgeted remove_background stage")
            master_paths = [Path(master) for master in masters if master is not None]
            cutout_gate = quality_gates.evaluate_cutouts(cache_dir, [master.name for master in master_paths])
            if cutout_gate["status"] != "passed":
                raise ValueError(f"cached cutout gate rejected batch: {cutout_gate['rejection_reasons']}")
        geometry_evidence = None
        if preset.get("derive_geometry"):
            derived = derive_shared_geometry(master_paths, preset["variants"])
            geometry = derived["geometry"]
            variants_config = derived["variants"]
            geometry_evidence = derived["evidence"]
        else:
            geometry = preset["geometry"]
            variants_config = preset["variants"]
        export_config = {
            "job_id": "character", "action": selection["action"], "direction": "ne", "loop": selection["loop"],
            **selection, "selection_mode": params["selection_mode"],
            "source": {"file": source.name, "sha256": sha256(source)},
            "geometry": geometry, "variants": variants_config,
        }
        variants = export_variants(master_paths, root, export_config)
        for variant in variants:
            timing.stages.extend(variant.pop("_timings"))
        duration = (selection["cycle_end_exclusive"] - selection["cycle_start"]) / selection["native_fps"]
        playback_fps = len(selection["selected_indices"]) / duration
        with timing.stage("preview_encode"):
            for variant in variants:
                variant["preview"] = _encode_preview(
                    root, variant["canvas"], playback_fps, len(master_paths), loop=selection["loop"],
                    frame_durations_seconds=selection.get("frame_durations_seconds"),
                )
            write_player(root, max(variant["canvas"] for variant in variants))
        with timing.stage("final_verify"):
            verification = _verify_all_frames(root, variants)
            _atomic_json(root / "spatial-verification.json", verification)
        artifacts = ["preview.html", "spatial-verification.json"]
        for variant in variants:
            artifacts.extend([variant["atlas"], variant["manifest"], variant["preview"]])
            artifacts.extend(f"all-frames-{variant['canvas']}-{background}.png" for background in BG)
        with timing.stage("package"):
            package = root / "spatial-export.zip"
            with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name in artifacts:
                    archive.write(root / name, name)
        timings = timing.record(artifact_ready=True)
        _atomic_json(root / "spatial-timings.json", timings)
        result_record = {
            "schema": "animation-spatial-export-result-v1", "status": "completed",
            "selection_mode": params["selection_mode"], "provider_call_made": False,
            "source_sha256": sha256(source), "selected_indices": selection["selected_indices"],
            "variants": variants, "zip": {"file": package.name, "sha256": sha256(package)},
            "geometry": {**geometry, "variants": variants_config, "derivation": geometry_evidence},
            "visual_quality_certified": False,
        }
        _atomic_json(root / "spatial-export-result.json", result_record)
        artifacts.extend(["spatial-export.zip", "spatial-timings.json", "spatial-export-result.json"])
        return {"status": "completed", "artifacts": artifacts, "details": result_record}
    except Exception:
        _atomic_json(root / "spatial-timings.json", timing.record(artifact_ready=False))
        raise


def run_job(config_path: Path) -> dict[str, Any]:
    config_path = Path(config_path).resolve(strict=True)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    source = Path(config["source_video"]).resolve(strict=True)
    output = Path(config["output_dir"]).resolve()
    cache_dir = Path(config["cutout_cache_dir"]).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("output directory must be absent or empty; use a fresh workspace")
    output.mkdir(parents=True, exist_ok=True)
    if sha256(source) != config["source_sha256"]:
        raise ValueError("source video hash does not match config")
    if config.get("selection_mode") != "explicit_human_reviewed":
        raise ValueError("this CLI currently supports honest explicit_human_reviewed selection only")
    receipt_path = Path(config["selection_receipt"]).resolve(strict=True)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("bounds") != [config["cycle_start"], config["cycle_end_exclusive"]]:
        raise ValueError("selection receipt bounds do not match config")
    timing = Timings()
    try:
        extraction = output / "selected-originals"
        extraction.mkdir()
        shutil.copyfile(source, extraction / "source.mp4")
        with timing.stage("extraction"):
            extracted = pipeline.run_stage("extract_frames", extraction, {
                "input": "source.mp4",
                "fps": config["native_fps"],
                "indices": config["selected_indices"],
                "output_prefix": "original",
            })
            if extracted["status"] != "needs_review":
                raise ValueError("frame extraction did not complete")
        originals = [extraction / f"original-frame-{order:04d}.png" for order in range(len(config["selected_indices"]))]
        imported = []
        import_config = config.get("accepted_cache_import")
        if import_config:
            masters = [Path(item).resolve(strict=True) for item in import_config["masters"]]
            expected = import_config["master_sha256"]
            if len(masters) != len(originals) or [sha256(path) for path in masters] != expected:
                raise ValueError("accepted master import mapping or hashes do not match")
            with timing.stage("cache_import"):
                for original, master in zip(originals, masters):
                    imported.append(import_cached_cutout(original, master, cache_dir, config["removal_preset"], config["removal_recipe"]))
                _atomic_json(output / "cache-import-receipt.json", {
                    "schema": "accepted-cutout-import-v1",
                    "source_video_sha256": config["source_sha256"],
                    "selection_receipt_sha256": sha256(receipt_path),
                    "entries": [{"input_sha256": sha256(source_frame), "cache_key": item["key"], "output_sha256": sha256(item["path"])} for source_frame, item in zip(originals, imported)],
                    "provider_call_made": False,
                })
        with timing.stage("cutout_cache_lookup"):
            masters = [lookup_cached_cutout(path, cache_dir, config["removal_preset"], config["removal_recipe"]) for path in originals]
            if any(path is None for path in masters):
                missing = [order for order, path in enumerate(masters) if path is None]
                raise ValueError(f"cutout cache miss for frame orders {missing}; no provider call was made")
            master_paths = [Path(path) for path in masters if path is not None]
            cutout_gate = quality_gates.evaluate_cutouts(cache_dir, [path.name for path in master_paths])
            if cutout_gate["status"] != "passed":
                raise ValueError(f"cached cutout gate rejected batch: {cutout_gate['rejection_reasons']}")
        export_config = {
            "job_id": config["job_id"], "action": config["action"], "direction": config["direction"],
            "native_fps": config["native_fps"], "cycle_start": config["cycle_start"], "cycle_end_exclusive": config["cycle_end_exclusive"],
            "selected_indices": config["selected_indices"], "selection_mode": config["selection_mode"],
            "selection_receipt": {"file": receipt_path.name, "sha256": sha256(receipt_path)},
            "source": {"file": source.name, "sha256": config["source_sha256"]},
            "geometry": config["geometry"], "variants": config["variants"],
            "loop": config.get("loop", config["action"] == "walk"),
            "frame_durations_seconds": config.get("frame_durations_seconds"),
        }
        variants = export_variants(master_paths, output, export_config)
        for variant in variants:
            timing.stages.extend(variant.pop("_timings"))
        duration = (config["cycle_end_exclusive"] - config["cycle_start"]) / float(config["native_fps"])
        fps = len(config["selected_indices"]) / duration
        with timing.stage("preview_encode"):
            for variant in variants:
                variant["preview"] = _encode_preview(
                    output, variant["canvas"], fps, len(master_paths), loop=export_config["loop"],
                    frame_durations_seconds=export_config.get("frame_durations_seconds"),
                )
            write_player(output, max(variant["canvas"] for variant in variants))
        with timing.stage("final_verify"):
            verification = _verify_all_frames(output, variants)
            _atomic_json(output / "verification.json", verification)
        with timing.stage("package"):
            package = output / "export.zip"
            with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for variant in variants:
                    for key in ("atlas", "manifest", "preview"):
                        archive.write(output / variant[key], variant[key])
                archive.write(output / "verification.json", "verification.json")
                if (output / "cache-import-receipt.json").is_file():
                    archive.write(output / "cache-import-receipt.json", "cache-import-receipt.json")
                archive.write(output / "preview.html", "preview.html")
        timings = timing.record(artifact_ready=True)
        _atomic_json(output / "timings.json", timings)
        result = {
            "status": "completed",
            "selection_mode": config["selection_mode"],
            "provider_call_made": False,
            "cache_entries_imported": sum(bool(item["imported"]) for item in imported),
            "cache_entries_reused": len(master_paths) - sum(bool(item["imported"]) for item in imported),
            "variants": variants,
            "verification": "verification.json",
            "timings": "timings.json",
            "zip": {"file": package.name, "sha256": sha256(package)},
        }
        _atomic_json(output / "run-result.json", result)
        return result
    except Exception:
        _atomic_json(output / "timings.json", timing.record(artifact_ready=False))
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path, help="JSON job config; no source edits are required between jobs")
    args = parser.parse_args()
    print(json.dumps(run_job(args.config), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
