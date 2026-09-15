#!/usr/bin/env python3
"""Prepare a short video for human-reviewed sprite extraction, then export it.

This deliberately does not infer direction, action, roots, or which frames are
good.  ``prepare`` produces an immutable review bundle and a proposed recipe;
the author fills the selection and clip fields before ``export`` writes equal
PNG cells plus the ordinary sprite-pack.json consumed by pack-sprites.py.
"""

import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
from uuid import uuid4

from PIL import Image, ImageChops, ImageDraw

MAX_SOURCE_BYTES = 256 * 1024 * 1024
MAX_FRAMES = 720
MAX_PIXELS = 16_777_216
MAX_DECODED_PIXELS = 67_108_864
MAX_DURATION_SECONDS = 90
MAX_AXIS = 8192
MARGIN = 4


def fail(message):
    raise ValueError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path, maximum=4 * 1024 * 1024):
    raw = Path(path).read_bytes()
    if len(raw) > maximum:
        fail(f"JSON exceeds {maximum} bytes: {Path(path).name}")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                fail(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: fail(f"invalid JSON number: {value}")), raw


def exact(value, keys, where):
    if not isinstance(value, dict) or set(value) != set(keys):
        fail(f"{where} must have exactly these keys: {', '.join(keys)}")


def finite(value, minimum, maximum, where, integer=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not minimum <= value <= maximum
            or (integer and not isinstance(value, int))):
        fail(f"{where} must be {'an integer' if integer else 'a finite number'} in [{minimum}, {maximum}]")


def parse_key(value):
    if not isinstance(value, str) or len(value) != 7 or value[0] != "#":
        fail("key must be #RRGGBB")
    try:
        return tuple(int(value[index:index + 2], 16) for index in (1, 3, 5))
    except ValueError:
        fail("key must be #RRGGBB")


def relative(base, value, suffix=None):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "\x00" in value:
        fail("paths must be relative forward-slash paths")
    part = PurePosixPath(value)
    if part.is_absolute() or ".." in part.parts or (suffix and part.suffix.lower() != suffix):
        fail(f"invalid relative path: {value}")
    target = (base / Path(*part.parts)).resolve()
    if not target.is_relative_to(base.resolve()):
        fail(f"path escapes review directory: {value}")
    return target


def command(args):
    try:
        return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        fail(f"required executable is not on PATH: {args[0]}")
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip().splitlines()[-1] if error.stderr.strip() else "failed"
        fail(f"{args[0]} failed: {detail}")


def ffmpeg_version():
    return command(["ffmpeg", "-version"]).stdout.splitlines()[0]


def probe(source):
    result = command(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_streams",
                      "-show_frames", "-show_entries",
                      "stream=width,height,duration:frame=best_effort_timestamp_time,media_type",
                      "-of", "json", str(source)])
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    if len(streams) != 1:
        fail("source needs exactly one selected video stream")
    stream = streams[0]
    width, height = stream.get("width"), stream.get("height")
    if not isinstance(width, int) or not isinstance(height, int) or width < 1 or height < 1 or width > MAX_AXIS or height > MAX_AXIS or width * height > MAX_PIXELS:
        fail("video dimensions exceed extraction limits")
    times = []
    for frame in data.get("frames", []):
        if frame.get("media_type") != "video":
            continue
        try:
            time = float(frame["best_effort_timestamp_time"])
        except (KeyError, TypeError, ValueError):
            fail("ffprobe did not provide best_effort_timestamp_time for every video frame")
        if not math.isfinite(time) or (times and time <= times[-1]):
            fail("video frame timestamps must be finite and strictly increasing")
        times.append(time)
    if not times or len(times) > MAX_FRAMES:
        fail(f"video must contain 1 to {MAX_FRAMES} frames")
    try:
        duration = float(stream.get("duration"))
    except (TypeError, ValueError):
        # Some valid variable-frame-rate containers omit stream duration; the
        # decoded PTS range is still enough to keep this review bundle bounded.
        duration = times[-1] - times[0]
    if not math.isfinite(duration) or duration < 0 or duration > MAX_DURATION_SECONDS:
        fail(f"video duration must be finite and at most {MAX_DURATION_SECONDS} seconds")
    if width * height * len(times) > MAX_DECODED_PIXELS:
        fail("decoded video pixels exceed extraction limits")
    return width, height, times


def mask(image, key, tolerance):
    rgba = image.convert("RGBA")
    if key is None:
        return rgba
    # Deliberately a simple maximum per-channel RGB distance. It is documented
    # and reproducible, but does not verify a semantically correct background.
    rgb = rgba.convert("RGB")
    key_image = Image.new("RGB", rgba.size, key)
    difference = ImageChops.difference(rgb, key_image)
    channels = [channel.point(lambda value: 255 if value <= tolerance else 0) for channel in difference.split()]
    keyed = ImageChops.multiply(ImageChops.multiply(channels[0], channels[1]), channels[2])
    inverse = keyed.point(lambda value: 255 - value)
    rgba.putalpha(ImageChops.multiply(rgba.getchannel("A"), inverse))
    rgb.close(); key_image.close(); difference.close()
    for channel in channels:
        channel.close()
    keyed.close(); inverse.close()
    return rgba


def alpha_bounds(path, key, tolerance):
    with Image.open(path) as image:
        rgba = mask(image, key, tolerance)
    bounds = rgba.getchannel("A").getbbox()
    rgba.close()
    return bounds


def proposed_crop(frame_paths, width, height, key, tolerance):
    bounds = None
    for path in frame_paths:
        current = alpha_bounds(path, key, tolerance)
        if current:
            bounds = current if bounds is None else (min(bounds[0], current[0]), min(bounds[1], current[1]), max(bounds[2], current[2]), max(bounds[3], current[3]))
    if bounds is None:
        return {"x": 0, "y": 0, "width": width, "height": height}
    left, top, right, bottom = bounds
    left, top = max(0, left - MARGIN), max(0, top - MARGIN)
    right, bottom = min(width, right + MARGIN), min(height, bottom + MARGIN)
    return {"x": left, "y": top, "width": right - left, "height": bottom - top}


def board(paths, key, tolerance, columns=8, thumb=128, offset=0, backgrounds=False):
    rows = math.ceil(len(paths) / columns)
    image = Image.new("RGBA", (columns * thumb, rows * (thumb + 18)), (24, 27, 33, 255))
    draw = ImageDraw.Draw(image)
    for index, path in enumerate(paths):
        with Image.open(path) as original:
            frame = mask(original, key, tolerance)
        frame.thumbnail((thumb, thumb), Image.Resampling.NEAREST)
        x, y = (index % columns) * thumb, (index // columns) * (thumb + 18)
        fx, fy = x + (thumb - frame.width) // 2, y + (thumb - frame.height) // 2
        if backgrounds:
            for yy in range(y, y + thumb, 16):
                for xx in range(x, x + thumb, 16):
                    draw.rectangle((xx, yy, xx + 15, yy + 15), fill=(238, 238, 238, 255) if ((xx - x) // 16 + (yy - y) // 16) % 2 else (61, 130, 79, 255))
        image.alpha_composite(frame, (fx, fy))
        draw.text((x + 2, y + thumb + 2), str(offset + index), fill=(235, 235, 235, 255))
        frame.close()
    return image


def image_data(image):
    import io
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def preview(title, frames, key, tolerance, output, intervals, loop=True):
    images = []
    for path in frames:
        with Image.open(path) as image:
            images.append(image_data(mask(image, key, tolerance)))
    escaped_title = title.replace("&", "&amp;").replace("<", "&lt;")
    content, timing = json.dumps(images), json.dumps(intervals)
    html = f'''<!doctype html><meta charset="utf-8"><title>{escaped_title}</title>
<style>body{{font:16px system-ui;background:#181b21;color:#eee;margin:24px}}img{{max-width:90vw;max-height:75vh;image-rendering:pixelated;background:conic-gradient(#555 25%,#333 0 50%,#555 0 75%,#333 0) 0/16px 16px}}button{{margin:8px}}</style>
<h1>{escaped_title}</h1><img id="frame" alt="frame preview"><p id="label"></p><button id="previous">Previous</button><button id="toggle">Pause</button><button id="next">Next</button><label> <input id="loop" type="checkbox" checked> Loop</label>
<script>const frames={content},timing={timing};let i=0,playing=true,timer;const image=document.querySelector('#frame'),label=document.querySelector('#label'),loop=document.querySelector('#loop');loop.checked={str(loop).lower()};function show(){{image.src=frames[i];label.textContent=`Frame ${{i+1}} / ${{frames.length}}`;}}function stop(){{clearTimeout(timer);timer=null;}}function advance(){{if(!playing)return;if(i===frames.length-1&&!loop.checked){{playing=false;document.querySelector('#toggle').textContent='Play';return;}}i=(i+1)%frames.length;show();schedule();}}function schedule(){{stop();if(playing)timer=setTimeout(advance,Math.max(1,timing[i]||160));}}function step(n){{stop();playing=false;document.querySelector('#toggle').textContent='Play';i=(i+n+frames.length)%frames.length;show();}}document.querySelector('#previous').onclick=()=>step(-1);document.querySelector('#next').onclick=()=>step(1);document.querySelector('#toggle').onclick=e=>{{playing=!playing;e.target.textContent=playing?'Pause':'Play';if(playing)schedule();else stop();}};show();schedule();</script>'''
    output.write_text(html, encoding="utf-8", newline="\n")


def cycle_suggestions(paths, times):
    # A low-cost visual heuristic, deliberately not an animation decision.
    if len(paths) < 3:
        return []
    samples = []
    for path in paths:
        with Image.open(path) as image:
            sample = image.convert("L").resize((32, 32), Image.Resampling.BILINEAR)
            samples.append(sample)
    candidates = []
    for start in range(min(len(samples) - 2, 48)):
        for end in range(start + 2, min(len(samples), start + 49)):
            duration = times[end] - times[start]
            if duration < .25 or duration > 2:
                continue
            difference = ImageChops.difference(samples[start], samples[end])
            histogram = difference.histogram()
            score = sum(value * count for value, count in enumerate(histogram)) / (32 * 32)
            difference.close()
            candidates.append((score, start, end, duration))
    for sample in samples:
        sample.close()
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    return [{"start": start, "endExclusive": end, "durationSeconds": round(duration, 6), "similarity": round(1 - score / 255, 6),
             "note": "Approximate visual repeat; endpoint is excluded. Review before selecting."}
            for score, start, end, duration in candidates[:3]]


def fresh_output(output):
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        fail(f"output already exists; choose a new directory: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Inherit the workspace's permissions. On Windows, mkdtemp's private ACL
    # can survive publication and hide the review bundle from sandboxed tools.
    staging = output.parent / f".extract-video-{uuid4().hex}"
    staging.mkdir(exist_ok=False)
    return output, staging


def publish(staging, output):
    os.replace(staging, output)


def prepare(source, output, key=None, tolerance=48):
    source = Path(source).resolve()
    if not source.is_file() or source.stat().st_size > MAX_SOURCE_BYTES:
        fail("source must be a regular video within extraction byte limits")
    if key is not None:
        parse_key(key)
    finite(tolerance, 0, 255, "tolerance", integer=True)
    output, staging = fresh_output(output)
    try:
        (staging / "source").mkdir()
        local_source = staging / "source" / source.name
        shutil.copyfile(source, local_source)
        # Decode the copied bytes that the preparation records, not a mutable
        # external source path.
        width, height, times = probe(local_source)
        frames = staging / "frames"
        frames.mkdir()
        command(["ffmpeg", "-v", "error", "-i", str(local_source), "-map", "0:v:0", "-vsync", "0",
                 "-start_number", "0", str(frames / "frame-%06d.png")])
        paths = sorted(frames.glob("frame-*.png"))
        if len(paths) != len(times):
            fail(f"decoded frame count {len(paths)} does not match ffprobe timestamp count {len(times)}")
        for path in paths:
            with Image.open(path) as image:
                if image.size != (width, height):
                    fail("decoded frame dimensions differ from probed stream")
        entries = [{"file": f"frames/{path.name}", "sha256": sha256(path), "timeSeconds": time}
                   for path, time in zip(paths, times)]
        mask_data = {"mode": "none"} if key is None else {"mode": "colorkey", "color": key, "tolerance": tolerance}
        preparation = {"version": 1, "source": {"file": f"source/{source.name}", "sha256": sha256(local_source)},
                       "width": width, "height": height, "decodedFrames": entries, "ffmpegVersion": ffmpeg_version()}
        prep_path = staging / "preparation.json"
        prep_path.write_text(json.dumps(preparation, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
        recipe = {"version": 1, "preparation": {"file": "preparation.json", "sha256": sha256(prep_path)},
                  "crop": proposed_crop(paths, width, height, parse_key(key) if key else None, tolerance),
                  "mask": mask_data, "selection": None, "clip": None}
        # This is the author-edited recipe named by the public workflow.  Its
        # exact shape intentionally has no suggestion fields.
        (staging / "extraction.json").write_text(json.dumps(recipe, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
        review = {"version": 1, "preparation": {"file": "preparation.json", "sha256": recipe["preparation"]["sha256"]},
                  "decodedFrameCount": len(paths), "timestampsStrictlyIncreasing": True,
                  "cycleSuggestions": cycle_suggestions(paths, times)}
        (staging / "review-notes.json").write_text(json.dumps(review, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
        pages = (len(paths) + 63) // 64
        for page in range(pages):
            page_paths = paths[page * 64:(page + 1) * 64]
            contact = board(page_paths, None, tolerance, offset=page * 64)
            contact.save(staging / f"contact-board-{page + 1:03d}.png")
            contact.close()
            if key:
                alpha = board(page_paths, parse_key(key), tolerance, offset=page * 64, backgrounds=True)
                alpha.save(staging / f"alpha-board-{page + 1:03d}.png")
                alpha.close()
        intervals = [max(1, round((times[index + 1] - time) * 1000)) if index + 1 < len(times) else max(1, round((times[-1] - times[-2]) * 1000)) for index, time in enumerate(times)] if len(times) > 1 else [1000]
        preview("Video extraction review (unapproved)", paths, parse_key(key) if key else None, tolerance, staging / "review.html", intervals)
        publish(staging, output)
        return recipe
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def load_recipe(recipe_path):
    recipe_path = Path(recipe_path).resolve()
    recipe, recipe_raw = read_json(recipe_path)
    exact(recipe, ("version", "preparation", "crop", "mask", "selection", "clip"), "recipe")
    if recipe["version"] != 1:
        fail("recipe.version must be 1")
    exact(recipe["preparation"], ("file", "sha256"), "recipe.preparation")
    base = recipe_path.parent.resolve()
    prep_path = relative(base, recipe["preparation"]["file"], ".json")
    if not prep_path.is_file() or sha256(prep_path) != recipe["preparation"]["sha256"]:
        fail("preparation hash does not match")
    preparation, _ = read_json(prep_path)
    exact(preparation, ("version", "source", "width", "height", "decodedFrames", "ffmpegVersion"), "preparation")
    if preparation["version"] != 1:
        fail("preparation.version must be 1")
    exact(preparation["source"], ("file", "sha256"), "preparation.source")
    source = relative(base, preparation["source"]["file"])
    if not source.is_file() or sha256(source) != preparation["source"]["sha256"]:
        fail("prepared source hash does not match")
    for name in ("width", "height"):
        finite(preparation[name], 1, MAX_AXIS, f"preparation.{name}", integer=True)
    exact(recipe["crop"], ("x", "y", "width", "height"), "recipe.crop")
    for name in recipe["crop"]:
        finite(recipe["crop"][name], 0 if name in ("x", "y") else 1, MAX_AXIS, f"recipe.crop.{name}", integer=True)
    crop = recipe["crop"]
    if crop["x"] + crop["width"] > preparation["width"] or crop["y"] + crop["height"] > preparation["height"] or crop["width"] * crop["height"] > MAX_PIXELS:
        fail("recipe.crop is outside the source bounds")
    if crop["width"] > 1024 or crop["height"] > 1024:
        fail("recipe.crop exceeds the packer cell limit of 1024 pixels")
    if not isinstance(recipe["mask"], dict) or recipe["mask"].get("mode") not in ("none", "colorkey"):
        fail("recipe.mask.mode must be none or colorkey")
    if recipe["mask"]["mode"] == "none":
        exact(recipe["mask"], ("mode",), "recipe.mask")
        key, tolerance = None, 0
    else:
        exact(recipe["mask"], ("mode", "color", "tolerance"), "recipe.mask")
        key = parse_key(recipe["mask"]["color"])
        tolerance = recipe["mask"]["tolerance"]
        finite(tolerance, 0, 255, "recipe.mask.tolerance", integer=True)
    frames = preparation["decodedFrames"]
    if not isinstance(frames, list) or not 1 <= len(frames) <= MAX_FRAMES:
        fail("preparation.decodedFrames is invalid")
    paths, times = [], []
    for index, entry in enumerate(frames):
        exact(entry, ("file", "sha256", "timeSeconds"), f"decodedFrames[{index}]")
        path = relative(base, entry["file"], ".png")
        finite(entry["timeSeconds"], -MAX_DURATION_SECONDS, MAX_DURATION_SECONDS * 2, f"decodedFrames[{index}].timeSeconds")
        if times and entry["timeSeconds"] <= times[-1]:
            fail("preparation timestamps are not strictly increasing")
        if not path.is_file() or sha256(path) != entry["sha256"]:
            fail(f"decoded frame hash does not match: {index}")
        paths.append(path); times.append(entry["timeSeconds"])
    return recipe, recipe_raw, preparation, paths, times, key, tolerance, base


def validate_author_choices(recipe, frame_count):
    selection, clip = recipe["selection"], recipe["clip"]
    exact(selection, ("indices", "fps"), "recipe.selection")
    if not isinstance(selection["indices"], list) or not selection["indices"] or len(selection["indices"]) > 256:
        fail("recipe.selection.indices must be a nonempty bounded list")
    for index in selection["indices"]:
        finite(index, 0, frame_count - 1, "recipe.selection.indices", integer=True)
    finite(selection["fps"], .1, 120, "recipe.selection.fps")
    exact(clip, ("imageId", "action", "direction", "loop", "anchor"), "recipe.clip")
    import re
    ident = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
    for key in ("imageId", "action", "direction"):
        if not isinstance(clip[key], str) or not ident.fullmatch(clip[key]) or clip[key] in ("__proto__", "prototype", "constructor"):
            fail(f"recipe.clip.{key} is invalid")
    if clip["direction"] not in ("n", "ne", "e", "se", "s", "sw", "w", "nw") or type(clip["loop"]) is not bool:
        fail("recipe.clip direction or loop is invalid")
    exact(clip["anchor"], ("x", "y"), "recipe.clip.anchor")
    finite(clip["anchor"]["x"], 0, 1, "recipe.clip.anchor.x")
    finite(clip["anchor"]["y"], 0, 1, "recipe.clip.anchor.y")


def export(recipe_path, output):
    recipe, recipe_raw, prep, paths, times, key, tolerance, base = load_recipe(recipe_path)
    validate_author_choices(recipe, len(paths))
    crop = recipe["crop"]
    # A shared crop applies to selected frames only; authors may intentionally
    # omit startup/outlier poses after reviewing the full preparation board.
    rectangle = (crop["x"], crop["y"], crop["x"] + crop["width"], crop["y"] + crop["height"])
    selected = recipe["selection"]["indices"]
    for index in selected:
        path = paths[index]
        bounds = alpha_bounds(path, key, tolerance)
        if not bounds:
            fail("mask leaves an empty frame")
        if bounds[0] < rectangle[0] or bounds[1] < rectangle[1] or bounds[2] > rectangle[2] or bounds[3] > rectangle[3]:
            fail("crop clips visible pixels after masking")
    output, staging = fresh_output(output)
    try:
        frames_dir = staging / "frames"; frames_dir.mkdir()
        output_files = []
        for order, index in enumerate(selected):
            with Image.open(paths[index]) as image:
                rgba = mask(image, key, tolerance).crop(rectangle)
            minimum, maximum = rgba.getchannel("A").getextrema()
            if minimum != 0 or maximum == 0:
                fail("each selected frame must have both visible and transparent pixels after masking")
            name = f"frame-{order:04d}.png"
            rgba.save(frames_dir / name, format="PNG")
            rgba.close()
            output_files.append(f"frames/{name}")
        clip = recipe["clip"]
        spec = {"version": 1, "imageId": clip["imageId"], "cell": {"width": crop["width"], "height": crop["height"]},
                "anchor": clip["anchor"], "requiredDirections": [clip["direction"]], "requiredActions": [clip["action"]],
                "clips": [{"action": clip["action"], "direction": clip["direction"], "fps": recipe["selection"]["fps"], "loop": clip["loop"], "frames": output_files}]}
        (staging / "sprite-pack.json").write_text(json.dumps(spec, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
        provenance = {"version": 1, "source": prep["source"], "preparationSha256": recipe["preparation"]["sha256"],
                      "recipeSha256": hashlib.sha256(recipe_raw).hexdigest(), "selected": [{"sourceIndex": index, "timeSeconds": times[index], "decodedFrameSha256": sha256(paths[index])} for index in selected],
                      "crop": crop, "mask": recipe["mask"]}
        (staging / "provenance.json").write_text(json.dumps(provenance, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
        final_paths = [staging / item for item in output_files]
        alpha = board(final_paths, None, 0, backgrounds=True)
        alpha.save(staging / "alpha-board-001.png"); alpha.close()
        interval = max(1, round(1000 / recipe["selection"]["fps"]))
        preview("Extracted sprite preview (review required)", final_paths, None, 0, staging / "preview.html", [interval] * len(final_paths), clip["loop"])
        publish(staging, output)
        return spec
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("source", type=Path)
    prepare_parser.add_argument("--out", type=Path, required=True)
    prepare_parser.add_argument("--key")
    prepare_parser.add_argument("--tolerance", type=int, default=48)
    export_parser = commands.add_parser("export")
    export_parser.add_argument("recipe", type=Path)
    export_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args.source, args.out, args.key, args.tolerance)
            print(f"Prepared review bundle; fill selection and clip in {args.out / 'extraction.json'}")
        else:
            result = export(args.recipe, args.out)
            print(f"Exported {len(result['clips'][0]['frames'])} selected frames to {args.out}")
    except (ValueError, OSError, Image.DecompressionBombError) as error:
        print(f"extract-video: {error}", file=os.sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
