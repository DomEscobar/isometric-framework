"""Render each band of artwork that leaves its footprint, so the overhang can be classified.

Evidence for a ruling, not a verdict: this script measures and shows, it never decides.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

CHECKER = Path(__file__).resolve().parent / "check-art.mjs"
MAX_PIXELS = 16_000_000
OPAQUE = 8
WIDE, TALL = 420, 520


def measure(contract):
    """Ask the contract checker which columns spill and what they are weighed against."""
    done = subprocess.run(["node", str(CHECKER), str(contract)], capture_output=True, text=True)
    if not done.stdout.strip():
        raise ValueError(f"Contract checker produced no report: {done.stderr.strip()}")
    return json.loads(done.stdout)


def band(frame, asset, side, span):
    """The spilling columns in place, magnified, with the nearest ground contact marked."""
    ground = max(point["source"]["y"] for point in asset["groundPoints"])
    rows = [y for y in range(frame.height)
            for x in range(span["from"], span["to"] + 1) if frame.getpixel((x, y))[3] > OPAQUE]
    if not rows:
        return None
    pad = max(10, span["to"] - span["from"] + 1)
    box = (max(0, span["from"] - pad), max(0, min(rows) - 8),
           min(frame.width, span["to"] + 1 + pad), min(frame.height, max(rows) + 9))
    crop = Image.alpha_composite(Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), (26, 28, 34, 255)),
                                 frame.crop(box))
    scale = min(WIDE / crop.width, (TALL - 44) / crop.height)
    crop = crop.resize((max(1, round(crop.width * scale)), max(1, round(crop.height * scale))), Image.NEAREST)
    tile = Image.new("RGB", (crop.width + 8, crop.height + 48), (20, 22, 27))
    tile.paste(crop.convert("RGB"), (4, 44))
    mark = ImageDraw.Draw(tile)
    contact = 44 + round((ground - box[1]) * scale)
    shown = 44 <= contact < tile.height
    if shown:
        mark.line([0, contact, tile.width, contact], fill=(255, 60, 60))
    for column in (span["from"], span["to"] + 1):
        x = 4 + round((column - box[0]) * scale)
        mark.line([x, 44, x, tile.height], fill=(120, 200, 255))
    clearance = span["groundClearancePx"]
    mark.text((6, 6), f"{asset['id']} {side}: {span['to'] - span['from'] + 1} columns outside the footprint",
              fill=(255, 255, 255))
    where = "red line" if shown else "below this view"
    mark.text((6, 22), "lowest material "
              + ("unmeasured" if clearance is None else f"{clearance:+.1f}px from the ground contact, {where}"),
              fill=(150, 200, 240))
    return tile


def inspect(contract, output_directory):
    report = measure(contract)
    output_directory.mkdir(parents=True, exist_ok=False)
    regions = []
    for asset in report["assets"]:
        overhang = asset.get("overhang")
        if not overhang:
            continue
        with Image.open(asset["imagePath"]) as source:
            if source.width * source.height > MAX_PIXELS:
                raise ValueError(f"{asset['imagePath']} exceeds the 16 million pixel inspection limit")
            box = asset["frame"]
            frame = source.convert("RGBA").crop(
                (box["x"], box["y"], box["x"] + box["width"], box["y"] + box["height"]))
        views = []
        for side, span in overhang["columns"].items():
            if not span:
                continue
            tile = band(frame, asset, side, span)
            if tile is None:
                continue
            name = f"{asset['id']}-{side}.png"
            tile.save(output_directory / name)
            views.append({"side": side, "view": name, "columns": [span["from"], span["to"]],
                          "groundClearancePx": span["groundClearancePx"]})
        regions.append({"asset": asset["id"], "imageSha256": asset["sha256"],
                        "regionSha256": overhang["regionSha256"], "spill": overhang["spill"],
                        "classification": overhang.get("classification"), "bands": views})
    result = {"contract": str(contract), "passed": report["passed"], "regions": regions,
              "scope": "measured-geometry-only", "classification": "not decided here"}
    (output_directory / "overhang.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    parser.add_argument("output_directory", type=Path, help="New directory; refuses existing paths")
    args = parser.parse_args()
    result = inspect(args.contract, args.output_directory)
    print(json.dumps(result, indent=2))
    if not result["regions"]:
        print("No artwork leaves its footprint; no ruling is required.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
