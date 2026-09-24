#!/usr/bin/env python3
"""Export the user-reviewed MiniMax NE interval without new source generation."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import pipeline

SOURCE_DIR = ROOT / "artifacts" / "minimax-ne-source-01"
SOURCE = SOURCE_DIR / "provider-original.mp4"
CANDIDATE_PATH = SOURCE_DIR / "gait-candidate-previews" / "candidate-01-66-98" / "candidate.json"
OUT = ROOT / "artifacts" / "minimax-ne-export-final"
EXTRACT = OUT / "selected-originals"
PROOF = OUT / "private-provider-proof"
REMAINING = OUT / "private-provider-remaining"
MASTER = OUT / "master-cutouts"
QUOTE_UNIT = 0.004
MAX_SELECTED = 24
STAGE_CAP = 0.50
# Deterministic density sampling across exact inclusive native indices 66..97.
SELECTED = [66, 67, 69, 70, 71, 73, 74, 75, 77, 78, 79, 81, 82, 84, 85, 86, 88, 89, 90, 92, 93, 94, 96, 97]
PROOF_ORDERS = [0, 12, 23]
SOURCE_FPS = 24.0
CYCLE_DURATION = 32 / SOURCE_FPS
PLAYBACK_FPS = len(SELECTED) / CYCLE_DURATION
TRANSFORMS = {
    80: {"scale": 0.11262135922330097, "source_root": [395.5, 652.0], "target_root": [40, 72], "target_visible_height": 58},
    160: {"scale": 0.22524271844660193, "source_root": [395.5, 652.0], "target_root": [80, 144], "target_visible_height": 116},
}
BG = {"light": (238, 239, 234), "dark": (25, 29, 34), "petrol": (18, 68, 72)}


def utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_name("." + path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def load_key() -> str:
    env_path = Path("/root/.hermes/.env")
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        if raw.strip() and not raw.lstrip().startswith("#") and "=" in raw:
            name, value = raw.split("=", 1)
            if name.strip() == "WAVESPEED_API_KEY":
                key = value.strip().strip("\"").strip("'")
                if key:
                    return key
    raise RuntimeError("WaveSpeed credential unavailable")


def validate_scope() -> dict:
    candidate = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    if candidate.get("id") != "candidate-01-66-98" or candidate.get("bounds") != [66, 98] or candidate.get("frame_count") != 32:
        raise RuntimeError("candidate schema/bounds changed")
    if SELECTED != sorted(set(SELECTED)) or len(SELECTED) != MAX_SELECTED or SELECTED[0] != 66 or SELECTED[-1] != 97:
        raise RuntimeError("bounded selected-frame sampling is invalid")
    if not all(66 <= index < 98 for index in SELECTED):
        raise RuntimeError("selected frame leaves reviewed interval")
    if MAX_SELECTED * QUOTE_UNIT > STAGE_CAP:
        raise RuntimeError("maximum selected removal reservation exceeds stage cap")
    return candidate


def initialize() -> None:
    candidate = validate_scope()
    OUT.mkdir(parents=True, exist_ok=True)
    os.chmod(OUT, 0o700)
    report = OUT / "FINAL_EXPORT_REPORT.md"
    if not report.exists():
        report.write_text(
            "# Final MiniMax NE export report\n\n"
            "Status: spatial proof in progress; final export not yet claimed.\n\n"
            "Source review: human-reviewed exact source preview proposed-display-160-3loops.mp4; this is not automatic gate certification.\n"
            f"Candidate: {candidate['id']} native bounds [66,98), source background retained only in the reviewed source preview.\n"
            "Final delivery preview will be rendered from transparent provider cutouts, not from the source background.\n",
            encoding="utf-8",
        )
    quote = {
        "model_id": "wavespeed-ai/image-background-remover",
        "fetched_at_utc": "2026-09-21T05:17:06Z",
        "price": QUOTE_UNIT,
        "discounted_price": QUOTE_UNIT,
        "currency": "USD",
        "estimate": True,
        "unpriced_inputs": [],
        "required": ["image"],
        "balance_verified_usd": 15.33,
    }
    write_json(OUT / "fresh-remover-quote.json", quote)
    prior = json.loads((SOURCE_DIR / "cost-ledger.json").read_text(encoding="utf-8"))
    ledger_path = OUT / "cost-ledger.json"
    if not ledger_path.exists():
        reserve = MAX_SELECTED * QUOTE_UNIT
        ledger = {
            "version": 1,
            "currency": "USD",
            "authorization": prior["authorization"],
            "cumulative_prior_maximum_accounted_usd": prior["maximum_accounted_with_reservation_usd"],
            "stage_cap_usd": STAGE_CAP,
            "entries": [{
                "id": "minimax-ne-selected-removals",
                "model": quote["model_id"],
                "selected_frame_count_maximum": MAX_SELECTED,
                "unit_quote_usd": QUOTE_UNIT,
                "reserved_worst_case_usd": reserve,
                "status": "reserved_before_first_submission",
                "provider_references": [],
                "actual_charge_usd": None,
                "actual_charge_known": False,
            }],
            "this_stage_maximum_accounted_usd": reserve,
            "cumulative_maximum_accounted_usd": round(float(prior["maximum_accounted_with_reservation_usd"]) + reserve, 9),
            "cumulative_ceiling_usd": float(prior["fx"]["ceiling_usd"]),
            "updated_at_utc": utc(),
        }
        if ledger["cumulative_maximum_accounted_usd"] > ledger["cumulative_ceiling_usd"]:
            raise RuntimeError("cumulative authorization ceiling would be exceeded")
        write_json(ledger_path, ledger)


def extract_originals() -> None:
    EXTRACT.mkdir(exist_ok=True)
    source_target = EXTRACT / "provider-original.mp4"
    if not source_target.exists():
        shutil.copyfile(SOURCE, source_target)
    result = pipeline.run_stage("extract_frames", EXTRACT, {
        "input": source_target.name,
        "fps": SOURCE_FPS,
        "indices": SELECTED,
        "output_prefix": "original",
    })
    if result["status"] != "needs_review" or result["details"]["selected_indices"] != SELECTED:
        raise RuntimeError("exact selected-frame extraction did not complete")


def run_removal(workdir: Path, source_orders: list[int]) -> list[Path]:
    workdir.mkdir(exist_ok=True)
    os.chmod(workdir, 0o700)
    names = []
    for local_order, source_order in enumerate(source_orders):
        name = f"selected-frame-{local_order:04d}.png"
        target = workdir / name
        source = EXTRACT / f"original-frame-{source_order:04d}.png"
        if not target.exists():
            shutil.copyfile(source, target)
        names.append(name)
    os.environ["WAVESPEED_API_KEY"] = load_key()
    params = {"inputs": names, "preset": "waldlicht-removal-v1", "budget": {"authorized": True, "max_usd": len(names) * QUOTE_UNIT}}
    for _attempt in range(500):
        result = pipeline.run_stage("remove_background", workdir, params)
        state = json.loads((workdir / "remove-background-state.json").read_text(encoding="utf-8"))
        if state.get("status") == "completed":
            outputs = [workdir / item["output"]["file"] for item in state["items"]]
            if not all(path.is_file() for path in outputs):
                raise RuntimeError("provider state completed but a cutout is absent")
            update_ledger_references()
            return outputs
        if any(item.get("status") == "submission_unknown" for item in state.get("items", [])):
            update_ledger_references()
            raise RuntimeError("ambiguous remover submission; no resubmit")
        if result.get("details", {}).get("safe_resume") is not True:
            raise RuntimeError("remover stopped without safe known-ID resume")
        time.sleep(1.5)
    update_ledger_references()
    raise RuntimeError("known remover IDs exceeded bounded polling window")


def update_ledger_references(completed: bool = False) -> None:
    references: list[str] = []
    statuses: list[str] = []
    for directory in (PROOF, REMAINING):
        state_path = directory / "remove-background-state.json"
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            for item in state.get("items", []):
                if isinstance(item.get("prediction_id"), str):
                    references.append(item["prediction_id"])
                statuses.append(str(item.get("status")))
    ledger_path = OUT / "cost-ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    entry = ledger["entries"][0]
    entry["provider_references"] = sorted(set(references))
    if any(status == "submission_unknown" for status in statuses):
        entry["status"] = "ambiguous_submission_full_reservation_retained"
    elif completed and len(references) == MAX_SELECTED and statuses and all(status == "completed" for status in statuses):
        entry["status"] = "completed_charge_not_authoritatively_reported_full_reservation_retained"
    else:
        entry["status"] = "partially_submitted_known_ids_full_reservation_retained"
    ledger["updated_at_utc"] = utc()
    write_json(ledger_path, ledger)


def premultiplied_resize(source: Image.Image, size: tuple[int, int], resample: Image.Resampling = Image.Resampling.LANCZOS) -> Image.Image:
    rgba = source.convert("RGBA")
    red, green, blue, alpha = rgba.split()
    premult = [Image.new("L", rgba.size), Image.new("L", rgba.size), Image.new("L", rgba.size)]
    for target, channel in zip(premult, (red, green, blue)):
        target.putdata([(c * a + 127) // 255 for c, a in zip(channel.getdata(), alpha.getdata())])
    resized_alpha = alpha.resize(size, resample)
    resized_premult = [channel.resize(size, resample) for channel in premult]
    alpha_values = list(resized_alpha.getdata())
    color_values = [list(channel.getdata()) for channel in resized_premult]
    pixels = []
    for index, a in enumerate(alpha_values):
        if a == 0:
            pixels.append((0, 0, 0, 0))
        else:
            rgb = [min(255, (values[index] * 255 + a // 2) // a) for values in color_values]
            pixels.append((rgb[0], rgb[1], rgb[2], a))
    result = Image.new("RGBA", size)
    result.putdata(pixels)
    rgba.close(); red.close(); green.close(); blue.close(); alpha.close(); resized_alpha.close()
    for image in premult + resized_premult:
        image.close()
    return result


def normalize(master: Path, canvas: int) -> tuple[Image.Image, dict]:
    transform = TRANSFORMS[canvas]
    with Image.open(master) as opened:
        source = opened.convert("RGBA")
    scaled_size = (max(1, round(source.width * transform["scale"])), max(1, round(source.height * transform["scale"])))
    scaled = premultiplied_resize(source, scaled_size)
    paste = (
        transform["target_root"][0] - round(transform["source_root"][0] * transform["scale"]),
        transform["target_root"][1] - round(transform["source_root"][1] * transform["scale"]),
    )
    target = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    target.alpha_composite(scaled, paste)
    pixels = list(target.getdata())
    cleared = sum(1 for pixel in pixels if 0 < pixel[3] < 8)
    if cleared:
        target.putdata([(0, 0, 0, 0) if 0 < a < 8 else (r, g, b, a) for r, g, b, a in pixels])
    bounds = target.getchannel("A").getbbox()
    if bounds is None or bounds[0] <= 0 or bounds[1] <= 0 or bounds[2] >= canvas or bounds[3] >= canvas:
        raise RuntimeError(f"normalized {canvas}px frame clips/touches edge")
    source.close(); scaled.close()
    return target, {"scale": transform["scale"], "source_root": transform["source_root"], "target_root": transform["target_root"], "scaled_full_canvas": list(scaled_size), "paste_offset": list(paste), "alpha_1_7_pixels_cleared": cleared, "bounds": list(bounds)}


def composite(sprite: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    background = Image.new("RGBA", sprite.size, color + (255,))
    background.alpha_composite(sprite)
    return background.convert("RGB")


def create_proofboard() -> None:
    proof_cutouts = [PROOF / f"cutout-frame-{index:04d}.png" for index in range(3)]
    board = Image.new("RGB", (6 * 160, 3 * 190), (42, 45, 48))
    draw = ImageDraw.Draw(board)
    labels = ["ORIGINAL", "REMOVED/light", "FINAL/light", "FINAL/dark", "FINAL/petrol", "FINAL 2x nearest"]
    for column, label in enumerate(labels):
        draw.text((column * 160 + 4, 4), label, fill=(255, 226, 105))
    for row, (source_order, cutout) in enumerate(zip(PROOF_ORDERS, proof_cutouts)):
        y = row * 190 + 28
        with Image.open(EXTRACT / f"original-frame-{source_order:04d}.png") as opened:
            original = opened.convert("RGB").resize((160, 160), Image.Resampling.LANCZOS)
        board.paste(original, (0, y)); original.close()
        final, _record = normalize(cutout, 160)
        for column, background in zip((1, 2, 3, 4), (BG["light"], BG["light"], BG["dark"], BG["petrol"])):
            rendered = composite(final, background)
            board.paste(rendered, (column * 160, y)); rendered.close()
        enlarged = final.resize((320, 320), Image.Resampling.NEAREST).crop((80, 80, 240, 240))
        enlarged_rgb = composite(enlarged, BG["dark"])
        board.paste(enlarged_rgb, (5 * 160, y)); enlarged.close(); enlarged_rgb.close(); final.close()
        draw.text((4, y + 144), f"native {SELECTED[source_order]} / {SELECTED[source_order]/SOURCE_FPS:.3f}s", fill=(255, 226, 105))
    target = OUT / "SPATIAL_PROOFBOARD.png"
    board.save(target); board.close()
    proof = {
        "source_sha256": sha256(SOURCE),
        "candidate": "candidate-01-66-98",
        "representative_native_indices": [SELECTED[index] for index in PROOF_ORDERS],
        "provider_cutout_hashes": [sha256(path) for path in proof_cutouts],
        "board": {"file": target.name, "sha256": sha256(target)},
        "transform": TRANSFORMS[160],
        "processing": "direct full-resolution provider cutout -> premultiplied-alpha Lanczos resize -> alpha 1..7 cleanup",
        "visual_quality_certified": False,
    }
    write_json(OUT / "spatial-proof.json", proof)


def proof_phase() -> None:
    initialize(); extract_originals()
    run_removal(PROOF, PROOF_ORDERS)
    create_proofboard()
    print(json.dumps({"status": "proof_ready", "proofboard": str(OUT / "SPATIAL_PROOFBOARD.png"), "ledger": str(OUT / "cost-ledger.json")}, indent=2))


def copy_masters() -> list[Path]:
    MASTER.mkdir(exist_ok=True)
    remaining_orders = [order for order in range(MAX_SELECTED) if order not in PROOF_ORDERS]
    run_removal(REMAINING, remaining_orders)
    mapping = {}
    for local, source_order in enumerate(PROOF_ORDERS):
        mapping[source_order] = PROOF / f"cutout-frame-{local:04d}.png"
    for local, source_order in enumerate(remaining_orders):
        mapping[source_order] = REMAINING / f"cutout-frame-{local:04d}.png"
    masters = []
    for order in range(MAX_SELECTED):
        target = MASTER / f"master-cutout-{order:04d}.png"
        if not target.exists():
            shutil.copyfile(mapping[order], target)
        masters.append(target)
    update_ledger_references(completed=True)
    return masters


def encode_preview(frame_dir: Path, fps: float, target: Path, loops: int = 3) -> None:
    count = MAX_SELECTED * loops
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-stream_loop", str(loops - 1), "-framerate", f"{fps:.12g}",
        "-i", str(frame_dir / "frame-%04d.png"), "-frames:v", str(count), "-c:v", "libx264",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(target),
    ], check=True, timeout=180)


def export_variant(masters: list[Path], canvas: int) -> dict:
    directory = OUT / f"export-{canvas}"
    directory.mkdir(exist_ok=True)
    frames = []
    records = []
    for order, master in enumerate(masters):
        frame, transform = normalize(master, canvas)
        name = f"frame-{order:04d}.png"
        frame.save(directory / name)
        frames.append(frame)
        records.append({
            "id": f"keeper.walk.ne.{canvas}.{order:04d}", "order": order,
            "native_source_index": SELECTED[order], "timestamp_seconds": SELECTED[order] / SOURCE_FPS,
            "source_master": master.relative_to(OUT).as_posix(), "source_master_sha256": sha256(master),
            "file": name, "sha256": sha256(directory / name), "rect": {},
            "anchor": {"x": 0.5, "y": 0.9}, "transform": transform,
        })
    columns = 8
    gutter = 2
    rows = (len(frames) + columns - 1) // columns
    atlas = Image.new("RGBA", (gutter + columns * (canvas + gutter), gutter + rows * (canvas + gutter)), (0, 0, 0, 0))
    for order, frame in enumerate(frames):
        x = gutter + (order % columns) * (canvas + gutter); y = gutter + (order // columns) * (canvas + gutter)
        atlas.alpha_composite(frame, (x, y))
        records[order]["rect"] = {"x": x, "y": y, "width": canvas, "height": canvas}
    atlas_name = f"atlas-{canvas}.png"
    atlas.save(OUT / atlas_name)
    manifest = {
        "schema": "animation-pipeline-atlas-v1", "version": 1,
        "source": {"file": SOURCE.relative_to(ROOT).as_posix(), "sha256": sha256(SOURCE), "candidate": "candidate-01-66-98", "human_reviewed_source": True, "automatic_gate_certified": False},
        "image": {"id": f"keeper-walk-ne-{canvas}", "file": atlas_name, "sha256": sha256(OUT / atlas_name), "width": atlas.width, "height": atlas.height, "sampling": "premultiplied-alpha-lanczos"},
        "packing": {"columns": columns, "rows": rows, "gutter": gutter, "cell": {"width": canvas, "height": canvas}},
        "clip": {"id": f"keeper.walk.ne.{canvas}", "action": "walk", "direction": "ne", "fps": PLAYBACK_FPS, "loop": True, "duration_seconds": CYCLE_DURATION, "frames": [record["id"] for record in records]},
        "display": {"native_css_pixels": [canvas, canvas], "allowed_sampling": "nearest-neighbour", "allowed_scale": "integer only", "fractional_css_scaling": False},
        "processing": {"full_resolution_masters_preserved": True, "direct_from_master": True, "premultiplied_alpha_resample": True, "cleanup": {"alpha_min": 1, "alpha_max": 7, "component_removal": False}},
        "frames": records,
    }
    manifest_name = f"atlas-{canvas}-manifest.json"
    write_json(OUT / manifest_name, manifest)
    preview_dir = directory / "preview-petrol"
    preview_dir.mkdir(exist_ok=True)
    for order, frame in enumerate(frames):
        rendered = composite(frame, BG["petrol"])
        rendered.save(preview_dir / f"frame-{order:04d}.png"); rendered.close(); frame.close()
    preview = OUT / f"preview-{canvas}-native-petrol-3loops.mp4"
    encode_preview(preview_dir, PLAYBACK_FPS, preview)
    atlas.close()
    return {"canvas": canvas, "atlas": atlas_name, "atlas_sha256": sha256(OUT / atlas_name), "manifest": manifest_name, "manifest_sha256": sha256(OUT / manifest_name), "preview": preview.name, "preview_sha256": sha256(preview)}


def composite_atlas_board(variants: list[dict]) -> Path:
    board = Image.new("RGB", (960, 780), (35, 38, 42))
    draw = ImageDraw.Draw(board)
    draw.text((8, 6), "FINAL TRANSPARENT FRAMES - light / dark / petrol; native 160 detail", fill=(255, 226, 105))
    manifest = json.loads((OUT / "atlas-160-manifest.json").read_text(encoding="utf-8"))
    with Image.open(OUT / "atlas-160.png") as opened:
        atlas = opened.convert("RGBA")
    chosen = list(range(0, MAX_SELECTED, 3))
    for row, order in enumerate(chosen):
        rect = manifest["frames"][order]["rect"]
        sprite = atlas.crop((rect["x"], rect["y"], rect["x"] + rect["width"], rect["y"] + rect["height"]))
        y = 36 + row * 92
        draw.text((4, y + 35), f"n{SELECTED[order]}", fill=(255, 226, 105))
        thumb = sprite.resize((80, 80), Image.Resampling.LANCZOS)
        for column, color in enumerate(BG.values()):
            rendered = composite(thumb, color); board.paste(rendered, (80 + column * 90, y)); rendered.close()
        detail = composite(sprite, BG["dark"]); board.paste(detail, (390, y)); detail.close()
        sprite.close(); thumb.close()
    atlas.close()
    target = OUT / "FINAL_MULTI_BACKGROUND_CONTACT.png"
    board.save(target); board.close()
    return target


def write_player() -> None:
    (OUT / "preview.html").write_text("""<!doctype html><meta charset=utf-8><title>MiniMax NE final atlas</title>
<style>body{background:#203b3d;color:#fff;font:14px system-ui}section{display:inline-block;margin:16px}canvas{image-rendering:pixelated;background:#124448} .x2{width:320px;height:320px}</style>
<h1>Transparent atlas, exact manifest playback</h1><section><p>160px native 1:1</p><canvas id=n width=160 height=160></canvas></section><section><p>160px integer 2x nearest</p><canvas id=x class=x2 width=160 height=160></canvas></section>
<script>Promise.all([fetch('atlas-160-manifest.json').then(r=>r.json()),new Promise((ok,no)=>{let i=new Image;i.onload=()=>ok(i);i.onerror=no;i.src='atlas-160.png'})]).then(([m,img])=>{let k=0,last=performance.now(),step=1000/m.clip.fps;function f(t){if(t-last>=step){k=(k+Math.floor((t-last)/step))%m.frames.length;last=t-(t-last)%step}let r=m.frames[k].rect;for(let id of ['n','x']){let c=document.getElementById(id),g=c.getContext('2d');g.clearRect(0,0,c.width,c.height);g.imageSmoothingEnabled=false;g.drawImage(img,r.x,r.y,r.width,r.height,0,0,c.width,c.height)}requestAnimationFrame(f)}requestAnimationFrame(f)})</script>""", encoding="utf-8")


def final_phase() -> None:
    initialize(); extract_originals()
    if not (OUT / "SPATIAL_PROOFBOARD.png").is_file():
        raise RuntimeError("spatial proof must exist before full removal")
    masters = copy_masters()
    variants = [export_variant(masters, canvas) for canvas in (80, 160)]
    contact = composite_atlas_board(variants)
    write_player()
    package = OUT / "minimax-ne-transparent-export.zip"
    included = [OUT / item[key] for item in variants for key in ("atlas", "manifest", "preview")]
    included += [OUT / "preview.html", contact, OUT / "SPATIAL_PROOFBOARD.png", OUT / "cost-ledger.json", OUT / "fresh-remover-quote.json"]
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in included:
            archive.write(path, path.name)
    ledger = json.loads((OUT / "cost-ledger.json").read_text(encoding="utf-8"))
    report = [
        "# Final MiniMax NE export report", "", "Status: real transparent export created; visual inspection remains evidence-bound, not a perfection claim.", "",
        "## Source and selection", "", f"- Source: {SOURCE.relative_to(ROOT)}", f"- Source SHA-256: {sha256(SOURCE)}", "- Candidate: candidate-01-66-98, native [66,98), 1.333333333 s.", "- Source label: human-reviewed exact 160px source preview; not automatic gate certification.", f"- Selected original frames ({len(SELECTED)}): {', '.join(map(str, SELECTED))}.", f"- Playback: {PLAYBACK_FPS:.9f} FPS, preserving the reviewed interval duration.", "",
        "## Processing", "", "- Actual WaveSpeed image-background-remover outputs downloaded for every selected original frame.", "- Full-resolution RGBA cutout masters preserved in master-cutouts/.", "- 80px and 160px variants each derive directly from the full-resolution master with one premultiplied-alpha Lanczos downsample.", "- Shared source root/scale per resolution; no per-frame recentering or scale changes.", "- Only alpha 1..7 resampling fringe is cleared; no connected components/anatomy are deleted.", "- Runtime: native 160px recommended for retained detail; 80px is a compact variant. Display uses nearest-neighbour at integer scales only.", "",
        "## Deliverables", "",
    ]
    for variant in variants:
        report += [f"- {variant['canvas']}px atlas: {variant['atlas']} ({variant['atlas_sha256']})", f"- {variant['canvas']}px manifest: {variant['manifest']} ({variant['manifest_sha256']})", f"- {variant['canvas']}px 3-loop petrol preview: {variant['preview']} ({variant['preview_sha256']})"]
    report += [f"- Multi-background exact final contact: {contact.name} ({sha256(contact)})", f"- Manifest player: preview.html ({sha256(OUT / 'preview.html')})", f"- ZIP: {package.name} ({sha256(package)})", "", "## Cost", "", f"- Fresh quote: USD {QUOTE_UNIT:.3f}/image; 24-image maximum reserved before first submission: USD {MAX_SELECTED * QUOTE_UNIT:.3f}.", f"- Provider IDs: {len(ledger['entries'][0]['provider_references'])}; actual charge not authoritatively returned, so full USD {MAX_SELECTED * QUOTE_UNIT:.3f} remains accounted.", f"- Cumulative maximum accounted: USD {ledger['cumulative_maximum_accounted_usd']:.9f} of USD {ledger['cumulative_ceiling_usd']:.4f}.", "", "## Honest limits", "", "- One NE walk direction only.", "- No VLM review, source regeneration, frame synthesis, ping-pong, or public/game change.", "- Human review covered the source preview; transparent final export requires independent visual review of the retained evidence.", "- MP4 previews are opaque composites for playback convenience; atlas PNGs and frame PNGs contain true alpha.", ""]
    (OUT / "FINAL_EXPORT_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"status": "final_ready", "output": str(OUT), "zip": str(package), "report": str(OUT / "FINAL_EXPORT_REPORT.md"), "variants": variants}, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("proof", "final"))
    args = parser.parse_args()
    if args.phase == "proof": proof_phase()
    else: final_phase()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
