#!/usr/bin/env python3
"""Replay accepted Waldlicht inputs through the generic local pipeline.

This tool only reads /root/games/waldlicht. It copies genuine accepted assets into
an isolated service workspace, then verifies the derived dimensions, alpha and
hashes against Waldlicht's recorded accepted normalization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

SERVICE_ROOT = Path(__file__).resolve().parents[1]
WALDLICHT = Path("/root/games/waldlicht")
sys.path.insert(0, str(SERVICE_ROOT))

import pipeline  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def alpha_record(path: Path) -> dict:
    with Image.open(path) as opened:
        rgba = opened.convert("RGBA")
    alpha = rgba.getchannel("A")
    histogram = alpha.histogram()
    record = {
        "width": rgba.width,
        "height": rgba.height,
        "bounds": list(alpha.getbbox()) if alpha.getbbox() else None,
        "minimum": alpha.getextrema()[0],
        "maximum": alpha.getextrema()[1],
        "transparent_pixels": histogram[0],
        "semi_transparent_pixels": sum(histogram[1:255]),
        "opaque_pixels": histogram[255],
    }
    alpha.close()
    rgba.close()
    return record


def copy_verified(source: Path, target: Path, expected: str | None = None) -> dict:
    actual = sha256(source)
    if expected is not None and actual != expected:
        raise RuntimeError(f"recorded source hash mismatch: {source}")
    shutil.copyfile(source, target)
    copied = sha256(target)
    if copied != actual:
        raise RuntimeError(f"copy hash mismatch: {target}")
    return {"source": str(source), "source_sha256": actual, "copy": target.name, "copy_sha256": copied, "byte_equal": True}


def replay(workspace: Path, replace: bool) -> dict:
    workspace = workspace.resolve()
    allowed_root = (SERVICE_ROOT / "artifacts").resolve()
    if workspace != allowed_root and allowed_root not in workspace.parents:
        raise ValueError("workspace must stay under service artifacts/")
    if workspace.exists():
        if not replace:
            raise ValueError("workspace exists; use --replace for this isolated replay directory")
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)

    facing_result_path = WALDLICHT / "art/character-motion/ne-facing-01/result-01.json"
    facing_result = json.loads(facing_result_path.read_text(encoding="utf-8"))
    reference_source = WALDLICHT / facing_result["source"]
    reference_copy = copy_verified(reference_source, workspace / "reference.png", facing_result["sourceSha256"])
    inspect_result = pipeline.run_stage("inspect_reference", workspace, {"input": "reference.png"})
    if (inspect_result["details"]["width"], inspect_result["details"]["height"]) != tuple(facing_result["sourceSize"]):
        raise RuntimeError("reference dimensions differ from recorded Waldlicht source")

    accepted_root = WALDLICHT / "art/character-motion/se-cutout-01"
    provenance_path = accepted_root / "official-provider-export/provenance.json"
    normalization_path = accepted_root / "normalization.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    normalization = json.loads(normalization_path.read_text(encoding="utf-8"))
    if provenance.get("version") != 2 or len(provenance.get("exportedFrames", [])) != 16:
        raise RuntimeError("accepted Waldlicht provenance is not the expected 16-frame version-2 export")
    if len(normalization.get("frames", [])) != len(provenance["exportedFrames"]):
        raise RuntimeError("accepted provenance and normalization frame counts differ")

    copied_cutouts = []
    input_names = []
    for order, (exported, normalized) in enumerate(zip(provenance["exportedFrames"], normalization["frames"])):
        source = accepted_root / "official-provider-export" / exported["file"]
        name = f"accepted-cutout-{order:04d}.png"
        copied = copy_verified(source, workspace / name, exported["sha256"])
        copied["accepted_alpha"] = alpha_record(source)
        copied["recorded_normalization_input_sha256"] = normalized["inputSha256"]
        if copied["source_sha256"] != normalized["inputSha256"]:
            raise RuntimeError(f"accepted input records disagree at frame {order}")
        copied_cutouts.append(copied)
        input_names.append(name)

    pack_result = pipeline.run_stage("pack", workspace, {
        "inputs": input_names,
        "image_id": "waldlicht-se-replay",
        "action": "walk",
        "direction": "se",
        "fps": 12,
        "loop": True,
        "canvas": {"width": 80, "height": 80},
        "target_visible_height": 58,
        "target_root": {"x": 40, "y": 72},
        "anchor": {"x": 0.5, "y": 0.9},
        "gutter": 2,
        "columns": 16,
        "resample": "nearest",
    })

    frame_checks = []
    for order, canonical in enumerate(normalization["frames"]):
        actual = workspace / f"normalized-frame-{order:04d}.png"
        expected = WALDLICHT / canonical["output"]
        actual_alpha = alpha_record(actual)
        expected_alpha = alpha_record(expected)
        check = {
            "order": order,
            "actual": actual.name,
            "actual_sha256": sha256(actual),
            "expected_source": str(expected),
            "expected_sha256": canonical["outputSha256"],
            "hash_equal": sha256(actual) == canonical["outputSha256"] == sha256(expected),
            "actual_alpha": actual_alpha,
            "expected_alpha": expected_alpha,
            "dimensions_and_alpha_equal": actual_alpha == expected_alpha,
        }
        frame_checks.append(check)
    if not all(item["hash_equal"] and item["dimensions_and_alpha_equal"] for item in frame_checks):
        raise RuntimeError("generic normalized output differs from accepted Waldlicht derivation")

    canonical_atlas = accepted_root / "packed-c-density/sheet.png"
    atlas_check = {
        "actual": "atlas.png",
        "actual_sha256": sha256(workspace / "atlas.png"),
        "canonical": str(canonical_atlas),
        "canonical_sha256": sha256(canonical_atlas),
        "hash_equal": sha256(workspace / "atlas.png") == sha256(canonical_atlas),
        "actual_alpha": alpha_record(workspace / "atlas.png"),
        "canonical_alpha": alpha_record(canonical_atlas),
    }
    atlas_check["dimensions_and_alpha_equal"] = atlas_check["actual_alpha"] == atlas_check["canonical_alpha"]
    if not atlas_check["hash_equal"] or not atlas_check["dimensions_and_alpha_equal"]:
        raise RuntimeError("generic atlas pixels/encoding differ from accepted Waldlicht sheet")

    manifest_path = workspace / "atlas-manifest.json"
    report = {
        "version": 1,
        "status": "passed",
        "source_game_read_only": True,
        "source_game": str(WALDLICHT),
        "workspace": str(workspace),
        "reference": reference_copy,
        "reference_inspection": inspect_result,
        "accepted_cutout_provenance": {
            "file": str(provenance_path),
            "sha256": sha256(provenance_path),
            "normalization": str(normalization_path),
            "normalization_sha256": sha256(normalization_path),
            "copies": copied_cutouts,
        },
        "generic_pack": pack_result,
        "frame_checks": frame_checks,
        "atlas_check": atlas_check,
        "generic_manifest": {"file": manifest_path.name, "sha256": sha256(manifest_path), "schema": "animation-pipeline-atlas-v1", "stock_framework_v4_claimed": False},
        "paid_calls": 0,
        "pass": True,
    }
    report_path = workspace / "replay-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=SERVICE_ROOT / "artifacts/replay-existing")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    try:
        report = replay(args.workspace, args.replace)
    except (ValueError, RuntimeError, OSError, KeyError, json.JSONDecodeError) as error:
        print(f"replay_existing: {error}", file=sys.stderr)
        return 1
    print(json.dumps({
        "pass": report["pass"],
        "workspace": report["workspace"],
        "frames": len(report["frame_checks"]),
        "all_frame_hashes_equal": all(item["hash_equal"] for item in report["frame_checks"]),
        "atlas_hash_equal": report["atlas_check"]["hash_equal"],
        "paid_calls": report["paid_calls"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
