"""Decode a candidate and make a light/dark/magenta contact sheet; never edit it."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

MAX_PIXELS = 16_000_000


def inspect(source, expected_size=None):
    source = Path(source)
    with Image.open(source) as decoded:
        if decoded.width * decoded.height > MAX_PIXELS:
            raise ValueError("Image exceeds the 16 million pixel inspection limit")
        decoded.load()
        original_mode = decoded.mode
        original_format = decoded.format
        explicit_alpha = "A" in decoded.getbands() or "transparency" in decoded.info
        rgba = decoded.convert("RGBA")
    alpha = rgba.getchannel("A")
    histogram = alpha.histogram()
    total = rgba.width * rgba.height
    bounds = alpha.getbbox()  # All nonzero alpha, right/bottom exclusive.
    cutout = histogram[0] > 0 and sum(histogram[1:]) > 0
    size_matches = expected_size is None or tuple(expected_size) == rgba.size
    result = {
        "source": str(source),
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "format": original_format,
        "mode": original_mode,
        "width": rgba.width,
        "height": rgba.height,
        "explicit_alpha": explicit_alpha,
        "alpha_min": alpha.getextrema()[0],
        "alpha_max": alpha.getextrema()[1],
        "transparent_pixels": histogram[0],
        "partial_alpha_pixels": sum(histogram[1:255]),
        "opaque_pixels": histogram[255],
        "transparent_fraction": histogram[0] / total,
        "nonzero_alpha_bounds": bounds,
        "touches_canvas_edge": bool(bounds and (
            bounds[0] == 0 or bounds[1] == 0 or
            bounds[2] == rgba.width or bounds[3] == rgba.height)),
        "has_cutout_alpha": cutout,
        "expected_size": expected_size,
        "size_matches": size_matches,
        "scope": "decoded-alpha-only",
        "visual_quality": "unverified",
    }
    return result, rgba


def comparison(rgba):
    """Three backgrounds, same unscaled source pixels; labels outside the image."""
    label_height = 24
    board = Image.new("RGB", (rgba.width * 3, rgba.height + label_height), "white")
    draw = ImageDraw.Draw(board)
    for index, (name, color) in enumerate([
        ("LIGHT", (240, 240, 235)),
        ("DARK", (25, 30, 35)),
        ("MAGENTA", (220, 40, 180)),
    ]):
        background = Image.new("RGBA", rgba.size, (*color, 255))
        background.alpha_composite(rgba)
        board.paste(background.convert("RGB"), (rgba.width * index, label_height))
        draw.text((rgba.width * index + 4, 5), name, fill="black")
    return board


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output_directory", type=Path, help="New directory; refuses existing paths")
    parser.add_argument("--require-cutout", action="store_true")
    parser.add_argument("--expect-size", type=int, nargs=2, metavar=("WIDTH", "HEIGHT"))
    args = parser.parse_args()
    result, rgba = inspect(args.input, args.expect_size)
    # New directory avoids overwriting either an original or earlier evidence.
    args.output_directory.mkdir(parents=True, exist_ok=False)
    (args.output_directory / "alpha.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")
    comparison(rgba).save(args.output_directory / "backgrounds.png")
    print(json.dumps(result, indent=2))
    return 1 if (args.require_cutout and not result["has_cutout_alpha"]) or not result["size_matches"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
