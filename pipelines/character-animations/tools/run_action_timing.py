#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import animation_review
import pipeline
import spatial_export

BASE = ROOT / "review/minimax-480p-3s-punch-01"
OUT = ROOT / "review/action-timing-01"
CACHE = BASE / "cutout-cache"
PRESET = "waldlicht-removal-v1"
RECIPE = "wavespeed-image-background-remover-output-v1"
TASK_CAP = 0.15


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_authorized_credentials() -> str:
    connection = sqlite3.connect("file:/root/.openclaw/state/openclaw.sqlite?mode=ro", uri=True)
    try:
        row = connection.execute(
            "SELECT value, allowed_hosts FROM secret_store_entries WHERE deleted_at_ms IS NULL AND name='OPWNROUTER_KEY_2'"
        ).fetchone()
    finally:
        connection.close()
    if not row or not isinstance(row[0], str) or "openrouter.ai" not in (row[1] or ""):
        raise RuntimeError("authorized exact-model OpenRouter credential is unavailable")
    for line in Path("/root/.hermes/.env").read_text(encoding="utf-8").splitlines():
        if line.startswith("WAVESPEED_API_KEY="):
            os.environ["WAVESPEED_API_KEY"] = line.split("=", 1)[1]
            break
    if not os.environ.get("WAVESPEED_API_KEY"):
        raise RuntimeError("authorized WaveSpeed credential is unavailable")
    return row[0]


def prior_maximum_accounted() -> dict[str, object]:
    path = BASE / "cost-ledger.json"
    ledger = json.loads(path.read_text(encoding="utf-8"))
    prior = float(ledger["prior_reconciliation"]["maximum_accounted_usd"])
    current = float(ledger["maximum_accounted_usd"])
    return {"source": str(path), "maximum_accounted_usd": prior + current}


def milestone(name: str, details: dict[str, object]) -> None:
    report = OUT / "REPORT.md"
    report.write_text(
        "# Action timing 01\n\n"
        f"Current milestone: {name}\n\n"
        f"Updated UTC: {utc()}\n\n"
        "```json\n" + json.dumps(details, indent=2, sort_keys=True) + "\n```\n",
        encoding="utf-8",
    )


def main() -> int:
    prepare = json.loads((OUT / "PREPARE.json").read_text(encoding="utf-8"))
    analysis = json.loads((OUT / "local-action-analysis.json").read_text(encoding="utf-8"))
    sampling = prepare["sampling"]
    source = OUT / "source-original.mp4"
    metadata = animation_review.fetch_openrouter_model_metadata()
    metadata_path = OUT / "openrouter-model-metadata.json"
    write(metadata_path, metadata)

    request = animation_review.build_review_request(
        OUT, source.name, analysis, max_tokens=300,
        request_binding={"request_id": "action-timing-01", "source_sha256": sha(source), "source_revision": 1},
    )
    review_bound = request["_review_evidence"]["conservative_input_token_bound"]
    review_quote = review_bound * float(metadata["pricing"]["prompt"]) + 300 * float(metadata["pricing"]["completion"])
    removal_quote = len(prepare["cache"]["missing"]) * 0.004
    if review_quote + removal_quote > TASK_CAP:
        raise RuntimeError("bounded paid reservation exceeds task cap")

    prior = prior_maximum_accounted()
    ceiling = float(json.loads((BASE / "cost-ledger.json").read_text(encoding="utf-8"))["cumulative_ceiling_usd"])
    if float(prior["maximum_accounted_usd"]) + review_quote + removal_quote > ceiling + 1e-12:
        raise RuntimeError("global EUR20 development ceiling exceeded before paid action-timing calls")
    ledger_path = OUT / "cost-ledger.json"
    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    else:
        ledger = {
            "schema": "action-timing-cost-ledger-v1", "updated_at_utc": utc(),
            "task_cap_usd": TASK_CAP, "cumulative_ceiling_usd": ceiling,
            "prior_reconciliation": prior,
            "entries": [
                {"id": "phase-review", "model": animation_review.DEFAULT_MODEL, "reserved_usd": review_quote, "known_billed_usd": None, "open_liability_usd": review_quote, "status": "reserved_not_sent"},
                {"id": "missing-cutouts", "model": "wavespeed-ai/image-background-remover", "count": len(prepare["cache"]["missing"]), "reserved_usd": removal_quote, "known_billed_usd": None, "open_liability_usd": removal_quote, "status": "reserved_not_sent"},
            ],
            "maximum_accounted_usd": review_quote + removal_quote,
            "cumulative_maximum_accounted_usd": float(prior["maximum_accounted_usd"]) + review_quote + removal_quote,
        }
    write(OUT / "cost-ledger.json", ledger)
    milestone("metadata_and_reservation_complete", {
        "exact_model": metadata["id"], "context_length": metadata["context_length"],
        "pricing": metadata["pricing"], "metadata_receipt": metadata_path.name,
        "review_reserved_usd": review_quote, "removal_reserved_usd": removal_quote,
        "selected_indices": sampling["indices"], "frame_durations_seconds": sampling["frame_durations_seconds"],
        "longest_hold_seconds": max(sampling["frame_durations_seconds"]),
    })

    review_path = OUT / "phase-review-result.json"
    review = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else None
    if review is not None and review.get("status") == "needs_attention" and review.get("reason") == "review model context length metadata is invalid":
        archived = OUT / "phase-review-result-metadata-invalid-not-sent.json"
        if not archived.exists():
            review_path.replace(archived)
        else:
            review_path.unlink()
        review = None
    if review is None:
        openrouter_key = load_authorized_credentials()
        ledger["entries"][0]["status"] = "submission_started"
        ledger["updated_at_utc"] = utc()
        write(OUT / "cost-ledger.json", ledger)
        review = animation_review.submit_review(
            OUT, source.name, analysis, paid_enabled=True,
            api_key=openrouter_key, budget_cap_usd=review_quote,
            max_input_tokens=review_bound, max_tokens=300, capability_metadata=metadata,
            request_binding={"request_id": "action-timing-01", "source_sha256": sha(source), "source_revision": 1},
        )
        write(review_path, review)
        review_cost = (review.get("budget") or {}).get("actual_cost_usd")
        ledger["entries"][0].update(
            known_billed_usd=review_cost,
            open_liability_usd=0.0 if review_cost is not None else review_quote,
            status="known_billed" if review_cost is not None else "response_received_cost_unknown",
            provider_reference=review.get("response_id"),
        )
        ledger["updated_at_utc"] = utc()
        write(OUT / "cost-ledger.json", ledger)
    milestone("phase_review_received", {"review": review, "cost_ledger": ledger})
    if review.get("status") != "approved" or review.get("selected_candidate") != prepare["candidate"]:
        raise RuntimeError(f"phase review did not approve exact proposed interval: {review.get('status')} {review.get('reason')}")

    extraction = OUT / "selected-originals"
    originals = [extraction / f"action-frame-{order:04d}.png" for order in range(len(sampling["indices"]))]
    masters = [spatial_export.lookup_cached_cutout(item, CACHE, PRESET, RECIPE) for item in originals]
    missing_orders = [order for order, item in enumerate(masters) if item is None]
    if missing_orders:
        load_authorized_credentials()
        ledger["entries"][1]["status"] = "submission_started"
        ledger["updated_at_utc"] = utc()
        write(OUT / "cost-ledger.json", ledger)
        removal_inputs = []
        for order in missing_orders:
            name = f"timing-selected-{order:04d}.png"
            shutil.copyfile(originals[order], OUT / name)
            removal_inputs.append(name)
        removal_params = {
            "inputs": removal_inputs, "preset": PRESET,
            "budget": {"authorized": True, "max_usd": len(removal_inputs) * 0.004},
        }
        result = pipeline.run_stage("remove_background", OUT, removal_params)
        for _attempt in range(20):
            details = result.get("details") if isinstance(result, dict) else None
            if result.get("status") != "needs_attention" or not isinstance(details, dict) or details.get("safe_resume") is not True:
                break
            time.sleep(1)
            result = pipeline.run_stage("remove_background", OUT, removal_params)
        if result["status"] != "needs_review":
            raise RuntimeError(f"missing-cutout removal incomplete: {result['status']}")
        for batch_order, source_order in enumerate(missing_orders):
            spatial_export.import_cached_cutout(
                originals[source_order], OUT / f"cutout-frame-{batch_order:04d}.png", CACHE, PRESET, RECIPE,
            )
        state = json.loads((OUT / "remove-background-state.json").read_text(encoding="utf-8"))
        provider_ids = sorted({item.get("prediction_id") for item in state.get("items", []) if isinstance(item, dict) and isinstance(item.get("prediction_id"), str)})
        ledger["entries"][1].update(
            open_liability_usd=removal_quote,
            status="completed_charge_not_authoritatively_reported",
            provider_references=provider_ids,
        )
        ledger["updated_at_utc"] = utc()
        write(OUT / "cost-ledger.json", ledger)
    milestone("cutout_cache_complete", {"missing_cutouts_processed": len(missing_orders), "cost_ledger": ledger})
    master_paths = [spatial_export.lookup_cached_cutout(item, CACHE, PRESET, RECIPE) for item in originals]
    if any(item is None for item in master_paths):
        raise RuntimeError("verified cache remains incomplete")
    masters_exact = [Path(item) for item in master_paths if item is not None]

    derived = spatial_export.derive_shared_geometry(masters_exact, spatial_export.SERVICE_SPATIAL_PRESETS["derived-native-160-80-v1"]["variants"])
    config = {
        "job_id": "keeper-punch-timed", "action": "punch", "direction": "ne", "loop": False,
        "native_fps": 24.0, "cycle_start": sampling["native_interval"]["start_inclusive"],
        "cycle_end_exclusive": sampling["native_interval"]["end_exclusive"],
        "selected_indices": sampling["indices"], "frame_durations_seconds": sampling["frame_durations_seconds"],
        "selection_mode": "automatic_model_validated",
        "selection_receipt": {"file": review_path.name, "sha256": sha(review_path)},
        "frame_policy": sampling["frame_policy"],
        "source": {"file": source.name, "sha256": sha(source)},
        "geometry": derived["geometry"], "variants": derived["variants"],
    }
    variants = spatial_export.export_variants(masters_exact, OUT, config)
    for variant in variants:
        variant.pop("_timings", None)
        variant["preview"] = spatial_export._encode_preview(
            OUT, variant["canvas"], sampling["playback_fps"], len(masters_exact), loop=False,
            frame_durations_seconds=sampling["frame_durations_seconds"],
        )
    spatial_export.write_player(OUT, 160)
    verification = spatial_export._verify_all_frames(OUT, variants)
    write(OUT / "verification.json", verification)

    before = BASE / "preview-160-native-petrol-repeated-3x.mp4"
    shutil.copyfile(before, OUT / "BEFORE-punch-untrimmed-uniform.mp4")
    after = OUT / "preview-160-native-petrol-repeated-3x.mp4"
    compare = OUT / "comparison.html"
    compare.write_text("""<!doctype html><meta charset=utf-8><link rel=icon href=data:,><style>body{background:#123;color:white;font:16px system-ui;display:flex;gap:24px}video{image-rendering:pixelated;width:320px}section{max-width:360px}</style><section><h2>BEFORE · 3.042 s · uniform</h2><video controls loop autoplay muted src='BEFORE-punch-untrimmed-uniform.mp4'></video></section><section><h2>AFTER · 1.625 s · source timing · loop=false</h2><video controls loop autoplay muted src='preview-160-native-petrol-repeated-3x.mp4'></video></section>""", encoding="utf-8")

    artifacts = ["atlas-160.png", "atlas-160-manifest.json", "atlas-80.png", "atlas-80-manifest.json", variants[0]["preview"], variants[1]["preview"], "preview.html", "comparison.html", "verification.json", review_path.name]
    package = OUT / "action-timing-export.zip"
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in artifacts:
            archive.write(OUT / name, name)
    if zipfile.ZipFile(package).testzip() is not None:
        raise RuntimeError("export ZIP CRC failed")

    probe = json.loads(subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "format=duration", "-of", "json", str(after),
    ], check=True, capture_output=True, text=True).stdout)
    report = {
        "status": "completed_local_not_deployed", "source_sha256": sha(source),
        "review": {"model": review.get("model"), "response_id": review.get("response_id"), "actual_cost_usd": (review.get("budget") or {}).get("actual_cost_usd"), "result_sha256": sha(review_path)},
        "paid": {"task_cap_usd": TASK_CAP, "review_reserved_usd": review_quote, "removal_reserved_usd": removal_quote, "new_video_generation_calls": 0, "missing_cutouts": len(missing_orders)},
        "selection": {"indices": sampling["indices"], "start_inclusive": config["cycle_start"], "end_exclusive": config["cycle_end_exclusive"], "phases": prepare["candidate"]["phase_proposals"], "frame_durations_seconds": sampling["frame_durations_seconds"], "duration_seconds": sampling["cycle_duration_seconds"]},
        "outputs": {"zip": {"file": package.name, "sha256": sha(package)}, "before": {"file": "BEFORE-punch-untrimmed-uniform.mp4", "sha256": sha(OUT / "BEFORE-punch-untrimmed-uniform.mp4")}, "after": {"file": after.name, "sha256": sha(after), "encoded_duration_seconds": float(probe["format"]["duration"])}, "atlas_160_sha256": sha(OUT / "atlas-160.png"), "atlas_80_sha256": sha(OUT / "atlas-80.png")},
        "verification": verification, "game_adapter_changed": False, "deployed": False,
    }
    write(OUT / "REPORT.json", report)
    (OUT / "REPORT.md").write_text("# Action timing 01\n\n" + json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
