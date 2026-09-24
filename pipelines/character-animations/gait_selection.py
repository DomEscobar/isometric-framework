"""Generic silhouette/lower-body gait-cycle candidate selection.

The selector is intentionally color/identity agnostic.  Corner color is used only to
estimate an opaque video's background mask; ranking uses silhouette and lower-body
motion, never raw RGBA similarity or skin/apparel colors.
"""
from __future__ import annotations

import math
from pathlib import Path
from statistics import mean, median
from typing import Any, Sequence

from PIL import Image, ImageChops


def _background_mask(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    width, height = rgb.size
    size = max(2, min(width, height) // 20)
    samples: list[tuple[int, int, int]] = []
    for box in (
        (0, 0, size, size),
        (width - size, 0, width, size),
        (0, height - size, size, height),
        (width - size, height - size, width, height),
    ):
        with rgb.crop(box) as corner:
            samples.extend(corner.get_flattened_data())
    background = tuple(int(median(pixel[channel] for pixel in samples)) for channel in range(3))
    mask = Image.new("L", rgb.size)
    mask.putdata([
        255 if sum((pixel[channel] - background[channel]) ** 2 for channel in range(3)) >= 35**2 else 0
        for pixel in rgb.get_flattened_data()
    ])
    rgb.close()
    return mask


def _normalize_mask(mask: Image.Image, bounds: tuple[int, int, int, int], size: int = 64) -> Image.Image:
    with mask.crop(bounds) as crop:
        width, height = crop.size
        scale = min((size - 8) / max(1, width), (size - 4) / max(1, height))
        resized = crop.resize((max(1, round(width * scale)), max(1, round(height * scale))), Image.Resampling.NEAREST)
    output = Image.new("L", (size, size), 0)
    output.paste(resized, ((size - resized.width) // 2, size - 2 - resized.height))
    resized.close()
    return output


def _difference(left: Image.Image, right: Image.Image, crop: tuple[int, int, int, int] | None = None) -> float:
    if crop is None:
        a, b = left, right
        owned = False
    else:
        a, b = left.crop(crop), right.crop(crop)
        owned = True
    with ImageChops.difference(a, b) as delta:
        value = sum(delta.get_flattened_data()) / (255.0 * delta.width * delta.height)
    if owned:
        a.close()
        b.close()
    return value


def _feature(path: Path) -> dict[str, Any]:
    with Image.open(path) as opened:
        mask = _background_mask(opened)
    bounds = mask.getbbox()
    if bounds is None:
        mask.close()
        raise ValueError(f"empty foreground in {path.name}")
    normalized = _normalize_mask(mask, bounds)
    mask.close()
    pixels = list(normalized.get_flattened_data())
    lower_top = 38
    lower_points = [
        (index % 64, index // 64)
        for index, value in enumerate(pixels)
        if value and index // 64 >= lower_top
    ]
    if not lower_points:
        normalized.close()
        raise ValueError(f"empty lower-body silhouette in {path.name}")
    xs = [point[0] for point in lower_points]
    foot_points = [point for point in lower_points if point[1] >= 54]
    if not foot_points:
        foot_points = lower_points
    foot_xs = [point[0] for point in foot_points]
    foot_mean = mean(foot_xs) / 63.0
    foot_spread = math.sqrt(mean((value - mean(foot_xs)) ** 2 for value in foot_xs)) / 63.0
    row_centroids: list[float] = []
    for start, end in ((38, 43), (43, 48), (48, 53), (53, 58), (58, 64)):
        band = [x for x, y in lower_points if start <= y < end]
        row_centroids.append((mean(band) / 63.0) if band else 0.5)
    return {
        "normalized": normalized,
        "bounds": list(bounds),
        "root_x": (bounds[0] + bounds[2] - 1) / 2,
        "root_bottom": bounds[3],
        "foot_centroid": foot_mean,
        "foot_spread": foot_spread,
        "lower_row_centroids": row_centroids,
    }


def _turning_points(values: Sequence[float], epsilon: float) -> int:
    signs: list[int] = []
    for left, right in zip(values, values[1:]):
        delta = right - left
        sign = 1 if delta > epsilon else -1 if delta < -epsilon else 0
        if sign and (not signs or sign != signs[-1]):
            signs.append(sign)
    return max(0, len(signs) - 1)


def analyze_gait_frames(
    paths: Sequence[Path],
    *,
    native_fps: float,
    minimum_cycle_seconds: float = 0.75,
    maximum_cycle_seconds: float = 1.875,
    maximum_results: int = 3,
) -> dict[str, Any]:
    """Exhaustively rank bounded whole-cycle intervals on a native frame sequence."""
    if not paths or len(paths) < 8 or native_fps <= 0:
        raise ValueError("gait selection requires a non-empty native frame sequence and positive fps")
    minimum_frames = max(8, math.ceil(minimum_cycle_seconds * native_fps))
    maximum_frames = min(len(paths) - 1, math.floor(maximum_cycle_seconds * native_fps))
    if minimum_frames > maximum_frames:
        raise ValueError("gait cycle bounds do not fit the frame sequence")
    features = [_feature(Path(path)) for path in paths]
    try:
        adjacent_lower = [
            _difference(left["normalized"], right["normalized"], (0, 36, 64, 64))
            for left, right in zip(features, features[1:])
        ]
        adjacent_full = [
            _difference(left["normalized"], right["normalized"])
            for left, right in zip(features, features[1:])
        ]
        active_reference = max(median(adjacent_lower), 1e-6)
        hold_threshold = max(0.0025, active_reference * 0.22)
        hold_transitions = [index for index, value in enumerate(adjacent_lower) if value < hold_threshold]
        candidates: list[dict[str, Any]] = []
        for start in range(0, len(features) - minimum_frames):
            for end_exclusive in range(start + minimum_frames, min(len(features) - 1, start + maximum_frames) + 1):
                # A candidate contains frames [start, end_exclusive); the source frame at
                # end_exclusive is the desired first-frame phase recurrence.
                boundary = end_exclusive
                interval = features[start:end_exclusive]
                lower_internal = adjacent_lower[start:end_exclusive - 1]
                full_internal = adjacent_full[start:end_exclusive - 1]
                foot = [item["foot_centroid"] for item in interval]
                spread = [item["foot_spread"] for item in interval]
                combined_phase = [
                    item["foot_centroid"] + 0.35 * (item["lower_row_centroids"][-1] - item["lower_row_centroids"][0])
                    for item in interval
                ]
                phase_range = max(combined_phase) - min(combined_phase)
                spread_range = max(spread) - min(spread)
                lower_seam = _difference(features[end_exclusive - 1]["normalized"], features[start]["normalized"], (0, 36, 64, 64))
                full_seam = _difference(features[end_exclusive - 1]["normalized"], features[start]["normalized"])
                recurrence_lower = _difference(features[boundary]["normalized"], features[start]["normalized"], (0, 36, 64, 64))
                recurrence_full = _difference(features[boundary]["normalized"], features[start]["normalized"])
                typical_lower = max(median(lower_internal), 1e-6)
                typical_full = max(median(full_internal), 1e-6)
                incoming = combined_phase[-1] - combined_phase[-2]
                outgoing = combined_phase[1] - combined_phase[0]
                recurrence_velocity = combined_phase[boundary - start] - combined_phase[-1] if False else 0.0
                velocity_scale = max(median(abs(right - left) for left, right in zip(combined_phase, combined_phase[1:])), 1e-5)
                velocity_mismatch = abs(incoming - outgoing) / velocity_scale
                turn_count = _turning_points(combined_phase, max(0.0008, phase_range * 0.035))
                start_hold = start > 0 and adjacent_lower[start - 1] < hold_threshold
                end_hold = end_exclusive < len(adjacent_lower) and adjacent_lower[end_exclusive] < hold_threshold
                internal_hold_fraction = sum(value < hold_threshold for value in lower_internal) / max(1, len(lower_internal))
                root_x = [item["root_x"] for item in interval]
                root_bottom = [item["root_bottom"] for item in interval]
                width = max(1, features[start]["bounds"][2] - features[start]["bounds"][0])
                height = max(1, features[start]["bounds"][3] - features[start]["bounds"][1])
                root_x_range = (max(root_x) - min(root_x)) / width
                bob_range = (max(root_bottom) - min(root_bottom)) / height
                upper_differences = [
                    _difference(interval[0]["normalized"], item["normalized"], (0, 0, 64, 38))
                    for item in interval[1:]
                ]
                upper_silhouette_range = max(upper_differences, default=0.0)
                reasons: list[str] = []
                if start_hold or end_hold or internal_hold_fraction > 0.20:
                    reasons.append("source_hold_overlap")
                if phase_range < 0.020 and spread_range < 0.018:
                    reasons.append("insufficient_lower_body_articulation")
                if turn_count < 2:
                    reasons.append("incomplete_alternating_cycle")
                if recurrence_lower / typical_lower > 1.25 or recurrence_full / typical_full > 1.35:
                    reasons.append("phase_recurrence_mismatch")
                if lower_seam / typical_lower > 1.65 or full_seam / typical_full > 1.70:
                    reasons.append("silhouette_seam_discontinuity")
                if velocity_mismatch > 3.5:
                    reasons.append("phase_velocity_discontinuity")
                if root_x_range > 0.12:
                    reasons.append("root_horizontal_drift")
                if upper_silhouette_range > 0.22:
                    reasons.append("upper_silhouette_instability")
                duration = (end_exclusive - start) / native_fps
                score = (
                    recurrence_lower / typical_lower
                    + 0.75 * recurrence_full / typical_full
                    + 0.35 * lower_seam / typical_lower
                    + 0.25 * full_seam / typical_full
                    + 0.08 * velocity_mismatch
                    + 0.9 * internal_hold_fraction
                    + 0.2 * abs(duration - 33 / native_fps)
                )
                candidates.append({
                    "start_native_index": start,
                    "end_exclusive_native_index": end_exclusive,
                    "frame_count": end_exclusive - start,
                    "duration_seconds": round(duration, 9),
                    "score": round(score, 9),
                    "rejection_reasons": reasons,
                    "metrics": {
                        "lower_phase_range": phase_range,
                        "foot_spread_range": spread_range,
                        "turning_points": turn_count,
                        "lower_seam_to_internal_ratio": lower_seam / typical_lower,
                        "full_silhouette_seam_to_internal_ratio": full_seam / typical_full,
                        "lower_phase_recurrence_to_internal_ratio": recurrence_lower / typical_lower,
                        "full_silhouette_recurrence_to_internal_ratio": recurrence_full / typical_full,
                        "phase_velocity_mismatch_ratio": velocity_mismatch,
                        "internal_hold_fraction": internal_hold_fraction,
                        "root_x_range_body_fraction": root_x_range,
                        "natural_bob_range_body_fraction": bob_range,
                        "upper_silhouette_range": upper_silhouette_range,
                    },
                })
        accepted = sorted((item for item in candidates if not item["rejection_reasons"]), key=lambda item: item["score"])
        rejected = sorted((item for item in candidates if item["rejection_reasons"]), key=lambda item: item["score"])
        for index, item in enumerate(accepted[:maximum_results], start=1):
            item["id"] = f"gait-candidate-{index:02d}"
        return {
            "version": 1,
            "method": "native-silhouette-lower-body-phase-v1",
            "identity_or_apparel_color_heuristic_used": False,
            "native_fps": native_fps,
            "frame_count": len(paths),
            "search_bounds_frames": [minimum_frames, maximum_frames],
            "intervals_examined": len(candidates),
            "hold_threshold": hold_threshold,
            "hold_transition_indices": hold_transitions,
            "accepted_candidates": accepted[:maximum_results],
            "accepted_candidate_count": len(accepted),
            "rejected_candidates": rejected[:50],
            "visual_quality_certified": False,
        }
    finally:
        for feature in features:
            feature["normalized"].close()
