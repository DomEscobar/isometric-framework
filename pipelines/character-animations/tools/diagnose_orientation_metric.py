from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
import animation_review

OUT = ROOT / "review/real-cold-e2e-01/orientation-diagnostic"
SOURCES = {
    "new-minimax": ROOT / "review/real-cold-e2e-01/source-video.mp4",
    "accepted-old-minimax": ROOT / "artifacts/minimax-ne-source-01/video-output.mp4",
    "rotating-old-wan": ROOT / "artifacts/review-candidates/wan-existing-accepted-window/source.mp4",
    "clipped-omni": ROOT / "artifacts/gemini-omni-video-3s-01/video-output.mp4",
}


def skin_pixel(pixel: tuple[int, int, int]) -> bool:
    return (
        pixel[0] >= 115
        and pixel[0] > pixel[1] * 1.08
        and pixel[1] > pixel[2] * 1.08
        and sum(pixel) / 3 >= 105
    )


def annotated_frame(image: Image.Image, label: str) -> tuple[Image.Image, dict]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    corner_size = max(1, min(width, height) // 16)
    corners = []
    for box in (
        (0, 0, corner_size, corner_size),
        (width - corner_size, 0, width, corner_size),
        (0, height - corner_size, corner_size, height),
        (width - corner_size, height - corner_size, width, height),
    ):
        corners.extend(rgb.crop(box).get_flattened_data())
    background = tuple(sorted(pixel[channel] for pixel in corners)[len(corners) // 2] for channel in range(3))
    visible = []
    for y in range(height):
        for x in range(width):
            pixel = rgb.getpixel((x, y))
            if sum((pixel[channel] - background[channel]) ** 2 for channel in range(3)) >= 35**2:
                visible.append((x, y))
    xs = [p[0] for p in visible]
    ys = [p[1] for p in visible]
    bounds = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
    head_bottom = bounds[1] + max(1, round((bounds[3] - bounds[1]) * 0.36))
    skin = []
    for x, y in visible:
        if y < head_bottom and skin_pixel(rgb.getpixel((x, y))):
            skin.append((x, y))
    roi_width = max(1, bounds[2] - bounds[0])
    centroid_local = (
        sum((x - bounds[0]) / max(1, roi_width - 1) for x, _ in skin) / len(skin)
        if skin else None
    )
    overlay = rgb.copy()
    draw = ImageDraw.Draw(overlay)
    draw.rectangle(bounds, outline=(0, 255, 0), width=3)
    draw.rectangle((bounds[0], bounds[1], bounds[2], head_bottom), outline=(0, 140, 255), width=3)
    for x, y in skin:
        draw.point((x, y), fill=(255, 0, 255))
    if centroid_local is not None:
        cx = bounds[0] + centroid_local * max(1, roi_width - 1)
        draw.line((cx, bounds[1], cx, head_bottom), fill=(255, 255, 0), width=3)
    label_height = 34
    canvas = Image.new("RGB", (width, height + label_height), "black")
    canvas.paste(overlay, (0, label_height))
    ImageDraw.Draw(canvas).text((8, 8), label, fill="white")
    return canvas, {
        "foreground_bounds": list(bounds),
        "head_roi": [bounds[0], bounds[1], bounds[2], head_bottom],
        "background_rgb": list(background),
        "skin_pixel_count": len(skin),
        "head_skin_horizontal_centroid": None if centroid_local is None else round(centroid_local, 6),
        "skin_global_bounds": [min(x for x, _ in skin), min(y for _, y in skin), max(x for x, _ in skin) + 1, max(y for _, y in skin) + 1] if skin else None,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"legend": {"green": "foreground bounding box", "blue": "head ROI: top 36% of full foreground box", "magenta": "pixels matching the color-specific skin predicate", "yellow": "reported local ROI centroid"}, "sources": {}}
    for name, source in SOURCES.items():
        work = OUT / name
        work.mkdir(exist_ok=True)
        local_source = work / "source.mp4"
        if not local_source.exists():
            shutil.copyfile(source, local_source)
        analysis = animation_review.analyze_candidates(work, "source.mp4")
        samples = analysis["samples"]
        populated = [sample for sample in samples if sample["head_skin_horizontal_centroid"] is not None]
        ordered = sorted(populated, key=lambda sample: sample["head_skin_horizontal_centroid"])
        chosen = []
        for sample in (ordered[0], ordered[len(ordered) // 2], ordered[-1]):
            if sample["source_frame_index"] not in {item["source_frame_index"] for item in chosen}:
                chosen.append(sample)
        report["sources"][name] = {
            "source": str(source.relative_to(ROOT)),
            "source_sha256": analysis["source"]["sha256"],
            "status": analysis["status"],
            "hard_failures": analysis["hard_failures"],
            "candidate_count": len(analysis["candidates"]),
            "rejected_candidate_count": len(analysis["rejected_candidates"]),
            "edge_touch_sample_count": len(analysis["framing"]["edge_touch_sample_indices"]),
            "head_skin_centroid_min": ordered[0]["head_skin_horizontal_centroid"],
            "head_skin_centroid_max": ordered[-1]["head_skin_horizontal_centroid"],
            "frames": [],
        }
        images = animation_review._decode_samples(local_source, analysis["sampling"]["sample_fps"], analysis["source"]["width"] * analysis["source"]["height"] * len(samples))
        try:
            for sample in chosen:
                index = sample["sample_index"]
                label = f"{name} native={sample['source_frame_index']} t={sample['timestamp_seconds']:.6f}s sample={index}"
                overlay, diagnostic = annotated_frame(images[index], label)
                filename = f"native-{sample['source_frame_index']:04d}-t-{sample['timestamp_seconds']:.6f}.png"
                overlay.save(work / filename)
                overlay.close()
                report["sources"][name]["frames"].append({"file": str((work / filename).relative_to(OUT)), "sample": sample, "overlay": diagnostic})
        finally:
            for image in images:
                image.close()
    (OUT / "diagnostic.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(OUT / "diagnostic.json")


if __name__ == "__main__":
    main()
