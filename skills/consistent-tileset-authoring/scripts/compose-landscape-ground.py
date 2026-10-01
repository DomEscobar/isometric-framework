"""Deterministically compose host-defined contacts and object underlays onto a packed ground surface."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops


MAX_AXIS, MAX_PIXELS, MAX_BYTES = 8192, 16_000_000, 64 * 1024 * 1024
ORIENTATIONS = {"north", "east", "south", "west", "northEast", "northWest", "southEast", "southWest"}


def fail(message): raise ValueError(message)
def sha(data): return hashlib.sha256(data).hexdigest()
def stable(value): return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
def obj(value, name, allowed):
    if not isinstance(value, dict) or set(value) - set(allowed): fail(f"{name} must contain only: {', '.join(allowed)}")
    return value
def integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high: fail(f"{name} must be an integer between {low} and {high}")
    return value
def local(root, value, name):
    if not isinstance(value, str) or not value or Path(value).is_absolute() or "\\" in value or ":" in value: fail(f"{name} must be a local relative path")
    path = (root / value).resolve()
    if not path.is_relative_to(root): fail(f"{name} must stay inside its declared root")
    return path
def bounded_bytes(path, name, cap=MAX_BYTES):
    if not path.is_file() or path.stat().st_size > cap: fail(f"{name} missing or exceeds byte cap")
    try: return path.read_bytes()
    except OSError as exc: raise ValueError(f"{name} could not be read") from exc
def json_file(path, name):
    data = bounded_bytes(path, name, 1024 * 1024)
    try: return data, json.loads(data.decode("utf8"))
    except (UnicodeError, json.JSONDecodeError) as exc: raise ValueError(f"{name} must be valid JSON") from exc
def png(root, value, name, mode=None, size=None):
    path = local(root, value, name)
    data = bounded_bytes(path, name)
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.format != "PNG" or getattr(source, "n_frames", 1) != 1: fail(f"{name} must be a static PNG")
            if max(source.size) > MAX_AXIS or source.width * source.height > MAX_PIXELS: fail(f"{name} exceeds image bounds")
            image = source.convert(mode) if mode else source.copy()
    except (OSError, Image.DecompressionBombError) as exc: raise ValueError(f"{name} is not a valid bounded PNG") from exc
    if size and image.size != size: fail(f"{name} must be {size[0]}x{size[1]}")
    return image, {"path": value, "sha256": sha(data), "dimensions": list(image.size)}
def mask(root, value, name, size):
    image, record = png(root, value, name, "L", size)
    return np.array(image) > 0, record
def scaled(asset, scale, export_scale):
    target = [round(asset.width * scale[0] / export_scale[0]), round(asset.height * scale[1] / export_scale[1])]
    if min(target) < 1 or max(target) > MAX_AXIS: fail("asset scale exceeds image bounds")
    return asset.resize(tuple(target), Image.Resampling.NEAREST), [scale[0] / export_scale[0], scale[1] / export_scale[1]]
def placed_opaque(asset, anchor, asset_anchor, canvas):
    x, y = [anchor[i] - asset_anchor[i] for i in range(2)]; alpha = np.array(asset.convert("RGBA"))[:, :, 3] > 0
    result = np.zeros((canvas[1], canvas[0]), dtype=bool); left, top, right, bottom = max(0, x), max(0, y), min(canvas[0], x + asset.width), min(canvas[1], y + asset.height)
    if left < right and top < bottom: result[top:bottom, left:right] = alpha[top-y:bottom-y, left-x:right-x]
    return result
def dilate(mask, width):
    result = mask.copy()
    for _ in range(width):
        grown = result.copy()
        for dy, dx in ((-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)):
            ys, ye = max(0, -dy), result.shape[0] - max(0, dy); xs, xe = max(0, -dx), result.shape[1] - max(0, dx)
            grown[ys:ye, xs:xe] |= result[ys+dy:ye+dy, xs+dx:xe+dx]
        result = grown
    return result
def alpha_paste(base, asset, anchor, asset_anchor, allowed, strict, occupied=None):
    x, y = [anchor[i] - asset_anchor[i] for i in range(2)]; array = np.array(asset.convert("RGBA")); alpha = array[:, :, 3] > 0
    left, top, right, bottom = max(0, x), max(0, y), min(base.width, x + asset.width), min(base.height, y + asset.height)
    if left >= right or top >= bottom: fail("asset anchor places all opaque pixels outside canvas")
    crop = alpha[top-y:bottom-y, left-x:right-x]
    permitted = allowed[top:bottom, left:right]
    if strict and np.any(crop & ~permitted): fail("asset has opaque pixels outside its declared allowed mask")
    if occupied is not None and np.any(crop & permitted & occupied[top:bottom, left:right]): fail("contact opaque pixels overlap an earlier contact")
    clipped = array[top-y:bottom-y, left-x:right-x].copy(); clipped[:, :, 3] *= permitted.astype(np.uint8)
    layer = Image.new("RGBA", base.size); layer.paste(Image.fromarray(clipped), (left, top))
    base.alpha_composite(layer)
    changed = (crop & permitted).sum()
    if not changed: fail("asset has no opaque pixels in its declared allowed mask")
    if occupied is not None: occupied[top:bottom, left:right] |= crop & permitted
    return int(changed), crop & permitted


def load_surface(recipe_root, surface):
    obj(surface, "surface", ["packedArt", "groundPng"])
    packed_path = local(recipe_root, surface.get("packedArt"), "surface.packedArt")
    packed_bytes, packed = json_file(packed_path, "surface.packedArt")
    if packed.get("version") != 1 or not isinstance(packed.get("groups"), list): fail("surface.packedArt must be packed-art version 1")
    groups = [group for group in packed["groups"] if isinstance(group, dict) and group.get("kind") == "surface"]
    if len(groups) != 1: fail("surface.packedArt must have exactly one surface group")
    composition = groups[0].get("composition")
    if not isinstance(composition, dict) or set(composition) - {"reference", "origin", "sourceScale"}: fail("surface packed composition is invalid")
    origin = composition.get("origin"); scale = composition.get("sourceScale", 1)
    if not isinstance(origin, list) or len(origin) != 2: fail("surface packed composition.origin must be [x,y]")
    origin = [integer(value, "surface origin", -1_000_000, 1_000_000) for value in origin]; integer(scale, "surface sourceScale", 1, 8)
    expected = composition.get("reference")
    if surface.get("groundPng") != expected: fail("surface.groundPng must exactly equal packed composition.reference")
    image, record = png(packed_path.parent, expected, "surface.groundPng", "RGBA")
    return image, {"origin": origin, "sourceScale": scale, "packedArt": sha(packed_bytes), "ground": record, "packedPath": packed_path, "groundPath": local(packed_path.parent, expected, "surface.groundPng")}


def run(recipe_path, out_dir, project_root=None):
    recipe_path, out_dir = Path(recipe_path).resolve(), Path(out_dir).resolve()
    project_root = (Path(project_root) if project_root is not None else recipe_path.parent).resolve()
    input_hashes = {}
    def track(path, data=None):
        if not path.is_relative_to(project_root): fail("every consumed input must stay inside projectRoot")
        input_hashes[path.relative_to(project_root).as_posix()] = sha(bounded_bytes(path, str(path)) if data is None else data)
    if out_dir.exists(): fail("output directory already exists")
    raw, recipe = json_file(recipe_path, "recipe")
    track(recipe_path, raw)
    obj(recipe, "recipe", ["version", "geometrySource", "surface", "regionalMaterials", "regionalPaths", "contacts", "underlays", "protectedMasks"])
    if recipe.get("version") != 1: fail("recipe.version must be 1")
    geometry_declared = recipe.get("geometrySource"); geometry_path = local(recipe_path.parent, geometry_declared, "geometrySource")
    if not geometry_path.is_relative_to(project_root): fail("geometrySource must stay inside projectRoot")
    geometry_report_path = geometry_path.relative_to(project_root).as_posix()
    geometry_bytes, geometry = json_file(geometry_path, "geometrySource")
    track(geometry_path, geometry_bytes)
    obj(geometry, "geometry", ["version", "coordinateSpace", "projection", "origin", "canvas", "masks", "layout", "instances"])
    if geometry.get("version") != 1 or not isinstance(geometry.get("coordinateSpace"), str) or not geometry["coordinateSpace"]: fail("geometry must declare version 1 and coordinateSpace")
    if not isinstance(geometry.get("projection"), str) or not geometry["projection"]: fail("geometry must declare projection")
    origin, canvas = geometry.get("origin"), geometry.get("canvas")
    if not isinstance(origin, list) or len(origin) != 2 or not isinstance(canvas, list) or len(canvas) != 2: fail("geometry origin and canvas are required [x,y]/[width,height]")
    origin = [integer(v, "geometry origin", -1_000_000, 1_000_000) for v in origin]; canvas = [integer(v, "geometry canvas", 1, MAX_AXIS) for v in canvas]
    if canvas[0] * canvas[1] > MAX_PIXELS: fail("geometry canvas exceeds image bounds")
    if not isinstance(geometry.get("masks"), dict) or not geometry["masks"]: fail("geometry.masks must be a nonempty object")
    geometry_root = geometry_path.parent; masks, mask_records = {}, {}
    for key, entry in sorted(geometry["masks"].items()):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", key): fail("geometry mask IDs must be simple identifiers")
        obj(entry, f"geometry.masks.{key}", ["path", "sha256", "semantic"])
        if entry.get("semantic") is not None and entry["semantic"] not in {"road", "water", "land", "contact", "objectGround"}: fail(f"geometry.masks.{key}.semantic is unknown")
        data_path = local(geometry_root, entry.get("path"), f"geometry.masks.{key}.path")
        data = bounded_bytes(data_path, f"geometry.masks.{key}")
        track(data_path, data)
        if entry.get("sha256") != sha(data): fail(f"geometry.masks.{key}.sha256 does not match bytes")
        masks[key], mask_records[key] = mask(geometry_root, entry["path"], f"geometry.masks.{key}", tuple(canvas)); mask_records[key]["sha256"] = sha(data)
    layout = geometry.get("layout")
    obj(layout, "geometry.layout", ["path", "sha256"])
    layout_path = local(geometry_root, layout.get("path"), "geometry.layout.path"); layout_bytes = bounded_bytes(layout_path, "geometry.layout", 1024 * 1024)
    track(layout_path, layout_bytes)
    if layout.get("sha256") != sha(layout_bytes): fail("geometry.layout.sha256 does not match bytes")
    instances = geometry.get("instances")
    if not isinstance(instances, list): fail("geometry.instances must be a list")
    instance_ids = set()
    for entry in instances:
        obj(entry, "geometry instance", ["id", "anchor", "transform", "contactId"])
        ident = entry.get("id")
        if not isinstance(ident, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", ident) or ident in instance_ids: fail("geometry instance IDs must be unique simple identifiers")
        if "contactId" not in entry or (entry["contactId"] is not None and
                (not isinstance(entry["contactId"], str) or not entry["contactId"].strip())):
            fail(f"instance {ident} needs contactId or explicit null for no baked contact")
        instance_ids.add(ident); anchor = entry.get("anchor"); transform = entry.get("transform")
        if not isinstance(anchor, list) or len(anchor) != 2: fail(f"instance {ident} needs anchor [x,y]")
        [integer(v, f"instance {ident} anchor", -MAX_AXIS, MAX_AXIS) for v in anchor]
        obj(transform, f"instance {ident}.transform", ["scale"])
        scale = transform.get("scale")
        if not isinstance(scale, list) or len(scale) != 2 or any(type(v) not in (int, float) or v <= 0 or v > 32 for v in scale): fail(f"instance {ident} needs positive transform.scale [x,y]")
    base, surface_record = load_surface(recipe_path.parent, recipe.get("surface"))
    track(surface_record["packedPath"]); track(surface_record["groundPath"])
    if base.size != tuple(canvas) or surface_record["origin"] != origin: fail("surface dimensions and origin must exactly match geometry canvas and origin")
    material_sources = recipe.get("regionalMaterials")
    if not isinstance(material_sources, dict) or not material_sources: fail("regionalMaterials must be a nonempty object")
    regional_images = {}
    for material, source in sorted(material_sources.items()):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", material): fail("regional material IDs must be simple identifiers")
        regional_images[material], _ = png(recipe_path.parent, source, f"regionalMaterials.{material}", "RGBA", tuple(canvas))
        track(local(recipe_path.parent, source, f"regionalMaterials.{material}"))
    paths = recipe.get("regionalPaths")
    if not isinstance(paths, list) or not paths: fail("regionalPaths must be a nonempty list")
    path_union = np.zeros((canvas[1], canvas[0]), dtype=bool); path_ids = set()
    for item in paths:
        obj(item, "regionalPath", ["id", "mask", "material"]); ident = item.get("id")
        if not isinstance(ident, str) or ident in path_ids or item.get("mask") not in masks or item.get("material") not in regional_images: fail("regionalPaths need unique IDs, geometry masks and regional materials")
        path_ids.add(ident); path_union |= masks[item["mask"]]
    # A four-neighbour exterior of the whole route prevents seams at joins and intersections.
    north = np.zeros_like(path_union); north[1:] = path_union[:-1]
    south = np.zeros_like(path_union); south[:-1] = path_union[1:]
    west = np.zeros_like(path_union); west[:, 1:] = path_union[:, :-1]
    east = np.zeros_like(path_union); east[:, :-1] = path_union[:, 1:]
    exterior = path_union & ~(north & south & west & east)
    result = base.copy()
    for item in paths:
        result_array = np.array(result); source = np.array(regional_images[item["material"]]); selected = masks[item["mask"]]
        result_array[selected] = source[selected]; result = Image.fromarray(result_array)
    contacts = recipe.get("contacts")
    if not isinstance(contacts, list) or not contacts: fail("contacts must be a nonempty list; production cannot silently omit contact art")
    contact_report = []; contact_ids = set(); contact_occupied = np.zeros_like(path_union)
    for item in contacts:
        obj(item, "contact", ["id", "kind", "insideMask", "outsideMask", "allowedMask", "orientation", "edgeWidth", "asset", "anchor", "assetAnchor"])
        ident = item.get("id")
        if not isinstance(ident, str) or ident in contact_ids: fail("contact IDs must be unique strings")
        contact_ids.add(ident)
        if item.get("kind") not in {"pathExterior", "materialPair"}: fail(f"contact {ident} has unknown kind")
        if item.get("orientation") not in ORIENTATIONS: fail(f"contact {ident} has unknown orientation")
        for field in ("insideMask", "outsideMask", "allowedMask"):
            if item.get(field) not in masks: fail(f"contact {ident}.{field} must name a geometry mask")
        anchor = item.get("anchor")
        if not isinstance(anchor, list) or len(anchor) != 2: fail(f"contact {ident}.anchor must be [x,y]")
        anchor = [integer(v, f"contact {ident} anchor", -MAX_AXIS, MAX_AXIS) for v in anchor]
        asset_anchor = item.get("assetAnchor")
        if not isinstance(asset_anchor, list) or len(asset_anchor) != 2: fail(f"contact {ident}.assetAnchor must be [x,y]")
        asset_anchor = [integer(v, f"contact {ident} assetAnchor", 0, MAX_AXIS) for v in asset_anchor]
        edge_width = integer(item.get("edgeWidth"), f"contact {ident}.edgeWidth", 1, 64)
        allowed = masks[item["allowedMask"]]
        if not np.any(allowed & masks[item["insideMask"]]) or not np.any(allowed & masks[item["outsideMask"]]): fail(f"contact {ident} allowed mask must touch both declared materials")
        path_band = None
        if item["kind"] == "pathExterior":
            if not np.any(exterior): fail(f"contact {ident} declares path exterior but regional paths have no exterior")
            band = path_union.copy(); interior = path_union.copy()
            for _ in range(edge_width):
                n = np.zeros_like(interior); n[1:] = interior[:-1]; s = np.zeros_like(interior); s[:-1] = interior[1:]; w = np.zeros_like(interior); w[:, 1:] = interior[:, :-1]; e = np.zeros_like(interior); e[:, :-1] = interior[:, 1:]
                interior &= n & s & w & e
            band &= ~interior
            path_band = band
            if np.any(allowed & path_union & ~band): fail(f"contact {ident} allowed mask reaches an internal regional-path pixel")
            if not np.any(allowed & exterior): fail(f"contact {ident} allowed mask misses the global path exterior")
        vectors = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0), "northEast": (1, -1), "northWest": (-1, -1), "southEast": (1, 1), "southWest": (-1, 1)}
        dx, dy = vectors[item["orientation"]]; inside, outside = masks[item["insideMask"]], masks[item["outsideMask"]]
        shifted = np.zeros_like(outside); ys, ye = max(0, -dy), outside.shape[0] - max(0, dy); xs, xe = max(0, -dx), outside.shape[1] - max(0, dx); shifted[ys:ye, xs:xe] = outside[ys+dy:ye+dy, xs+dx:xe+dx]
        if not np.any(allowed & inside & shifted): fail(f"contact {ident} orientation does not match an inside/outside boundary")
        asset, asset_record = png(recipe_path.parent, item.get("asset"), f"contact {ident}.asset", "RGBA")
        track(local(recipe_path.parent, item["asset"], f"contact {ident}.asset"))
        actual = placed_opaque(asset, anchor, asset_anchor, canvas)
        directional_band = dilate(inside & shifted, edge_width)
        permitted = allowed & directional_band
        if path_band is not None: permitted &= (~path_union | path_band)
        if np.any(actual & ~permitted): fail(f"contact {ident} opaque pixels escape its directional exterior band")
        changed, _ = alpha_paste(result, asset, anchor, asset_anchor, allowed, True, contact_occupied)
        contact_report.append({"id": ident, "kind": item["kind"], "orientation": item["orientation"], "asset": asset_record, "changedPixels": changed})
    protected = np.zeros_like(path_union); protected_ids = recipe.get("protectedMasks")
    if not isinstance(protected_ids, list) or not protected_ids: fail("protectedMasks must name at least one geometry mask")
    for ident in protected_ids:
        if ident not in masks: fail("protectedMasks must name geometry masks")
        protected |= masks[ident]
    if np.any(path_union & ~protected): fail("protectedMasks must cover every regional path mask")
    for ident, entry in geometry["masks"].items():
        if entry.get("semantic") in {"road", "water"} and np.any(masks[ident] & ~protected): fail("protectedMasks must cover every semantic road/water mask")
    before_underlays = np.array(result)
    underlays = recipe.get("underlays", [])
    if not isinstance(underlays, list): fail("underlays must be a list")
    instance_map = {item["id"]: item for item in instances}; underlay_report = []; used_instances = set()
    for item in underlays:
        obj(item, "underlay", ["id", "instanceId", "family", "asset", "assetAnchor", "exportScale", "allowedMask"])
        ident, instance_id = item.get("id"), item.get("instanceId")
        if not isinstance(ident, str) or instance_id not in instance_map or instance_id in used_instances: fail("underlays need unique geometry instance IDs")
        used_instances.add(instance_id)
        if instance_map[instance_id].get("contactId") != ident: fail(f"underlay {ident} must exactly match geometry instance contactId")
        if not isinstance(item.get("family"), str) or not item["family"] or item.get("allowedMask") not in masks: fail(f"underlay {ident} needs family and geometry allowedMask")
        asset_anchor, export_scale = item.get("assetAnchor"), item.get("exportScale")
        if not isinstance(asset_anchor, list) or len(asset_anchor) != 2 or not isinstance(export_scale, list) or len(export_scale) != 2: fail(f"underlay {ident} needs assetAnchor and exportScale [x,y]")
        if any(type(v) is not int or v < 0 for v in asset_anchor) or any(type(v) not in (int, float) or v <= 0 for v in export_scale): fail(f"underlay {ident} has invalid assetAnchor/exportScale")
        allowed = masks[item["allowedMask"]] & ~protected
        asset, asset_record = png(recipe_path.parent, item.get("asset"), f"underlay {ident}.asset", "RGBA")
        track(local(recipe_path.parent, item["asset"], f"underlay {ident}.asset"))
        target_scale = [value * surface_record["sourceScale"] for value in instance_map[instance_id]["transform"]["scale"]]
        asset, factors = scaled(asset, target_scale, export_scale)
        scaled_anchor = [round(asset_anchor[i] * factors[i]) for i in range(2)]
        changed, _ = alpha_paste(result, asset, instance_map[instance_id]["anchor"], scaled_anchor, allowed, False)
        underlay_report.append({"id": ident, "instanceId": instance_id, "family": item["family"], "asset": asset_record, "changedPixels": changed, "scale": instance_map[instance_id]["transform"]["scale"], "surfaceSourceScale": surface_record["sourceScale"], "exportScale": export_scale})
    required_instances = {entry["id"] for entry in instances if entry["contactId"] is not None}
    if used_instances != required_instances:
        fail("underlays must cover every declared instance contactId exactly once")
    after_underlays = np.array(result)
    if not np.array_equal(before_underlays[protected], after_underlays[protected]): fail("underlays changed protected road/water pixels")
    out_dir.mkdir(parents=True, exist_ok=False)
    result.save(out_dir / "ground.png", compress_level=9)
    Image.fromarray((protected * 255).astype(np.uint8)).save(out_dir / "protected-pixels.png", compress_level=9)
    manifest = {"version": 1, "images": {"ground": {"url": "ground.png", "sampling": "nearest", "width": canvas[0], "height": canvas[1]}}, "textures": {"ground": {"image": "ground", "frame": {"x": 0, "y": 0, "width": canvas[0], "height": canvas[1]}, "anchor": {"x": 0, "y": 0}}}, "placements": {"ground": {"x": origin[0], "y": origin[1]}}}
    (out_dir / "manifest.json").write_bytes(stable(manifest))
    packed = {"version": 1, "manifest": "manifest.json", "groups": [{"id": "composed-landscape-ground", "kind": "surface", "textures": ["ground"], "composition": {"reference": "ground.png", "origin": origin, "sourceScale": surface_record["sourceScale"]}}]}
    (out_dir / "packed-art.json").write_bytes(stable(packed))
    surface_report = {key: value for key, value in surface_record.items() if key not in {"packedPath", "groundPath"}}
    report = {"version": 1, "recipeSha256": sha(raw), "inputHashes": dict(sorted(input_hashes.items())), "geometrySource": geometry_report_path, "geometrySha256": sha(geometry_bytes), "coordinateSpace": geometry["coordinateSpace"], "projection": geometry["projection"], "passOrder": ["baseSurface", "regionalContacts", "objectUnderlays"], "surface": surface_report, "masks": mask_records, "layoutSha256": sha(layout_bytes), "contacts": contact_report, "underlays": underlay_report, "protectedPixelReport": {"path": "protected-pixels.png", "sha256": sha((out_dir / "protected-pixels.png").read_bytes()), "protectedPixels": int(protected.sum()), "unchangedAfterUnderlays": True}, "output": {"path": "ground.png", "sha256": sha((out_dir / "ground.png").read_bytes())}}
    (out_dir / "composition-report.json").write_bytes(stable(report))
    provenance = {"version": 1, "algorithm": "host-mask-landscape-compositor-v1", "recipeSha256": sha(raw), "geometrySha256": sha(geometry_bytes), "toolSha256": sha(Path(__file__).read_bytes()), "outputs": {name: sha((out_dir / name).read_bytes()) for name in ["ground.png", "protected-pixels.png", "manifest.json", "packed-art.json", "composition-report.json"]}}
    (out_dir / "provenance.json").write_bytes(stable(provenance))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("recipe"); parser.add_argument("--out", required=True); parser.add_argument("--project-root"); args = parser.parse_args()
    try: run(args.recipe, args.out, args.project_root)
    except ValueError as exc: parser.error(str(exc))
