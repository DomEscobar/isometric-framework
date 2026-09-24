"""Deterministic technical quality gates for cutouts and atlases.

These checks reject malformed processing outputs. They never certify visual quality.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from statistics import mean, median
from typing import Any

from PIL import Image, ImageChops

_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file(root: Path, name: Any, suffix: str) -> Path:
    if not isinstance(name, str) or not _SAFE.fullmatch(name) or not name.lower().endswith(suffix):
        raise ValueError("quality-gate input must be a safe artifact basename")
    path = root / name
    resolved_root = root.resolve(strict=True)
    resolved = path.resolve(strict=True)
    if path.is_symlink() or resolved.parent != resolved_root or not resolved.is_file():
        raise ValueError("quality-gate input must be a confined regular artifact")
    return resolved


def _alpha_record(image: Image.Image) -> dict[str, Any]:
    alpha = image.getchannel("A")
    histogram = alpha.histogram()
    bounds = alpha.getbbox()
    extrema = alpha.getextrema()
    alpha.close()
    total = image.width * image.height
    return {
        "minimum": extrema[0],
        "maximum": extrema[1],
        "transparent_pixels": histogram[0],
        "semi_transparent_pixels": sum(histogram[1:255]),
        "opaque_pixels": histogram[255],
        "visible_bounds": list(bounds) if bounds else None,
        "visible_fraction": round(sum(histogram[1:]) / total, 8),
        "has_true_alpha": histogram[0] > 0 and sum(histogram[1:]) > 0,
    }


def evaluate_cutouts(workdir: Path, inputs: list[str]) -> dict[str, Any]:
    """Check alpha integrity, confinement and batch geometry without visual approval."""
    root = Path(workdir)
    if not root.is_dir() or root.is_symlink() or not isinstance(inputs, list) or not inputs or len(inputs) > 128 or len(set(inputs)) != len(inputs):
        raise ValueError("cutout gate requires 1..128 unique confined PNG artifacts")
    records: list[dict[str, Any]] = []
    reasons: set[str] = set()
    dimensions: set[tuple[int, int]] = set()
    heights: list[int] = []
    bottoms: list[int] = []
    for order, name in enumerate(inputs):
        path = _file(root, name, ".png")
        try:
            with Image.open(path) as opened:
                if opened.format != "PNG":
                    raise ValueError("cutout gate input is not PNG")
                image = opened.convert("RGBA")
        except OSError as error:
            raise ValueError("cutout gate input is not a valid PNG") from error
        alpha = _alpha_record(image)
        dimensions.add(image.size)
        bounds = alpha["visible_bounds"]
        if not alpha["has_true_alpha"]:
            reasons.add("missing_true_alpha")
        if bounds is None:
            reasons.add("empty_foreground")
        else:
            heights.append(bounds[3] - bounds[1])
            bottoms.append(bounds[3])
            if bounds[0] <= 0 or bounds[1] <= 0 or bounds[2] >= image.width or bounds[3] >= image.height:
                reasons.add("foreground_touches_frame_edge")
        if alpha["visible_fraction"] < 0.002:
            reasons.add("foreground_too_small")
        if alpha["visible_fraction"] > 0.85:
            reasons.add("foreground_coverage_too_large")
        records.append({"order": order, "file": name, "sha256": _sha256(path), "width": image.width, "height": image.height, "alpha": alpha})
        image.close()
    if len(dimensions) != 1:
        reasons.add("inconsistent_dimensions")
    if heights:
        typical_height = median(heights)
        if typical_height <= 0 or any(abs(value - typical_height) / typical_height > 0.35 for value in heights):
            reasons.add("unstable_visible_height")
    if bottoms:
        typical_bottom = median(bottoms)
        canvas_height = records[0]["height"]
        if any(abs(value - typical_bottom) / canvas_height > 0.12 for value in bottoms):
            reasons.add("unstable_foot_baseline")
    return {
        "version": 1,
        "gate": "cutout-alpha-geometry-v1",
        "status": "passed" if not reasons else "rejected",
        "rejection_reasons": sorted(reasons),
        "frames": records,
        "technical_checks_only": True,
        "visual_quality_certified": False,
    }


def _motion_feature(image: Image.Image) -> dict[str, Any]:
    rgb = image.convert("RGB")
    alpha = image.getchannel("A") if image.mode == "RGBA" else Image.new("L", image.size, 255)
    if alpha.getextrema() == (255, 255):
        corner = max(1, min(image.size) // 16)
        pixels = []
        for box in (
            (0, 0, corner, corner),
            (image.width - corner, 0, image.width, corner),
            (0, image.height - corner, corner, image.height),
            (image.width - corner, image.height - corner, image.width, image.height),
        ):
            with rgb.crop(box) as sample:
                pixels.extend(sample.get_flattened_data())
        background = tuple(int(median(pixel[channel] for pixel in pixels)) for channel in range(3))
        alpha.close()
        background_image = Image.new("RGB", image.size, background)
        difference = ImageChops.difference(rgb, background_image)
        channels = difference.split()
        maximum = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
        # max-channel >= 21 is the integer lower bound implied by an RGB
        # Euclidean distance of 35, implemented in Pillow rather than a slow
        # identity/color-specific Python pixel loop.
        alpha = maximum.point(lambda value: 255 if value >= 21 else 0)
        background_image.close()
        difference.close()
        maximum.close()
        for channel in channels:
            channel.close()
    bounds = alpha.getbbox()
    if bounds is None:
        rgb.close()
        alpha.close()
        raise ValueError("motion frame has empty foreground")
    crop_rgb = rgb.crop(bounds)
    crop_alpha = alpha.crop(bounds)
    width, height = crop_rgb.size
    scale = min(56 / width, 56 / height)
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    resized_rgb = crop_rgb.resize(size, Image.Resampling.BILINEAR)
    resized_alpha = crop_alpha.resize(size, Image.Resampling.NEAREST)
    normalized = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    offset = ((64 - size[0]) // 2, (64 - size[1]) // 2)
    normalized.paste(resized_rgb, offset, resized_alpha)

    lower_top = bounds[1] + round((bounds[3] - bounds[1]) * 0.72)
    lower = alpha.crop((bounds[0], lower_top, bounds[2], bounds[3]))
    lower_pixels = lower.tobytes()
    occupied = [index % lower.width for index, value in enumerate(lower_pixels) if value]
    occupied_mean = mean(occupied) if occupied else 0.0
    foot_balance = (occupied_mean / max(1, lower.width - 1)) if occupied else 0.5
    foot_spread = (
        math.sqrt(mean((value - occupied_mean) ** 2 for value in occupied)) / max(1, lower.width - 1)
        if occupied else 0.0
    )
    row_centroids = []
    for band in range(4):
        top = round(lower.height * band / 4)
        bottom = round(lower.height * (band + 1) / 4)
        xs = [
            index % lower.width for index, value in enumerate(lower_pixels)
            if value and top <= index // lower.width < bottom
        ]
        row_centroids.append(mean(xs) / max(1, lower.width - 1) if xs else 0.5)
    normalized_alpha = normalized.getchannel("A")
    upper = normalized_alpha.crop((0, 0, 64, 38))
    upper_values = upper.tobytes()
    upper_points = [(index % upper.width, index // upper.width) for index, value in enumerate(upper_values) if value]
    upper_centroid_x = mean(point[0] for point in upper_points) / 63 if upper_points else 0.5
    result = {
        "normalized": normalized,
        "bounds": list(bounds),
        "foot_balance": foot_balance,
        "foot_spread": foot_spread,
        "lower_phase": foot_balance + 0.35 * (row_centroids[-1] - row_centroids[0]),
        "upper_centroid_x": upper_centroid_x,
        "body_aspect_ratio": width / max(1, height),
    }
    for item in (rgb, alpha, crop_rgb, crop_alpha, resized_rgb, resized_alpha, lower, normalized_alpha, upper):
        item.close()
    return result


def _normalized_pose_difference(left: Image.Image, right: Image.Image) -> float:
    with left.getchannel("A") as left_alpha, right.getchannel("A") as right_alpha:
        a = left_alpha.tobytes()
        b = right_alpha.tobytes()
    return mean(abs(x - y) / 255 for x, y in zip(a, b))


def _pose_velocity(left: Image.Image, right: Image.Image) -> list[float]:
    with left.getchannel("A") as left_alpha, right.getchannel("A") as right_alpha:
        return [(b - a) / 255 for a, b in zip(left_alpha.tobytes(), right_alpha.tobytes())]


def _turning_points(values: list[float], epsilon: float) -> int:
    signs: list[int] = []
    for left, right in zip(values, values[1:]):
        delta = right - left
        sign = 1 if delta > epsilon else -1 if delta < -epsilon else 0
        if sign and (not signs or sign != signs[-1]):
            signs.append(sign)
    return max(0, len(signs) - 1)


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return numerator / max(left_norm * right_norm, 1e-12)


def evaluate_motion_sequence(
    workdir: Path,
    inputs: list[str],
    *,
    native_indices: list[int],
    native_fps: float,
    cycle_end_exclusive: int,
    expected_facing: str,
) -> dict[str, Any]:
    """Reject sparse, incomplete, rotating or discontinuous proposed gait cycles."""
    root = Path(workdir)
    if (
        not isinstance(inputs, list) or len(inputs) < 4 or len(inputs) > 64
        or len(inputs) != len(native_indices) or len(set(inputs)) != len(inputs)
        or any(type(value) is not int for value in native_indices)
        or native_indices != sorted(set(native_indices))
        or type(native_fps) not in (int, float) or native_fps <= 0
        or type(cycle_end_exclusive) is not int or cycle_end_exclusive <= native_indices[-1]
        or expected_facing not in {"n", "ne", "e", "se", "s", "sw", "w", "nw"}
    ):
        raise ValueError("motion gate inputs are invalid")
    features = []
    for name in inputs:
        path = _file(root, name, ".png")
        with Image.open(path) as opened:
            features.append(_motion_feature(opened.convert("RGBA")))
    try:
        internal = [
            _normalized_pose_difference(left["normalized"], right["normalized"])
            for left, right in zip(features, features[1:])
        ]
        wrap = _normalized_pose_difference(features[-1]["normalized"], features[0]["normalized"])
        typical = median(internal)
        native_gaps = [right - left for left, right in zip(native_indices, native_indices[1:])]
        native_gaps.append(cycle_end_exclusive - native_indices[-1])
        maximum_allowed_gap = max(1, math.floor(float(native_fps) / 10))
        wrap_velocity = _pose_velocity(features[-1]["normalized"], features[0]["normalized"])
        incoming_velocity = _pose_velocity(features[-2]["normalized"], features[-1]["normalized"])
        outgoing_velocity = _pose_velocity(features[0]["normalized"], features[1]["normalized"])
        velocity_cosines = {
            "incoming_to_wrap": _cosine(incoming_velocity, wrap_velocity),
            "wrap_to_outgoing": _cosine(wrap_velocity, outgoing_velocity),
        }
        foot = [item["foot_balance"] for item in features]
        foot_range = max(foot) - min(foot)
        foot_endpoint_change = abs(foot[-1] - foot[0])
        lower_phase = [item["lower_phase"] for item in features]
        lower_phase_range = max(lower_phase) - min(lower_phase)
        lower_turning_points = _turning_points(lower_phase, max(0.0008, lower_phase_range * 0.04))
        spread = [item["foot_spread"] for item in features]
        spread_range = max(spread) - min(spread)
        upper_centroid = [item["upper_centroid_x"] for item in features]
        upper_centroid_range = max(upper_centroid) - min(upper_centroid)
        aspect = [item["body_aspect_ratio"] for item in features]
        aspect_range = max(aspect) - min(aspect)
        reasons: set[str] = set()
        if max(native_gaps) > maximum_allowed_gap:
            reasons.add("sparse_temporal_sampling")
        seam_ratio = wrap / max(typical, 1e-9)
        if seam_ratio > 1.1 or min(velocity_cosines.values()) < -0.1:
            reasons.add("loop_pose_discontinuity")
        if upper_centroid_range > 0.085 or aspect_range > 0.22:
            reasons.add("orientation_drift")
        if lower_phase_range < 0.025 and spread_range < 0.018:
            reasons.add("insufficient_gait_articulation")
        elif lower_turning_points < 2:
            reasons.add("incomplete_alternating_gait_cycle")
        elif foot_endpoint_change > max(0.035, foot_range * 0.55):
            reasons.add("incomplete_gait_cycle")
        return {
            "version": 1,
            "gate": "motion-cycle-orientation-v1",
            "status": "passed" if not reasons else "rejected",
            "rejection_reasons": sorted(reasons),
            "native_indices": native_indices,
            "native_fps": float(native_fps),
            "cycle_end_exclusive": cycle_end_exclusive,
            "cycle_duration_seconds": (cycle_end_exclusive - native_indices[0]) / float(native_fps),
            "sampling": {
                "native_gaps_including_wrap_boundary": native_gaps,
                "maximum_native_gap": max(native_gaps),
                "maximum_allowed_native_gap": maximum_allowed_gap,
            },
            "pose_velocity": {
                "normalized_internal_differences": internal,
                "median_internal_difference": typical,
                "wrap_difference": wrap,
                "wrap_to_internal_median_ratio": seam_ratio,
                "boundary_velocity_cosines": velocity_cosines,
            },
            "gait_cycle": {
                "foot_balance": foot,
                "foot_balance_range": foot_range,
                "endpoint_change": foot_endpoint_change,
                "lower_phase": lower_phase,
                "lower_phase_range": lower_phase_range,
                "foot_spread_range": spread_range,
                "turning_points": lower_turning_points,
                "complete_alternating_cycle": lower_turning_points >= 2,
            },
            "source_pose_orientation": {
                "included": True,
                "expected_facing": expected_facing,
                "method": "generic_upper_silhouette_and_body_aspect_v1",
                "identity_or_apparel_color_heuristic_used": False,
                "upper_silhouette_centroid_x_range": upper_centroid_range,
                "body_aspect_ratio_range": aspect_range,
                "automatic_classification": "orientation_drift" if "orientation_drift" in reasons else "stable_by_local_signature",
                "classification_is_visual_approval": False,
            },
            "technical_checks_only": True,
            "visual_quality_certified": False,
        }
    finally:
        for feature in features:
            feature["normalized"].close()


def evaluate_atlas(workdir: Path, atlas_name: str, manifest_name: str) -> dict[str, Any]:
    """Verify atlas hash, transparency, frame geometry, timing and common anchor."""
    root = Path(workdir)
    atlas_path = _file(root, atlas_name, ".png")
    manifest_path = _file(root, manifest_name, ".json")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("atlas manifest is invalid") from error
    reasons: set[str] = set()
    if not isinstance(manifest, dict) or manifest.get("schema") != "animation-pipeline-atlas-v1":
        raise ValueError("atlas manifest schema is invalid")
    with Image.open(atlas_path) as opened:
        if opened.format != "PNG":
            raise ValueError("atlas is not PNG")
        atlas = opened.convert("RGBA")
    image_record = manifest.get("image") if isinstance(manifest.get("image"), dict) else {}
    atlas_hash = _sha256(atlas_path)
    if image_record.get("file") != atlas_name or image_record.get("sha256") != atlas_hash:
        reasons.add("atlas_hash_or_name_mismatch")
    if image_record.get("width") != atlas.width or image_record.get("height") != atlas.height:
        reasons.add("atlas_dimensions_mismatch")
    alpha = _alpha_record(atlas)
    if alpha["transparent_pixels"] == 0:
        reasons.add("atlas_has_no_transparency")
    alpha_values = atlas.getchannel("A").get_flattened_data()
    low_alpha_fringe_pixels = sum(1 for value in alpha_values if 0 < value < 8)
    if low_alpha_fringe_pixels:
        reasons.add("low_alpha_resample_fringe")
    colors = atlas.convert("RGB").getcolors(maxcolors=atlas.width * atlas.height) or []
    magenta = sum(count for count, color in colors if color[0] >= 240 and color[1] <= 20 and color[2] >= 240)
    if magenta / (atlas.width * atlas.height) > 0.5 and alpha["transparent_pixels"] == 0:
        reasons.add("opaque_magenta_background")
    frames = manifest.get("frames")
    clip = manifest.get("clip") if isinstance(manifest.get("clip"), dict) else {}
    if not isinstance(frames, list) or not frames:
        raise ValueError("atlas manifest has no frames")
    ids: list[str] = []
    anchors: list[dict[str, Any]] = []
    for order, frame in enumerate(frames):
        if not isinstance(frame, dict) or frame.get("order") != order or not isinstance(frame.get("id"), str):
            reasons.add("invalid_frame_order_or_id")
            continue
        rect = frame.get("rect") if isinstance(frame.get("rect"), dict) else {}
        values = [rect.get(key) for key in ("x", "y", "width", "height")]
        if any(type(value) is not int for value in values):
            reasons.add("invalid_frame_rect")
        else:
            x, y, width, height = values
            if width < 1 or height < 1 or x < 0 or y < 0 or x + width > atlas.width or y + height > atlas.height:
                reasons.add("frame_rect_outside_atlas")
        anchor = frame.get("anchor")
        if not isinstance(anchor, dict) or set(anchor) != {"x", "y"} or any(type(anchor[key]) not in (int, float) or not math.isfinite(float(anchor[key])) or not 0 <= anchor[key] <= 1 for key in ("x", "y")):
            reasons.add("invalid_frame_anchor")
        else:
            anchors.append(anchor)
        ids.append(frame["id"])
    if clip.get("frames") != ids:
        reasons.add("clip_frame_order_mismatch")
    fps = clip.get("fps")
    if type(fps) not in (int, float) or not math.isfinite(float(fps)) or fps <= 0:
        reasons.add("invalid_clip_fps")
        duration = None
    else:
        duration = round(len(frames) / float(fps), 9)
    if not anchors or any(anchor != anchors[0] for anchor in anchors[1:]):
        reasons.add("inconsistent_foot_anchor")
    atlas.close()
    return {
        "version": 1,
        "gate": "atlas-integrity-timing-v1",
        "status": "passed" if not reasons else "rejected",
        "rejection_reasons": sorted(reasons),
        "atlas_sha256": atlas_hash,
        "manifest_sha256": _sha256(manifest_path),
        "frame_count": len(frames),
        "fps": float(fps) if type(fps) in (int, float) else None,
        "duration_seconds": duration,
        "foot_anchor": anchors[0] if anchors else None,
        "alpha": alpha,
        "low_alpha_fringe_pixels": low_alpha_fringe_pixels,
        "technical_checks_only": True,
        "visual_quality_certified": False,
    }
