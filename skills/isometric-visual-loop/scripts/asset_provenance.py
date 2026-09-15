"""Verify V4 generated-art provenance against the actual runtime asset binding.

This is a local reproducibility gate.  It verifies bytes and deterministic local
transformations; it deliberately does not authenticate a remote provider or a
renderer.
"""
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path
from PIL import Image, ImageChops


def fail(message):
    raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def local(root, name, exists=True):
    if not isinstance(name, str) or not name or ":" in name or "\\" in name or Path(name).is_absolute():
        fail("Use project-relative forward-slash paths")
    raw = root / name
    if any(item.is_symlink() for item in [raw, *raw.parents]):
        fail("Provenance input leaves project root or uses a symlink")
    path = raw.resolve()
    if not path.is_relative_to(root):
        fail("Provenance input leaves project root or uses a symlink")
    if exists and not path.is_file():
        fail("Missing provenance input: " + name)
    return path


def under_roots(root, path, roots):
    return any(path == local(root, item, exists=False) or path.is_relative_to(local(root, item, exists=False)) for item in roots)


def runtime_file(root, manifest_dir, name, input_roots):
    if not isinstance(name, str) or not name or ":" in name or "\\" in name or Path(name).is_absolute():
        fail("Runtime URLs must be project-relative forward-slash paths")
    raw = manifest_dir / name
    if any(item.is_symlink() for item in [raw, *raw.parents]):
        fail("Runtime URL uses a symlink")
    path = raw.resolve()
    if not path.is_relative_to(root) or not path.is_file() or not under_roots(root, path, input_roots):
        fail("Runtime URL leaves project root, inputRoots or is missing")
    return path


def validate_policy(plan, root, require_files=False):
    policy = plan.get("assetPolicy")
    if not isinstance(policy, dict):
        if plan.get("version") == 4:
            fail("V4 plans require assetPolicy")
        return {"enforced": False, "version": "legacy-v1-v3"}
    required = {"version", "sources", "characterAnimation", "coverageLedger", "runtime"}
    if set(policy) != required or type(policy["version"]) is not int or policy["version"] != 1:
        fail("V4 assetPolicy version 1 requires sources, characterAnimation, coverageLedger and runtime")
    sources = policy["sources"]
    if set(sources) != {"world", "character", "environment"} or any(value != "generated" for value in sources.values()):
        fail("V4 assetPolicy requires generated world, character and environment sources")
    animation = policy["characterAnimation"]
    if animation != {"animated": "image-to-video-extract-pack", "staticIdle": "generated-facing"}:
        fail("V4 characterAnimation requires image-to-video-extract-pack and generated-facing staticIdle")
    runtime = policy["runtime"]
    if not isinstance(runtime, dict) or set(runtime) != {"manifest", "binding"}:
        fail("V4 runtime needs manifest and binding paths")
    for name in (policy["coverageLedger"], runtime["manifest"], runtime["binding"]):
        path = local(root, name, exists=require_files)
        if not under_roots(root, path, plan["inputRoots"]):
            fail("V4 provenance paths must be under inputRoots")
    return {"enforced": True, "version": "v4", "policy": policy}


def _runtime_scope(root, plan, policy):
    manifest_path = local(root, policy["runtime"]["manifest"])
    binding_path = local(root, policy["runtime"]["binding"])
    manifest, binding = read(manifest_path), read(binding_path)
    assets = manifest.get("assets", manifest)
    if not isinstance(assets, dict) or not all(isinstance(assets.get(key), dict) for key in ("images", "textures", "animations")):
        fail("Runtime manifest must expose assets.images, assets.textures and assets.animations")
    if binding.get("version") != 1 or not isinstance(binding.get("used"), dict):
        fail("Runtime binding export version 1 with used categories required")
    categories = ("world", "character", "environment", "ui", "debug")
    if set(binding["used"]) != set(categories):
        fail("Runtime binding must explicitly classify world, character, environment, ui and debug")
    scope = {key: {} for key in categories}
    seen = {kind: set() for kind in ("images", "textures", "animations")}
    for category in categories:
        entry = binding["used"][category]
        if not isinstance(entry, dict) or set(entry) != {"images", "textures", "animations"}:
            fail("Each runtime category needs images, textures and animations")
        for kind, source in (("images", assets["images"]), ("textures", assets["textures"]), ("animations", assets["animations"])):
            values = entry[kind]
            if not isinstance(values, list) or len(values) != len(set(values)) or not all(isinstance(value, str) and value in source for value in values):
                fail(f"Runtime binding {category}.{kind} must name unique manifest IDs")
            overlap = seen[kind].intersection(values)
            if overlap:
                fail("Runtime asset is classified twice: " + sorted(overlap)[0])
            seen[kind].update(values); scope[category][kind] = values
    for kind in seen:
        if seen[kind] != set(assets[kind]):
            fail("Runtime binding must classify every manifest " + kind)
    # Texture/animation references must be internally sound and classified coherently.
    for category, entry in scope.items():
        for texture_id in entry["textures"]:
            image_id = assets["textures"][texture_id].get("image")
            if image_id not in entry["images"]:
                fail("Bound texture image is not in the same category: " + texture_id)
        for clip_id in entry["animations"]:
            frames = assets["animations"][clip_id].get("frames")
            if not isinstance(frames, list) or not frames or any(frame not in entry["textures"] for frame in frames):
                fail("Bound animation frames are not in the same category: " + clip_id)
    return assets, scope, manifest_path, binding_path


def _evidence(root, plan, item, label):
    if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
        fail(label + " needs path and sha256")
    path = local(root, item["path"])
    if not under_roots(root, path, plan["inputRoots"]):
        fail(label + " must be under inputRoots")
    if sha(path) != item["sha256"]:
        fail(label + " hash mismatch")
    return path


def _origin(root, plan, item, label):
    required = {"kind", "record", "output"}
    if not isinstance(item, dict) or not required <= set(item) or set(item) - required - {"prepared"}:
        fail(label + " needs generated kind, record and output evidence")
    if item["kind"] != "generated":
        fail(label + " must name generated origin evidence")
    _evidence(root, plan, item["record"], label + " record")
    output = _evidence(root, plan, item["output"], label + " output")
    record = read(local(root, item["record"]["path"]))
    if not isinstance(record, dict) or record.get("outputSha256") != sha(output) or not any(isinstance(record.get(key), str) and record[key].strip() for key in ("requestId", "jobId", "localJobId")):
        fail(label + " record must bind outputSha256 and a request, job or local job identity")
    if "prepared" in item:
        prepared = item["prepared"]
        if not isinstance(prepared, dict) or set(prepared) != {"image", "mask", "crop"}:
            fail(label + " prepared image needs image, mask and crop")
        result = _evidence(root, plan, prepared["image"], label + " prepared image")
        mask_file = _evidence(root, plan, prepared["mask"], label + " prepared mask")
        crop = prepared["crop"]
        if (not isinstance(crop, dict) or set(crop) != {"x", "y", "width", "height"}
                or any(type(value) is not int for value in crop.values())):
            fail(label + " prepared crop needs integer x, y, width and height")
        with Image.open(output) as raw, Image.open(mask_file) as mask, Image.open(result) as actual:
            x, y, width, height = (crop[key] for key in ("x", "y", "width", "height"))
            if mask.mode != "L" or mask.size != raw.size:
                fail(label + " prepared mask must be grayscale at original dimensions")
            if min(x, y) < 0 or min(width, height) <= 0 or x + width > raw.width or y + height > raw.height:
                fail(label + " prepared crop leaves original image")
            rgba = raw.convert("RGBA")
            rgba.putalpha(ImageChops.multiply(rgba.getchannel("A"), mask))
            expected = rgba.crop((x, y, x + width, y + height))
            if actual.size != expected.size or actual.convert("RGBA").tobytes() != expected.tobytes():
                fail(label + " prepared pixels differ from original mask/crop")
        return result
    return output


HORIZONTAL_PAIRS = {"ne": "nw", "nw": "ne", "se": "sw", "sw": "se", "e": "w", "w": "e"}


def clip_prefix(clip_id, direction):
    suffix = "." + direction
    if not isinstance(clip_id, str) or not clip_id.endswith(suffix) or len(clip_id) <= len(suffix):
        fail("Clip ID does not match declared direction: " + str(clip_id))
    return clip_id[:-len(suffix)]


def _assert_packed_clip(assets, root, plan, manifest_path, clip_id, spec, packed_runtime, packed_dir, direction):
    if len(spec["clips"][0]["frames"]) < 2:
        fail("Animated character clip needs at least two extracted frames: " + clip_id)
    expected_clip = spec["imageId"] + "." + spec["clips"][0]["action"] + "." + direction
    if expected_clip != clip_id or assets["animations"].get(clip_id) != packed_runtime["assets"]["animations"].get(clip_id):
        fail("Packed clip does not match runtime binding: " + clip_id)
    actual_frames = assets["animations"][clip_id]["frames"]
    expected_frames = packed_runtime["assets"]["animations"][clip_id]["frames"]
    for actual_id, expected_id in zip(actual_frames, expected_frames):
        actual, expected = assets["textures"][actual_id], packed_runtime["assets"]["textures"][expected_id]
        if actual.get("anchor") != expected.get("anchor") or actual.get("frame", {}).get("width") != expected["frame"]["width"] or actual.get("frame", {}).get("height") != expected["frame"]["height"]:
            fail("Runtime texture rectangle or anchor differs from extracted frame: " + clip_id)
        runtime_sheet = runtime_file(root, manifest_path.parent, assets["images"][actual["image"]]["url"], plan["inputRoots"])
        with Image.open(runtime_sheet) as sheet, Image.open(packed_dir / "sheet.png") as rebuilt:
            af, ef = actual["frame"], expected["frame"]
            left = sheet.crop((af["x"], af["y"], af["x"] + af["width"], af["y"] + af["height"]))
            right = rebuilt.crop((ef["x"], ef["y"], ef["x"] + ef["width"], ef["y"] + ef["height"]))
            if left.convert("RGBA").tobytes() != right.convert("RGBA").tobytes():
                fail("Packed frame pixels do not match runtime texture: " + clip_id)


def verify(plan, root):
    checked = validate_policy(plan, root, require_files=True)
    if not checked["enforced"]:
        return checked
    policy = checked["policy"]
    assets, scope, manifest_path, binding_path = _runtime_scope(root, plan, policy)
    ledger_path = local(root, policy["coverageLedger"])
    ledger = read(ledger_path)
    if not isinstance(ledger, dict) or set(ledger) != {"version", "images", "clips"} or ledger["version"] != 1:
        fail("Provenance ledger version 1 needs images and clips")
    images, clips = ledger["images"], ledger["clips"]
    if not isinstance(images, dict) or not isinstance(clips, dict):
        fail("Provenance ledger images and clips must be objects")
    required_images = set()
    for category, entry in scope.items():
        if category in policy["sources"]:
            required_images.update(entry["images"])
    if not required_images:
        fail("V4 production runtime binding needs at least one generated world, character or environment image")
    if set(images) != required_images:
        fail("Provenance ledger must cover exactly generated runtime image IDs")
    for image_id in required_images:
        item = images[image_id]
        if not isinstance(item, dict) or set(item) != {"origin", "transforms"}:
            fail("Image ledger entry needs generated origin and transforms: " + image_id)
        _origin(root, plan, item["origin"], "Generated origin " + image_id)
        if not isinstance(item["transforms"], list):
            fail("Image transforms must be a list: " + image_id)
        for index, transform in enumerate(item["transforms"]):
            _evidence(root, plan, transform, f"Image transform {image_id}[{index}]")
        url = assets["images"][image_id].get("url")
        if not isinstance(url, str):
            fail("Runtime image URL missing: " + image_id)
        runtime_image = runtime_file(root, manifest_path.parent, url, plan["inputRoots"])
        # An origin can be transformed, but it must not merely be a self-recorded
        # claim: the runtime image's bytes must be named by the transform endpoint.
        if not item["transforms"] or item["transforms"][-1] != {"path": str(runtime_image.relative_to(root)).replace("\\", "/"), "sha256": sha(runtime_image)}:
            fail("Image transform endpoint must hash the runtime image: " + image_id)
    character_clips = set(scope["character"]["animations"])
    if set(clips) != character_clips:
        fail("Provenance ledger must cover exactly character runtime animated clips")
    extractor = load_script("v4_extract_video", Path(__file__).resolve().parents[2] / "directional-sprite-authoring/scripts/extract-video.py")
    packer = load_script("v4_pack_sprites", Path(__file__).resolve().parents[2] / "directional-sprite-authoring/scripts/pack-sprites.py")
    mirrorer = load_script("v4_mirror_frames", Path(__file__).resolve().parents[2] / "directional-sprite-authoring/scripts/mirror-frames.py")
    extract_clips, mirrored_clips = [], []
    for clip_id in character_clips:
        item = clips[clip_id]
        static = len(assets["animations"][clip_id].get("frames", [])) == 1
        if static and clip_id.split(".")[-2:-1] == ["idle"]:
            if not isinstance(item, dict) or set(item) != {"mode", "selectedImage"} or item["mode"] != "generated-facing":
                fail("Static character idle needs generated-facing ledger mode: " + clip_id)
            selected = _origin(root, plan, item["selectedImage"], "Static generated image " + clip_id)
            texture = assets["textures"][assets["animations"][clip_id]["frames"][0]]
            sheet = runtime_file(root, manifest_path.parent, assets["images"][texture["image"]]["url"], plan["inputRoots"])
            frame = texture["frame"]
            with Image.open(selected) as source, Image.open(sheet) as atlas:
                crop = atlas.crop((frame["x"], frame["y"], frame["x"] + frame["width"], frame["y"] + frame["height"]))
                if source.size != crop.size or source.convert("RGBA").tobytes() != crop.convert("RGBA").tobytes():
                    fail("Static generated facing pixels do not match runtime texture: " + clip_id)
            continue
        if not isinstance(item, dict) or item.get("mode") not in ("image-to-video-extract-pack", "mirrored-frames"):
            fail("Character clip ledger needs mode, selectedImage, videoJob and recipe: " + clip_id)
        if item["mode"] == "mirrored-frames":
            mirrored_clips.append(clip_id)
            continue
        if set(item) != {"mode", "selectedImage", "videoJob", "recipe"}:
            fail("Character clip ledger needs mode, selectedImage, videoJob and recipe: " + clip_id)
        selected = _origin(root, plan, item["selectedImage"], "Selected generated image " + clip_id)
        job = read(_evidence(root, plan, item["videoJob"], "Video job " + clip_id))
        if (not isinstance(job, dict) or job.get("selectedImageSha256") != sha(selected)
                or not all(isinstance(job.get(key), str) and job[key].strip() for key in ("provider", "model"))
                or not any(isinstance(job.get(key), str) and job[key].strip() for key in ("requestId", "jobId", "localJobId"))):
            fail("Video job record must pin the selected image passed to the job: " + clip_id)
        recipe_path = _evidence(root, plan, item["recipe"], "Extraction recipe " + clip_id)
        recipe, _, prep, old_frames, _, _, _, recipe_base = extractor.load_recipe(recipe_path)
        source_video = recipe_base / Path(prep["source"]["file"])
        if not under_roots(root, source_video.resolve(), plan["inputRoots"]):
            fail("Extraction source video must be under inputRoots")
        for frame in old_frames:
            if not under_roots(root, frame.resolve(), plan["inputRoots"]):
                fail("Decoded extraction frame must be under inputRoots")
        if not job.get("videoSha256") == prep["source"]["sha256"]:
            fail("Video job record does not match extraction source video: " + clip_id)
        if recipe.get("clip") is None:
            fail("Extraction recipe must define a clip: " + clip_id)
        extract_clips.append((clip_id, recipe_path, recipe, prep, old_frames, source_video, recipe["selection"]["indices"]))

    for clip_id, recipe_path, recipe, prep, old_frames, source_video, indices in extract_clips:
        with tempfile.TemporaryDirectory(prefix="v4-provenance-") as temp:
            exported = Path(temp) / "extract"; packed = Path(temp) / "pack"
            replay = Path(temp) / "replay"
            extractor.prepare(source_video, replay)
            replay_prep = read(replay / "preparation.json")
            if len(replay_prep["decodedFrames"]) != len(prep["decodedFrames"]):
                fail("Re-decoded video frame count differs from recorded preparation: " + clip_id)
            if [item["timeSeconds"] for item in replay_prep["decodedFrames"]] != [item["timeSeconds"] for item in prep["decodedFrames"]]:
                fail("Re-decoded video timestamps differ from recorded preparation: " + clip_id)
            for index in indices:
                with Image.open(old_frames[index]) as old, Image.open(replay / replay_prep["decodedFrames"][index]["file"]) as fresh:
                    if old.size != fresh.size or old.convert("RGBA").tobytes() != fresh.convert("RGBA").tobytes():
                        fail("Re-decoded video pixels differ from recorded selected frame: " + clip_id)
            spec = extractor.export(recipe_path, exported)
            _assert_packed_clip(assets, root, plan, manifest_path, clip_id, spec, packer.pack(exported / "sprite-pack.json", packed), packed, spec["clips"][0]["direction"])
    for clip_id in mirrored_clips:
        item = clips[clip_id]
        if set(item) != {"mode", "sourceClip", "mirror"}:
            fail("Mirrored character clip needs mode, sourceClip and mirror: " + clip_id)
        source_id = item["sourceClip"]
        if source_id not in {entry[0] for entry in extract_clips}:
            fail("Mirrored clip source must be an extracted character clip: " + clip_id)
        mirror = item["mirror"]
        if not isinstance(mirror, dict) or set(mirror) != {"sourceDirection", "direction"}:
            fail("Mirror plan needs sourceDirection and direction: " + clip_id)
        source_dir, dest_dir = mirror["sourceDirection"], mirror["direction"]
        if HORIZONTAL_PAIRS.get(source_dir) != dest_dir:
            fail("Mirror pair is not a horizontal facing: " + clip_id)
        if clip_prefix(source_id, source_dir) != clip_prefix(clip_id, dest_dir):
            fail("Mirrored clip must keep the source image and action: " + clip_id)
        recipe_path = _evidence(root, plan, clips[source_id]["recipe"], "Extraction recipe " + clip_id)
        with tempfile.TemporaryDirectory(prefix="v4-mirror-") as temp:
            exported = Path(temp) / "extract"; mirrored = Path(temp) / "mirror"; packed = Path(temp) / "pack"
            spec = extractor.export(recipe_path, exported)
            if spec["clips"][0]["direction"] != source_dir:
                fail("Source recipe direction does not match mirror sourceDirection: " + clip_id)
            mirrored_spec = mirrorer.mirror(exported / "sprite-pack.json", mirrored, dest_dir)
            packed_runtime = packer.pack(mirrored / "sprite-pack.json", packed)
            _assert_packed_clip(assets, root, plan, manifest_path, clip_id, mirrored_spec, packed_runtime, packed, dest_dir)
    return {"enforced": True, "version": "v4", "images": len(required_images), "characterClips": len(character_clips),
            "limit": "Local hashes and deterministic transforms verified; remote provider and renderer authenticity are not authenticated."}
