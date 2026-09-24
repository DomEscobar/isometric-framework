#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "review/minimax-480p-3s-punch-01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(path: Path, count: bool = False) -> dict:
    command = ["ffprobe", "-v", "error"]
    if count:
        command.append("-count_frames")
    command += [
        "-select_streams", "v:0", "-show_entries",
        "stream=width,height,avg_frame_rate,nb_frames,nb_read_frames:format=duration",
        "-of", "json", str(path),
    ]
    return json.loads(subprocess.run(command, check=True, capture_output=True, text=True, timeout=30).stdout)


def main() -> int:
    manifest = json.loads((OUT / "atlas-160-manifest.json").read_text(encoding="utf-8"))
    with Image.open(OUT / "atlas-160.png") as opened:
        atlas = opened.convert("RGBA")
    proofs = {}
    for name, color in {"light": (238, 239, 234), "dark": (25, 29, 34), "petrol": (18, 68, 72)}.items():
        board = Image.new("RGB", (640, 320), color)
        for index, frame in enumerate(manifest["frames"]):
            rect = frame["rect"]
            sprite = atlas.crop((rect["x"], rect["y"], rect["x"] + 160, rect["y"] + 160))
            background = Image.new("RGBA", sprite.size, color + (255,))
            background.alpha_composite(sprite)
            board.paste(background.convert("RGB"), ((index % 4) * 160, (index // 4) * 160))
            sprite.close()
            background.close()
        path = OUT / f"proof-grid-160-{name}-4x2.png"
        board.save(path)
        board.close()
        proofs[name] = {"file": path.name, "sha256": sha(path)}
    atlas.close()
    with zipfile.ZipFile(OUT / "spatial-export.zip") as archive:
        spatial_zip = {"crc_error": archive.testzip(), "entry_count": len(archive.namelist())}
    with zipfile.ZipFile(OUT / "api-job-download.zip") as archive:
        api_zip = {"crc_error": archive.testzip(), "entry_count": len(archive.namelist())}
    removal = json.loads((OUT / "remove-background-state.json").read_text(encoding="utf-8"))
    result = {
        "source_probe": probe(OUT / "source-video.mp4"),
        "preview_probe": probe(OUT / "preview-160-native-petrol-repeated-3x.mp4", count=True),
        "clip": manifest["clip"],
        "proofs": proofs,
        "spatial_zip": spatial_zip,
        "api_zip": api_zip,
        "removal": {
            "count": len(removal["items"]),
            "configured_maximum_inflight": removal.get("maximum_inflight"),
            "observed_maximum_inflight": removal.get("observed_maximum_inflight"),
            "statuses": [item["status"] for item in removal["items"]],
        },
    }
    (OUT / "parent-verification.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
