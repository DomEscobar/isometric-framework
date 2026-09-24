#!/usr/bin/env python3
"""Build the bounded zero-cost export-motion-03 diagnostic."""
from __future__ import annotations

import hashlib
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import pipeline
import quality_gates

RUN = ROOT / "artifacts/live-e2e-20260920T223050Z-91b811"
OUT = RUN / "export-motion-03"
INVENTORY = OUT / "cache-inventory.json"
SOURCE_SHA256 = "2ca54f300087f790fbc02f1e938ff979700a9e52077da07eff96c33fb6e4e18e"
OLD_ROOT = Path("/root/games/waldlicht/art/character-motion/ne-cutout-01")
LIVE_JOB = RUN / "private-service-data/jobs/e0f2fc10ee3949ce89b31dd5d4444c86"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def pack_candidate(label: str, records: list[dict], fps: float, cycle_end: int) -> dict:
    target = OUT / label
    reset_dir(target)
    source_names = []
    cutout_names = []
    provenance = []
    for order, record in enumerate(records):
        source_name = f"source-frame-{order:04d}.png"
        cutout_name = f"cutout-frame-{order:04d}.png"
        source_path = Path(record["source_file"])
        cutout_path = Path(record["cutout_file"])
        shutil.copyfile(source_path, target / source_name)
        shutil.copyfile(cutout_path, target / cutout_name)
        source_names.append(source_name)
        cutout_names.append(cutout_name)
        provenance.append({
            "order": order,
            "native_source_index": record["native_source_index"],
            "timestamp_seconds": record["native_source_index"] / 30.0,
            "source_frame_sha256": sha256(target / source_name),
            "cutout_sha256": sha256(target / cutout_name),
            "cache": record["cache"],
            "cache_order": record["cache_order"],
        })
    gate = quality_gates.evaluate_motion_sequence(
        target,
        source_names,
        native_indices=[item["native_source_index"] for item in records],
        native_fps=30.0,
        cycle_end_exclusive=cycle_end,
        expected_facing="ne",
    )
    write_json(target / "motion-gate.json", gate)
    write_json(target / "frame-provenance.json", {
        "version": 1,
        "source_video_sha256": SOURCE_SHA256,
        "mapping": "unique exact RGB pixel match to native ffmpeg decode",
        "frames": provenance,
    })
    pack = pipeline.run_stage("pack", target, {
        "inputs": cutout_names,
        "image_id": f"keeper-walk-ne-{label}",
        "action": "walk",
        "direction": "ne",
        "fps": fps,
        "loop": True,
        "canvas": {"width": 80, "height": 80},
        "target_visible_height": 58,
        "target_root": {"x": 40, "y": 72},
        "anchor": {"x": 0.5, "y": 0.9},
        "gutter": 2,
        "columns": 8,
        "resample": "lanczos",
        "cleanup": {"recipe": "conservative-alpha-fringe-v1", "minimum_visible_alpha": 8},
    })
    write_json(target / "pack-invocation-result.json", pack)
    return {"label": label, "directory": target, "records": records, "gate": gate, "fps": fps}


def frame_from_atlas(candidate: dict, order: int) -> Image.Image:
    manifest = json.loads((candidate["directory"] / "atlas-manifest.json").read_text())
    frame = manifest["frames"][order]
    rect = frame["rect"]
    with Image.open(candidate["directory"] / "atlas.png") as opened:
        atlas = opened.convert("RGBA")
    image = atlas.crop((rect["x"], rect["y"], rect["x"] + rect["width"], rect["y"] + rect["height"]))
    atlas.close()
    return image


def comparison_board(old: dict, bad: dict, scale: int, target: Path) -> None:
    cell = 80 * scale
    columns = 10
    label_height = 34 * scale
    rows_old = 2
    rows_bad = 1
    width = columns * cell
    height = label_height * 2 + (rows_old + rows_bad) * cell
    board = Image.new("RGB", (width, height), (21, 27, 31))
    draw = ImageDraw.Draw(board)
    font = ImageFont.load_default(size=max(10, 10 * scale))
    y = 0
    for candidate, title, rows in (
        (old, "HISTORICAL 20 — REJECTED: orientation/loop", rows_old),
        (bad, "BAD 10 — REJECTED: sparse/orientation/loop", rows_bad),
    ):
        draw.rectangle((0, y, width, y + label_height), fill=(31, 39, 44))
        draw.text((8 * scale, y + 8 * scale), title, fill="white", font=font)
        y += label_height
        for order, record in enumerate(candidate["records"]):
            frame = frame_from_atlas(candidate, order)
            if scale != 1:
                frame = frame.resize((cell, cell), Image.Resampling.NEAREST)
            x = (order % columns) * cell
            row_y = y + (order // columns) * cell
            background = (237, 237, 232) if order % 2 == 0 else (16, 75, 78)
            tile = Image.new("RGBA", (cell, cell), (*background, 255))
            tile.alpha_composite(frame)
            board.paste(tile.convert("RGB"), (x, row_y))
            draw.text((x + 2 * scale, row_y + 2 * scale), f"n{record['native_source_index']}", fill=(255, 214, 72), font=font)
            tile.close()
            frame.close()
        y += rows * cell
    board.save(target)
    board.close()


def player_html(old: dict, bad: dict) -> str:
    old_manifest = json.loads((old["directory"] / "atlas-manifest.json").read_text())
    bad_manifest = json.loads((bad["directory"] / "atlas-manifest.json").read_text())
    old_atlas = "data:image/png;base64," + base64.b64encode((old["directory"] / "atlas.png").read_bytes()).decode("ascii")
    bad_atlas = "data:image/png;base64," + base64.b64encode((bad["directory"] / "atlas.png").read_bytes()).decode("ascii")
    return f"""<!doctype html><meta charset=utf-8><title>export-motion-03 rejected cache comparison</title>
<style>body{{margin:0;background:#151b1f;color:#fff;font:16px sans-serif}} h1{{font-size:18px;margin:14px}} .row{{display:flex;gap:36px;margin:20px;align-items:start}} .panel{{text-align:center}} canvas{{display:block;margin:8px auto;image-rendering:pixelated;background:#104b4e}} .note{{max-width:820px;margin:14px;color:#ffd648}}</style>
<h1>export-motion-03 — diagnostic only, both candidates rejected</h1><div class=row>
<div class=panel>Historical cached 20 @ 12 fps<canvas id=old width=80 height=80 style="width:320px;height:320px"></canvas></div>
<div class=panel>Previous bad 10 @ {bad['fps']:.6f} fps<canvas id=bad width=80 height=80 style="width:320px;height:320px"></canvas></div></div>
<div class=note>Not a final export. Automatic source analysis found no complete fixed-NE loop; this playback exposes the rotation and restart rather than hiding it.</div>
<script>
const clips={{old:{{manifest:{json.dumps(old_manifest)},src:{json.dumps(old_atlas)}}},bad:{{manifest:{json.dumps(bad_manifest)},src:{json.dumps(bad_atlas)}}}}};
window.renderedClips=0;
for(const [id,clip] of Object.entries(clips)){{const image=new Image(); image.onload=()=>{{const canvas=document.getElementById(id),ctx=canvas.getContext('2d');ctx.imageSmoothingEnabled=false;const start=performance.now();let counted=false;function tick(now){{const frames=clip.manifest.frames,fps=clip.manifest.clip.fps,index=Math.floor(Math.max(0,now-start)*fps/1000)%frames.length,r=frames[index].rect;ctx.clearRect(0,0,80,80);ctx.drawImage(image,r.x,r.y,r.width,r.height,0,0,80,80);if(!counted){{counted=true;window.renderedClips++}}requestAnimationFrame(tick)}}requestAnimationFrame(tick)}};image.src=clip.src}}
</script>"""


def record_browser(html: Path, duration_seconds: float) -> None:
    from playwright.sync_api import sync_playwright
    cached = sorted(Path.home().glob(".cache/ms-playwright/chromium-*/chrome-linux/chrome"), reverse=True)
    executable = str(cached[0]) if cached else (shutil.which("chromium") or "/usr/bin/chromium")
    video_dir = OUT / "browser-video"
    reset_dir(video_dir)
    os.environ.pop("DBUS_SESSION_BUS_ADDRESS", None)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=executable, headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
        context = browser.new_context(viewport={"width": 900, "height": 520}, record_video_dir=str(video_dir), record_video_size={"width": 900, "height": 520})
        page = context.new_page()
        browser_errors = []
        page.on("pageerror", lambda error: browser_errors.append(str(error)))
        page.goto(html.as_uri(), wait_until="load")
        page.wait_for_timeout(1000)
        rendered = page.evaluate("window.renderedClips")
        if rendered != 2:
            raise RuntimeError(f"browser player rendered {rendered!r} clips; errors={browser_errors!r}")
        page.wait_for_timeout(200)
        page.screenshot(path=str(OUT / "manifest-player-browser.png"))
        page.wait_for_timeout(round(duration_seconds * 1000))
        video = page.video
        context.close()
        if video is None:
            raise RuntimeError("browser video was not created")
        video.save_as(str(OUT / "diagnostic-browser-comparison-3loops.webm"))
        browser.close()
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-i", str(OUT / "diagnostic-browser-comparison-3loops.webm"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(OUT / "diagnostic-browser-comparison-3loops.mp4"),
    ], check=True)
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-i", str(OUT / "diagnostic-browser-comparison-3loops.mp4"),
        "-vf", "fps=2,scale=450:260,tile=4x3", "-frames:v", "1",
        str(OUT / "diagnostic-browser-comparison-filmstrip.png"),
    ], check=True)


def main() -> int:
    inventory = json.loads(INVENTORY.read_text())
    if inventory["source"]["sha256"] != SOURCE_SHA256:
        raise RuntimeError("inventory source hash mismatch")
    by_cache = {}
    for record in inventory["records"]:
        by_cache.setdefault(record["cache"], []).append(record)
    old_records = sorted(by_cache["waldlicht-ne-cutout-01"], key=lambda item: item["native_source_index"])
    bad_records = sorted(by_cache["service-live-e2e"], key=lambda item: item["native_source_index"])
    old_source = OLD_ROOT / "original-selected-frames"
    for record in old_records:
        record["source_file"] = str(old_source / f"frame-{record['cache_order']:04d}.png")
    for record in bad_records:
        record["source_file"] = str(LIVE_JOB / f"selected-frame-{record['cache_order']:04d}.png")
    historical = pack_candidate("historical-20-rejected", old_records, 12.0, 66)
    bad = pack_candidate("known-bad-10-rejected", bad_records, 10 / (47 / 30), 75)
    comparison_board(historical, bad, 1, OUT / "old20-vs-bad10-native1x.png")
    comparison_board(historical, bad, 4, OUT / "old20-vs-bad10-labelled4x.png")
    html = OUT / "manifest-player-rejected-comparison.html"
    html.write_text(player_html(historical, bad), encoding="utf-8")
    record_browser(html, 3 * max(20 / 12, 47 / 30) + 0.5)

    analysis = json.loads((OUT / "source-candidate-analysis-v2.json").read_text())
    alternatives = [{
        "rank": index + 1,
        "bounds": [item["start_source_frame_index"], item["end_source_frame_index"]],
        "duration_seconds": item["duration_seconds"],
        "rejection_reasons": item["local_rejection_reasons"],
        "orientation": item["source_pose_orientation"],
        "loop_pose_difference_ratio": item["loop_pose_difference_ratio"],
    } for index, item in enumerate(analysis["rejected_candidates"][:10])]
    summary = {
        "version": 1,
        "status": "blocked_source_quality",
        "source_video_sha256": SOURCE_SHA256,
        "automatic_source_analysis": {
            "status": analysis["status"],
            "hard_failures": analysis["hard_failures"],
            "accepted_candidate_count": len(analysis["candidates"]),
            "ranked_rejected_alternatives": alternatives,
        },
        "cached_inventory": {
            "total_records": len(inventory["records"]),
            "historical_12fps_native_indices": [item["native_source_index"] for item in old_records],
            "service_native_indices": [item["native_source_index"] for item in bad_records],
        },
        "local_gates": {
            "historical_20": historical["gate"],
            "known_bad_10": bad["gate"],
        },
        "new_paid_calls": 0,
        "ledger_changed": False,
        "final_sprite_export_created": False,
        "reason": "No complete gait cycle in the cached source remains at a consistent NE orientation. Packing more cached poses would preserve the facing rotation and cannot produce a clean loop.",
    }
    write_json(OUT / "motion-selection-summary.json", summary)

    archive = OUT / "export-motion-03-diagnostic.zip"
    members = [
        "cache-inventory.json", "source-candidate-analysis-v2.json", "known-bad-10-motion-gate.json",
        "motion-selection-summary.json", "old20-vs-bad10-native1x.png", "old20-vs-bad10-labelled4x.png",
        "manifest-player-rejected-comparison.html", "diagnostic-browser-comparison-3loops.webm",
        "diagnostic-browser-comparison-3loops.mp4", "manifest-player-browser.png",
        "diagnostic-browser-comparison-filmstrip.png",
        "historical-20-rejected/atlas.png", "historical-20-rejected/atlas-manifest.json",
        "historical-20-rejected/motion-gate.json", "historical-20-rejected/frame-provenance.json",
        "known-bad-10-rejected/atlas.png", "known-bad-10-rejected/atlas-manifest.json",
        "known-bad-10-rejected/motion-gate.json", "known-bad-10-rejected/frame-provenance.json",
    ]
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for name in members:
            output.write(OUT / name, name)
    hashes = {name: sha256(OUT / name) for name in members}
    hashes[archive.name] = sha256(archive)
    write_json(OUT / "artifact-hashes.json", hashes)
    print(json.dumps({
        "status": summary["status"],
        "historical_gate": historical["gate"]["rejection_reasons"],
        "bad_gate": bad["gate"]["rejection_reasons"],
        "archive": str(archive),
        "archive_sha256": hashes[archive.name],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
