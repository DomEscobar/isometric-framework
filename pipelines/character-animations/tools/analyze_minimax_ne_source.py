#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from statistics import mean

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import animation_review

WORKDIR = ROOT / "artifacts" / "minimax-ne-source-01"
FRAMES = WORKDIR / "native-frames"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def foreground_record(path: Path, background: tuple[int, int, int]) -> dict[str, object]:
    with Image.open(path) as opened:
        rgb = opened.convert("RGB")
        pixels = rgb.load()
        points = [
            (x, y)
            for y in range(rgb.height)
            for x in range(rgb.width)
            if sum((pixels[x, y][channel] - background[channel]) ** 2 for channel in range(3)) >= 35**2
        ]
        if not points:
            return {"bbox": None, "edge_touch": False, "coverage": 0.0}
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        bbox = [min(xs), min(ys), max(xs) + 1, max(ys) + 1]
        return {
            "bbox": bbox,
            "width": bbox[2] - bbox[0],
            "height": bbox[3] - bbox[1],
            "bottom": bbox[3],
            "center_x": (bbox[0] + bbox[2] - 1) / 2,
            "center_y": (bbox[1] + bbox[3] - 1) / 2,
            "coverage": len(points) / (rgb.width * rgb.height),
            "edge_touch": bbox[0] <= 8 or bbox[1] <= 8 or bbox[2] >= rgb.width - 8 or bbox[3] >= rgb.height - 8,
        }


def contact_sheet(files: list[Path], indices: list[int], target: Path) -> None:
    thumb = 256
    label = 28
    columns = 4
    rows = (len(indices) + columns - 1) // columns
    board = Image.new("RGB", (columns * thumb, rows * (thumb + label)), (24, 29, 32))
    draw = ImageDraw.Draw(board)
    for order, index in enumerate(indices):
        with Image.open(files[index]) as opened:
            frame = opened.convert("RGB").resize((thumb, thumb), Image.Resampling.LANCZOS)
        x = (order % columns) * thumb
        y = (order // columns) * (thumb + label)
        board.paste(frame, (x, y))
        draw.rectangle((x, y + thumb, x + thumb, y + thumb + label), fill=(24, 29, 32))
        draw.text((x + 6, y + thumb + 7), f"native {index}  t={index / 24:.3f}s", fill=(255, 220, 90))
    board.save(target)


def browser_recording() -> dict[str, object]:
    from playwright.sync_api import sync_playwright

    browser_source = WORKDIR / "native-source-muted.webm"
    if not browser_source.exists():
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(WORKDIR / "native-source-muted.mp4"), "-an", "-c:v", "libvpx-vp9", "-crf", "24", "-b:v", "0", str(browser_source)],
            check=True,
            timeout=180,
        )
    encoded = base64.b64encode(browser_source.read_bytes()).decode("ascii")
    html = WORKDIR / "source-playback.html"
    html.write_text(
        "<!doctype html><meta charset=utf-8><style>body{margin:0;background:#151b1f;color:white;font:16px sans-serif;text-align:center}"
        "h1{font-size:20px}video{width:768px;height:768px;background:#ccc}p{color:#ffd95a}</style>"
        "<h1>MiniMax fixed-NE source — complete repeated playback</h1>"
        f'<video id=v autoplay muted loop playsinline src="data:video/webm;base64,{encoded}"></video>'
        "<p>Source-only gate. No cutout or runtime sprite claim.</p>"
        "<script>v.play();window.ready=true</script>",
        encoding="utf-8",
    )
    video_dir = WORKDIR / "browser-video"
    if video_dir.exists():
        shutil.rmtree(video_dir)
    video_dir.mkdir()
    os.environ.pop("DBUS_SESSION_BUS_ADDRESS", None)
    with sync_playwright() as playwright:
        cached = sorted(Path.home().glob(".cache/ms-playwright/chromium-*/chrome-linux/chrome"), reverse=True)
        executable = str(cached[0]) if cached else (shutil.which("chromium") or "/usr/bin/chromium")
        browser = playwright.chromium.launch(executable_path=executable, headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
        context = browser.new_context(viewport={"width": 900, "height": 880}, record_video_dir=str(video_dir), record_video_size={"width": 900, "height": 880})
        page = context.new_page()
        page.goto(html.as_uri(), wait_until="load")
        page.wait_for_function("window.ready === true && document.querySelector('video').readyState >= 2")
        page.screenshot(path=str(WORKDIR / "browser-playback-start.png"))
        time.sleep(12.0)
        page.screenshot(path=str(WORKDIR / "browser-playback-after-two-loops.png"))
        video = page.video
        page.close()
        context.close()
        browser.close()
        recorded = Path(video.path())
    target = WORKDIR / "browser-source-playback-2plus-loops.webm"
    shutil.copyfile(recorded, target)
    shutil.rmtree(video_dir)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(target), "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(WORKDIR / "browser-source-playback-2plus-loops.mp4")], check=True, timeout=120)
    return {"webm": target.name, "webm_sha256": sha256(target), "capture_seconds": 12.0, "covers_more_than_two_source_loops": True}


def main() -> None:
    files = sorted(FRAMES.glob("frame-*.png"))
    if len(files) != 124:
        raise RuntimeError(f"expected 124 native frames, got {len(files)}")
    with Image.open(files[0]) as opened:
        if opened.size != (768, 768):
            raise RuntimeError("unexpected native frame dimensions")
        background = opened.convert("RGB").getpixel((0, 0))
    records = [foreground_record(path, background) for path in files]
    bounds = [record["bbox"] for record in records if record["bbox"] is not None]
    if len(bounds) != len(files):
        raise RuntimeError("foreground missing in one or more frames")

    motion = []
    for left_path, right_path in zip(files, files[1:]):
        with Image.open(left_path) as left_opened, Image.open(right_path) as right_opened:
            left = left_opened.convert("L").resize((96, 96), Image.Resampling.BILINEAR)
            right = right_opened.convert("L").resize((96, 96), Image.Resampling.BILINEAR)
            motion.append(mean(ImageChops.difference(left, right).getdata()) / 255.0)
    source_sequence = {
        "source_video": "provider-original.mp4",
        "source_video_sha256": sha256(WORKDIR / "provider-original.mp4"),
        "native_fps": 24,
        "frame_count": len(files),
        "frames": [
            {"native_index": index, "timestamp_seconds": index / 24, "file": path.relative_to(WORKDIR).as_posix(), "sha256": sha256(path), "foreground": records[index]}
            for index, path in enumerate(files)
        ],
    }
    dump(WORKDIR / "source-frame-sequence.json", source_sequence)
    extents = {
        "method": "fixed first-frame corner RGB with Euclidean threshold 35; framing/clipping diagnostic only",
        "identity_specific_orientation_claimed": False,
        "canvas": [768, 768],
        "aspect_ratio": "1:1",
        "frame_count": len(files),
        "bbox_extrema": {
            "left_min": min(box[0] for box in bounds), "left_max": max(box[0] for box in bounds),
            "top_min": min(box[1] for box in bounds), "top_max": max(box[1] for box in bounds),
            "right_min": min(box[2] for box in bounds), "right_max": max(box[2] for box in bounds),
            "bottom_min": min(box[3] for box in bounds), "bottom_max": max(box[3] for box in bounds),
        },
        "edge_touch_frames": [index for index, record in enumerate(records) if record["edge_touch"]],
        "body_height_range": [min(record["height"] for record in records), max(record["height"] for record in records)],
        "body_center_x_range": [min(record["center_x"] for record in records), max(record["center_x"] for record in records)],
        "body_bottom_range": [min(record["bottom"] for record in records), max(record["bottom"] for record in records)],
        "adjacent_motion_mean": mean(motion),
        "adjacent_motion_max": max(motion),
        "static_rejected": mean(motion) < 0.001,
        "visual_quality_certified": False,
    }
    dump(WORKDIR / "body-extents-and-motion.json", extents)
    indices = [round(index * (len(files) - 1) / 11) for index in range(12)]
    contact_sheet(files, indices, WORKDIR / "contact-sheet-12-native.png")

    analysis = animation_review.analyze_candidates(WORKDIR, "native-source-muted.mp4")
    analysis["analyzer_caveat"] = "Head-region skin thresholds were tuned on the prior identity/background and are not universal; an orientation rejection from this signal is reported separately and is not automatic visual certification."
    dump(WORKDIR / "source-candidate-analysis.json", analysis)
    browser = browser_recording()
    dump(WORKDIR / "browser-playback-evidence.json", browser)
    print(json.dumps({
        "frame_count": len(files),
        "edge_touch_frames": len(extents["edge_touch_frames"]),
        "motion_mean": extents["adjacent_motion_mean"],
        "analysis_status": analysis["status"],
        "candidate_count": len(analysis["candidates"]),
        "hard_failures": analysis["hard_failures"],
        "browser": browser,
    }, indent=2))


if __name__ == "__main__":
    main()
