#!/usr/bin/env python3
"""Replay free local candidate analysis on the two recorded review videos."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import animation_review

SOURCES = {
    "gemini-rejected-3s": ROOT / "artifacts/gemini-omni-video-3s-01/video-output.mp4",
    "wan-existing-accepted-window": Path("/root/games/waldlicht/art/character-motion/ne-video-01/source-video.mp4"),
}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _save_request_evidence(directory: Path, request: dict[str, object]) -> dict[str, object]:
    content = request["messages"][0]["content"]  # type: ignore[index]
    labels: list[str] = []
    images: list[dict[str, object]] = []
    video: dict[str, object] | None = None
    pending_label: str | None = None
    for item in content:  # type: ignore[union-attr]
        if item["type"] == "text":
            if item["text"].startswith("FRAME EVIDENCE"):
                pending_label = item["text"]
                labels.append(pending_label)
        elif item["type"] == "video_url":
            uri = item["video_url"]["url"]
            header, encoded = uri.split(",", 1)
            decoded = base64.b64decode(encoded, validate=True)
            video = {"data_uri_header": header, "decoded_bytes": len(decoded), "decoded_sha256": _sha256_bytes(decoded)}
        elif item["type"] == "image_url":
            uri = item["image_url"]["url"]
            decoded = base64.b64decode(uri.split(",", 1)[1], validate=True)
            name = f"boundary-evidence-{len(images) + 1:02d}.png"
            target = directory / name
            target.write_bytes(decoded)
            with Image.open(target) as opened:
                size = list(opened.size)
            images.append({"file": name, "sha256": _sha256_bytes(decoded), "bytes": len(decoded), "dimensions": size, "label": pending_label})
            pending_label = None
    canonical = json.dumps(request, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return {
        "model": request["model"],
        "request_sha256": _sha256_bytes(canonical),
        "request_bytes_with_embedded_media": len(canonical),
        "provider_routing": request["provider"],
        "response_format": request["response_format"],
        "video": video,
        "frame_labels": labels,
        "frame_evidence": images,
        "paid_transport_called": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/review-candidates")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        if not args.replace:
            raise SystemExit(f"output exists: {output}; pass --replace")
        shutil.rmtree(output)
    output.mkdir(parents=True)

    records: list[dict[str, object]] = []
    for label, source in SOURCES.items():
        if not source.is_file() or source.is_symlink():
            raise SystemExit(f"missing regular source video: {source}")
        directory = output / label
        directory.mkdir()
        local = directory / "source.mp4"
        shutil.copyfile(source, local)
        analysis = animation_review.analyze_candidates(directory, local.name, sample_fps=12, minimum_loop_seconds=0.5, maximum_loop_seconds=2.5)
        _write_json(directory / "candidate-analysis.json", analysis)
        request = animation_review.build_review_request(directory, local.name, analysis)
        request_manifest = _save_request_evidence(directory, request)
        _write_json(directory / "review-request-manifest.json", request_manifest)
        record = {
            "label": label,
            "original_read_only_source": str(source),
            "local_copy": str(local.relative_to(ROOT)),
            "source_sha256": analysis["source"]["sha256"],
            "analysis_status": analysis["status"],
            "hard_failures": analysis["hard_failures"],
            "candidate_count": len(analysis["candidates"]),
            "top_candidate": analysis["candidates"][0] if analysis["candidates"] else None,
            "analysis": str((directory / "candidate-analysis.json").relative_to(ROOT)),
            "request_manifest": str((directory / "review-request-manifest.json").relative_to(ROOT)),
            "provider_inference_run": False,
        }
        records.append(record)
        print(f"{label}: {record['analysis_status']} ({record['candidate_count']} candidates)")
    _write_json(
        output / "replay-report.json",
        {
            "version": 1,
            "review_model": animation_review.DEFAULT_MODEL,
            "local_candidate_analysis_only": True,
            "provider_inference_run": False,
            "records": records,
            "limitations": [
                "The WAN source has a previously accepted early review window; this replay does not claim the entire source or a new candidate was visually approved.",
                "Heuristic rankings are suggestions pending schema-validated Gemini review and existing service review gates.",
            ],
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
