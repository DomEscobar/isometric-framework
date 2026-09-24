#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "minimax-ne-export-final"
COLORS = {"light": (238, 239, 234), "dark": (25, 29, 34), "petrol": (18, 68, 72)}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def composite(sprite: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    background = Image.new("RGBA", sprite.size, color + (255,))
    background.alpha_composite(sprite)
    return background.convert("RGB")


def load_frames(canvas: int) -> tuple[dict, list[Image.Image]]:
    manifest_path = OUT / f"atlas-{canvas}-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    atlas_path = OUT / manifest["image"]["file"]
    if sha256(atlas_path) != manifest["image"]["sha256"]:
        raise RuntimeError(f"{canvas}px atlas hash mismatch")
    with Image.open(atlas_path) as opened:
        atlas = opened.convert("RGBA")
    frames = []
    for expected, record in enumerate(manifest["frames"]):
        if record["order"] != expected or record["id"] != manifest["clip"]["frames"][expected]:
            raise RuntimeError(f"{canvas}px manifest order/id mismatch")
        rect = record["rect"]
        if rect["width"] != canvas or rect["height"] != canvas or rect["x"] < 0 or rect["y"] < 0 or rect["x"] + canvas > atlas.width or rect["y"] + canvas > atlas.height:
            raise RuntimeError(f"{canvas}px frame rectangle invalid")
        frame = atlas.crop((rect["x"], rect["y"], rect["x"] + canvas, rect["y"] + canvas))
        if frame.getchannel("A").getbbox() is None:
            raise RuntimeError(f"{canvas}px blank frame {expected}")
        if any(0 < value < 8 for value in frame.getchannel("A").get_flattened_data()):
            raise RuntimeError(f"{canvas}px alpha 1..7 survived frame {expected}")
        frames.append(frame)
    atlas.close()
    if len(frames) != 24 or len(set(manifest["clip"]["frames"])) != 24:
        raise RuntimeError(f"{canvas}px frame count mismatch")
    return manifest, frames


def make_background_sheet(frames: list[Image.Image], canvas: int, name: str) -> Path:
    columns, rows = 8, 3
    label_height = 24
    board = Image.new("RGB", (columns * canvas, label_height + rows * canvas), (35, 38, 42))
    draw = ImageDraw.Draw(board)
    draw.text((5, 5), f"EXACT {canvas}px atlas frames 0..23 on {name}; native 1:1", fill=(255, 226, 105))
    for order, frame in enumerate(frames):
        rendered = composite(frame, COLORS[name])
        x, y = (order % columns) * canvas, label_height + (order // columns) * canvas
        board.paste(rendered, (x, y))
        draw.text((x + 3, y + 3), str(order), fill=(255, 226, 105))
        rendered.close()
    target = OUT / f"ALL_FRAMES_{canvas}_{name.upper()}.png"
    board.save(target)
    board.close()
    return target


def probe_video(path: Path) -> dict:
    process = subprocess.run([
        "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,avg_frame_rate,nb_read_frames:format=duration",
        "-of", "json", str(path),
    ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
    return json.loads(process.stdout)


def make_encoded_seam() -> Path:
    preview = OUT / "preview-160-native-petrol-3loops.mp4"
    decoded = OUT / ".encoded-seam-frames"
    if decoded.exists():
        for item in decoded.iterdir():
            item.unlink()
    else:
        decoded.mkdir()
    indices = [22, 23, 24, 25, 46, 47, 48, 49]
    expression = "+".join(f"eq(n\\,{index})" for index in indices)
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(preview), "-vf", f"select={expression}",
        "-vsync", "0", str(decoded / "frame-%02d.png"),
    ], check=True, timeout=120)
    board = Image.new("RGB", (8 * 160, 190), (35, 38, 42))
    draw = ImageDraw.Draw(board)
    labels = ["L1 end-1", "L1 end", "L2 first", "L2 first+1", "L2 end-1", "L2 end", "L3 first", "L3 first+1"]
    for order, (index, label) in enumerate(zip(indices, labels), start=1):
        with Image.open(decoded / f"frame-{order:02d}.png") as opened:
            frame = opened.convert("RGB")
        board.paste(frame, ((order - 1) * 160, 0))
        draw.text(((order - 1) * 160 + 3, 163), f"{label} #{index}", fill=(255, 226, 105))
        frame.close()
    target = OUT / "FINAL_ENCODED_SEAM.png"
    board.save(target)
    board.close()
    for item in decoded.iterdir():
        item.unlink()
    decoded.rmdir()
    return target


def provider_state() -> dict:
    ids = []
    statuses = []
    outputs = []
    for directory in (OUT / "private-provider-proof", OUT / "private-provider-remaining"):
        state = json.loads((directory / "remove-background-state.json").read_text(encoding="utf-8"))
        for item in state["items"]:
            ids.append(item["prediction_id"])
            statuses.append(item["status"])
            output = directory / item["output"]["file"]
            if sha256(output) != item["output"]["sha256"]:
                raise RuntimeError("provider cutout hash mismatch")
            outputs.append(sha256(output))
    if len(ids) != 24 or len(set(ids)) != 24 or set(statuses) != {"completed"}:
        raise RuntimeError("provider removal inventory is incomplete or duplicated")
    return {"prediction_count": len(ids), "unique_prediction_count": len(set(ids)), "statuses": sorted(set(statuses)), "output_hashes": outputs, "in_flight": False}


def main() -> int:
    manifests = {}
    evidence = []
    for canvas in (80, 160):
        manifest, frames = load_frames(canvas)
        manifests[str(canvas)] = {
            "atlas_sha256": manifest["image"]["sha256"],
            "manifest_sha256": sha256(OUT / f"atlas-{canvas}-manifest.json"),
            "frame_count": len(frames),
            "fps": manifest["clip"]["fps"],
            "duration_seconds": manifest["clip"]["duration_seconds"],
            "nonblank_frames": len(frames),
            "alpha_1_7_survivors": 0,
        }
        for name in COLORS:
            evidence.append(make_background_sheet(frames, canvas, name))
        for frame in frames:
            frame.close()
    video = {}
    for canvas in (80, 160):
        path = OUT / f"preview-{canvas}-native-petrol-3loops.mp4"
        video[str(canvas)] = {"file": path.name, "sha256": sha256(path), "probe": probe_video(path)}
    seam = make_encoded_seam()
    evidence.append(seam)
    package = OUT / "minimax-ne-transparent-export.zip"
    with zipfile.ZipFile(package) as archive:
        bad = archive.testzip()
        names = archive.namelist()
    if bad is not None or not {"atlas-80.png", "atlas-160.png", "atlas-80-manifest.json", "atlas-160-manifest.json", "preview.html"} <= set(names):
        raise RuntimeError("ZIP integrity/content check failed")
    verification = {
        "status": "passed_technical_and_exact_visual_evidence_created",
        "visual_quality_certified": False,
        "provider": provider_state(),
        "manifests": manifests,
        "encoded_previews": video,
        "zip": {"file": package.name, "sha256": sha256(package), "entry_count": len(names), "testzip": bad},
        "evidence": [{"file": path.name, "sha256": sha256(path)} for path in evidence],
        "checks": ["all 24 manifest rectangles in bounds and nonblank", "all delivered atlas frame alpha excludes 1..7 cleanup band", "all 24 provider IDs unique and completed", "all provider outputs downloaded and hash-matched", "encoded previews decoded by ffprobe", "two encoded loop seams extracted from actual 160px delivery MP4", "ZIP CRC and required entries verified"],
    }
    (OUT / "FINAL_VERIFICATION.json").write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(verification, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
