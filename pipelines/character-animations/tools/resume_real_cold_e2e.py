#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import animation_review
from store import Store

OUT = ROOT / "review/real-cold-e2e-01"
SOURCE = OUT / "source-video.mp4"
REFERENCE = ROOT / "artifacts/minimax-ne-source-01/reference.png"
REVIEW_MODEL = "google/gemini-3.8-flash"
REMOVAL_MODEL = "wavespeed-ai/image-background-remover"
REMOVAL_UNIT_USD = 0.004
MAX_REMOVALS = 32
REVIEW_OUTPUT_TOKENS = 600
INCREMENTAL_CAP_USD = 3.0
HOST = "127.0.0.1"
PORT = 4396
BASE = f"http://{HOST}:{PORT}"
SOURCE_SHA256 = "b0a962f49467df55859e838187430d05c3581e044e373f8f19655a1f0db4d2b2"


def utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any, mode: int | None = None) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    if mode is not None:
        path.chmod(mode)


def load_keys() -> tuple[str, str]:
    connection = sqlite3.connect("file:/root/.openclaw/state/openclaw.sqlite?mode=ro", uri=True)
    row = connection.execute(
        "SELECT value,allowed_hosts FROM secret_store_entries WHERE deleted_at_ms IS NULL AND name='OPWNROUTER_KEY_2'"
    ).fetchone()
    connection.close()
    if not row or "openrouter.ai" not in (row[1] or ""):
        raise RuntimeError("authorized OpenRouter key unavailable")
    wavespeed = None
    for line in Path("/root/.hermes/.env").read_text(encoding="utf-8").splitlines():
        if line.startswith("WAVESPEED_API_KEY="):
            wavespeed = line.split("=", 1)[1].strip().strip("'\"")
    if not wavespeed:
        raise RuntimeError("WaveSpeed key unavailable")
    return row[0], wavespeed


def get_json(url: str, key: str | None = None) -> tuple[int, dict[str, Any]]:
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, json.loads(response.read())


def append_trace(event: str, recovery_start: float, **data: Any) -> None:
    record = {
        "utc": utc(),
        "event": event,
        "recovery_monotonic_elapsed_seconds": round(time.monotonic() - recovery_start, 6),
        **data,
    }
    with (OUT / "redacted-trace.jsonl").open("a", encoding="utf-8") as output:
        output.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")


def wait_job(client: httpx.Client, headers: dict[str, str], job_id: str, timeout: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/v1/jobs/{job_id}", headers=headers)
        response.raise_for_status()
        job = response.json()
        if job["state"] not in {"queued", "running"}:
            return job
        time.sleep(0.25)
    raise RuntimeError("API stage timeout")


def start_server(environment: dict[str, str], log_path: Path) -> subprocess.Popen[bytes]:
    probe = socket.socket()
    probe.bind((HOST, PORT))
    probe.close()
    log = log_path.open("ab")
    process = subprocess.Popen(
        [str(ROOT / ".venv/bin/python"), "-m", "uvicorn", "app:app", "--host", HOST, "--port", str(PORT), "--log-level", "warning"],
        cwd=ROOT,
        env=environment,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    process._animation_log = log  # type: ignore[attr-defined]
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            if httpx.get(BASE + "/health", timeout=2).status_code == 200:
                return process
        except Exception:
            pass
        if process.poll() is not None:
            raise RuntimeError("isolated server exited")
        time.sleep(0.1)
    raise RuntimeError("isolated server health timeout")


def stop_server(process: subprocess.Popen[bytes] | None) -> None:
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(5)
    if process is not None and hasattr(process, "_animation_log"):
        process._animation_log.close()  # type: ignore[attr-defined]


def update_report(report: dict[str, Any], recovery: dict[str, Any]) -> None:
    report["recovery"] = recovery
    report["updated_at_utc"] = utc()
    write_json(OUT / "REPORT.json", report)
    status = recovery.get("status", "running")
    lines = [
        "# Real cold end-to-end run 01",
        "",
        f"Status: {status}",
        "",
        "The original source and original rejection evidence are retained unchanged. This recovery continues the same source after a classifier defect fix; it is not a new video run.",
        "",
        "## Original immutable source",
        "",
        f"- Source SHA-256: `{SOURCE_SHA256}`",
        f"- Prediction ID: `{json.loads((OUT / 'source-request-receipt.json').read_text())['prediction_id']}`",
        "- Original local analysis: `local-candidate-analysis.json`",
        "- Revised local analysis: `local-candidate-analysis-revision-02.json`",
        "- Orientation overlays: `orientation-diagnostic/diagnostic.json` and timestamp-labelled PNGs",
        "",
        "## Incremental recovery state",
        "",
        "```json",
        json.dumps(recovery, indent=2, sort_keys=True, allow_nan=False),
        "```",
        "",
        "No visual-perfection claim is made. Public service, game, and deployment remain unchanged.",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def reserve_costs(ledger: dict[str, Any], review_reserve: float) -> None:
    entries = {entry["id"]: entry for entry in ledger["entries"]}
    source = entries["new-minimax-source"]
    if source.get("open_liability_usd") != 0.5 or "5e374847b2214064a86398a41a49e035" not in source.get("provider_references", []):
        raise RuntimeError("existing source liability or provider ID changed")
    entries["new-openrouter-review"].update({
        "reserved_usd": round(review_reserve, 9),
        "known_billed_usd": None,
        "open_liability_usd": round(review_reserve, 9),
        "status": "reserved_before_recovery_paid_call",
        "basis": {"model": REVIEW_MODEL, "bounded_numbered_image_sequence": True, "max_output_tokens": REVIEW_OUTPUT_TOKENS},
    })
    entries["new-removals"].update({
        "reserved_usd": round(MAX_REMOVALS * REMOVAL_UNIT_USD, 9),
        "known_billed_usd": None,
        "open_liability_usd": round(MAX_REMOVALS * REMOVAL_UNIT_USD, 9),
        "status": "reserved_before_recovery_paid_call",
        "basis": {"model": REMOVAL_MODEL, "maximum_selected_originals": MAX_REMOVALS, "unit_quote_usd": REMOVAL_UNIT_USD},
    })
    known = sum(float(entry.get("known_billed_usd") or 0) for entry in ledger["entries"])
    opened = sum(float(entry.get("open_liability_usd") or 0) for entry in ledger["entries"])
    ledger.update(
        known_billed_usd=round(known, 9),
        open_liability_usd=round(opened, 9),
        maximum_accounted_usd=round(known + opened, 9),
        updated_at_utc=utc(),
    )
    if known + opened > INCREMENTAL_CAP_USD + 1e-12:
        raise RuntimeError("same-attempt USD3 cap exceeded before paid recovery call")
    write_json(OUT / "cost-ledger.json", ledger)


def run() -> int:
    recovery_start = time.monotonic()
    recovery_started = utc()
    process: subprocess.Popen[bytes] | None = None
    report = json.loads((OUT / "REPORT.json").read_text(encoding="utf-8"))
    ledger = json.loads((OUT / "cost-ledger.json").read_text(encoding="utf-8"))
    recovery: dict[str, Any] = {
        "status": "running",
        "started_at_utc": recovery_started,
        "source_regenerated": False,
        "source_sha256": sha(SOURCE),
        "original_rejection_revision_preserved": True,
        "stages": [],
        "public_policy_changed": False,
        "deployment_changed": False,
        "visual_quality_certified": False,
    }
    update_report(report, recovery)
    append_trace("recovery_started", recovery_start, source_sha256=sha(SOURCE), source_regenerated=False)

    def stage(name: str) -> tuple[str, str, float]:
        append_trace("recovery_stage_started", recovery_start, stage=name)
        return name, utc(), time.monotonic()

    def finish(marker: tuple[str, str, float], status: str = "completed", **details: Any) -> None:
        record = {
            "stage": marker[0],
            "started_at_utc": marker[1],
            "ended_at_utc": utc(),
            "duration_seconds": round(time.monotonic() - marker[2], 6),
            "status": status,
            **details,
        }
        recovery["stages"].append(record)
        append_trace("recovery_stage_finished", recovery_start, **record)
        update_report(report, recovery)

    try:
        if sha(SOURCE) != SOURCE_SHA256:
            raise RuntimeError("retained source hash changed")
        preflight = stage("recovery_preflight_analysis_pricing_reservation")
        analysis_dir = OUT / "local-analysis-revision-02"
        analysis_dir.mkdir(exist_ok=False)
        shutil.copyfile(SOURCE, analysis_dir / "video-output.mp4")
        analysis = animation_review.analyze_candidates(analysis_dir, "video-output.mp4")
        write_json(OUT / "local-candidate-analysis-revision-02.json", analysis, 0o444)
        if analysis["hard_failures"] or analysis["status"] != "requires_semantic_review" or not analysis["candidates"]:
            raise RuntimeError(f"revised deterministic analysis is not reviewer-eligible: {analysis['hard_failures']}")

        openrouter_key, wavespeed_key = load_keys()
        _, key_info = get_json("https://openrouter.ai/api/v1/key", openrouter_key)
        _, models = get_json("https://openrouter.ai/api/v1/models", openrouter_key)
        model = next(item for item in models["data"] if item.get("id") == REVIEW_MODEL)
        prompt_price = float(model["pricing"]["prompt"])
        completion_price = float(model["pricing"]["completion"])
        metadata = {
            "fetched_at_utc": utc(),
            "source": "https://openrouter.ai/api/v1/models",
            "id": REVIEW_MODEL,
            "canonical_slug": model.get("canonical_slug"),
            "context_length": int(model["context_length"]),
            "architecture": model["architecture"],
            "supported_parameters": model["supported_parameters"],
            "pricing": model["pricing"],
            "fixed_run_price_claimed": False,
        }
        write_json(OUT / "openrouter-model-metadata-revision-02.json", metadata)
        bounded = animation_review.build_review_request(
            analysis_dir,
            "video-output.mp4",
            analysis,
            max_tokens=REVIEW_OUTPUT_TOKENS,
            request_binding={"request_id": "0" * 32, "source_sha256": SOURCE_SHA256, "source_revision": 1},
        )["_review_evidence"]
        max_input_tokens = bounded["conservative_input_token_bound"]
        review_reserve = max_input_tokens * prompt_price + REVIEW_OUTPUT_TOKENS * completion_price
        reserve_costs(ledger, review_reserve)

        fx_xml = urllib.request.urlopen("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml", timeout=30).read().decode()
        usd_per_eur = float(re.search(r"currency=['\"]USD['\"] rate=['\"]([0-9.]+)", fx_xml).group(1))
        fx_date = re.search(r"time=['\"]([0-9-]+)", fx_xml).group(1)
        cumulative_maximum = float(ledger["prior_reconciliation"]["maximum_accounted_usd"]) + float(ledger["maximum_accounted_usd"])
        if cumulative_maximum > 20 * usd_per_eur + 1e-12:
            raise RuntimeError("cumulative EUR20 development ceiling exceeded before paid recovery call")
        write_json(OUT / "recovery-pricing-reservation.json", {
            "fetched_at_utc": utc(),
            "ecb_fx": {"date": fx_date, "usd_per_eur": usd_per_eur, "ceiling_eur": 20, "ceiling_usd": 20 * usd_per_eur},
            "openrouter": {"model": REVIEW_MODEL, "prompt_usd_per_token": prompt_price, "completion_usd_per_token": completion_price, "max_input_tokens": max_input_tokens, "max_output_tokens": REVIEW_OUTPUT_TOKENS, "reserved_usd": review_reserve, "max_price_routing_enabled": True, "fallback_allowed": False},
            "remover": {"model": REMOVAL_MODEL, "live_schema_required": ["image"], "unit_quote_usd": REMOVAL_UNIT_USD, "reserved_frames": MAX_REMOVALS, "reserved_usd": MAX_REMOVALS * REMOVAL_UNIT_USD, "live_balance_usd": 15.04},
            "same_attempt_source_open_liability_usd": 0.5,
            "same_attempt_maximum_accounted_usd": ledger["maximum_accounted_usd"],
            "prior_reconciled_maximum_usd": ledger["prior_reconciliation"]["maximum_accounted_usd"],
            "cumulative_maximum_usd": cumulative_maximum,
            "openrouter_limit_remaining": key_info["data"].get("limit_remaining"),
        }, 0o444)
        recovery["pricing"] = json.loads((OUT / "recovery-pricing-reservation.json").read_text())
        recovery["revised_local_analysis"] = {
            "file": "local-candidate-analysis-revision-02.json",
            "sha256": sha(OUT / "local-candidate-analysis-revision-02.json"),
            "status": analysis["status"],
            "candidate_count": len(analysis["candidates"]),
            "hard_failures": analysis["hard_failures"],
        }
        finish(preflight, whole_batch_reserved_before_paid_call=True)

        data_dir = OUT / "recovery-private-service-data"
        cache_dir = OUT / "recovery-cutout-cache"
        cache_dir.mkdir(exist_ok=False)
        store = Store(data_dir / "jobs.sqlite3", data_dir / "jobs")
        job = store.create_job("reference.png", {"run": "real-cold-e2e-01-recovery"}, REFERENCE.read_bytes())
        job_id = job["id"]
        workdir = store.job_dir(job_id)
        shutil.copyfile(SOURCE, workdir / "video-output.mp4")
        with store.connect() as connection:
            store.upsert_artifact(connection, job_id, "video-output.mp4", "retained_fresh_minimax_source", workdir / "video-output.mp4")
        artifact = store.get_artifact(job_id, "video-output.mp4")
        token = secrets.token_urlsafe(36)
        environment = os.environ.copy()
        environment.update({
            "ANIMATION_API_TOKEN": token,
            "ANIMATION_DATA_DIR": str(data_dir),
            "ANIMATION_REVIEW_ENABLED": "1",
            "ANIMATION_REVIEW_MAX_USD": str(review_reserve),
            "ANIMATION_REVIEW_MAX_INPUT_TOKENS": str(max_input_tokens),
            "ANIMATION_REVIEW_MAX_OUTPUT_TOKENS": str(REVIEW_OUTPUT_TOKENS),
            "ANIMATION_REVIEW_MODEL_METADATA_FILE": str(OUT / "openrouter-model-metadata-revision-02.json"),
            "OPENROUTER_API_KEY": openrouter_key,
            "ANIMATION_PAID_ENABLED": "1",
            "ANIMATION_MAX_STAGE_USD": "0.50",
            "WAVESPEED_API_KEY": wavespeed_key,
            "ANIMATION_REMOVAL_MAX_INFLIGHT": "1",
            "ANIMATION_CUTOUT_CACHE_DIR": str(cache_dir),
        })
        process = start_server(environment, OUT / "recovery-isolated-server.log")
        headers = {"Authorization": f"Bearer {token}"}
        with httpx.Client(base_url=BASE, timeout=30) as client:
            reviewer = stage("recovery_openrouter_review_and_exact_extraction")
            response = client.post(
                f"/v1/jobs/{job_id}/automatic-review",
                headers=headers,
                json={
                    "artifact": artifact["name"],
                    "sha256": artifact["sha256"],
                    "revision": artifact["revision"],
                    "authorize_paid_review": True,
                    "budget_cap_usd": review_reserve,
                },
            )
            response.raise_for_status()
            reviewed_job = wait_job(client, headers, job_id, 300)
            review = reviewed_job["automatic_reviews"][0]
            review_result = json.loads((workdir / "automatic-review-result.json").read_text(encoding="utf-8"))
            for name in ["automatic-review-analysis.json", "automatic-review-result.json", "automatic-review-raw-message.txt", "extract-frames.json"]:
                source_path = workdir / name
                if source_path.exists():
                    shutil.copyfile(source_path, OUT / name)
                    if name == "automatic-review-raw-message.txt":
                        (OUT / name).chmod(0o600)
            budget = review_result.get("budget") or {}
            actual_review_cost = budget.get("actual_cost_usd")
            review_entry = next(entry for entry in ledger["entries"] if entry["id"] == "new-openrouter-review")
            if isinstance(actual_review_cost, (int, float)):
                review_entry.update(known_billed_usd=float(actual_review_cost), open_liability_usd=0.0, status="known_billed", provider_reference=review_result.get("response_id"))
            else:
                review_entry.update(status="completed_or_failed_cost_unknown", provider_references=[value for value in [review_result.get("response_id")] if value])
            known = sum(float(entry.get("known_billed_usd") or 0) for entry in ledger["entries"])
            opened = sum(float(entry.get("open_liability_usd") or 0) for entry in ledger["entries"])
            ledger.update(known_billed_usd=round(known, 9), open_liability_usd=round(opened, 9), maximum_accounted_usd=round(known + opened, 9), updated_at_utc=utc())
            write_json(OUT / "cost-ledger.json", ledger)
            recovery["automatic_review"] = review_result
            finish(
                reviewer,
                status=review["status"],
                response_id=review_result.get("response_id"),
                selected_candidate=review.get("selected_candidate"),
                selected_sampling=review.get("selected_sampling"),
            )
            if review["status"] != "approved":
                removal_entry = next(entry for entry in ledger["entries"] if entry["id"] == "new-removals")
                removal_entry.update(reserved_usd=0.0, open_liability_usd=0.0, status="released_after_semantic_rejection", basis={"reason": "Gemini source rejection"})
                write_json(OUT / "cost-ledger.json", ledger)
                raise RuntimeError(f"Gemini review did not approve source: {review_result.get('rejection_reason') or review_result.get('reason')}")

            sampling = review["selected_sampling"]
            selected_count = len(sampling["indices"])
            if not 1 <= selected_count <= MAX_REMOVALS:
                raise RuntimeError("review-selected cadence exceeds bounded remover window")
            removal_entry = next(entry for entry in ledger["entries"] if entry["id"] == "new-removals")
            removal_entry.update(
                reserved_usd=round(selected_count * REMOVAL_UNIT_USD, 9),
                open_liability_usd=round(selected_count * REMOVAL_UNIT_USD, 9),
                status="reserved_selected_originals",
                basis={"selected_candidate_id": review["selected_candidate"]["id"], "selected_frames": selected_count, "unit_quote_usd": REMOVAL_UNIT_USD},
            )
            known = sum(float(entry.get("known_billed_usd") or 0) for entry in ledger["entries"])
            opened = sum(float(entry.get("open_liability_usd") or 0) for entry in ledger["entries"])
            ledger.update(known_billed_usd=round(known, 9), open_liability_usd=round(opened, 9), maximum_accounted_usd=round(known + opened, 9), updated_at_utc=utc())
            write_json(OUT / "cost-ledger.json", ledger)
            current_job = client.get(f"/v1/jobs/{job_id}", headers=headers).json()
            selected = sorted(
                [item for item in current_job["artifacts"] if item["name"].startswith("selected-frame-")],
                key=lambda item: item["name"],
            )
            if len(selected) != selected_count:
                raise RuntimeError("automatic extraction artifact count mismatch")

            removal = stage("recovery_selected_original_removal_serial_and_cache_ingest")
            prediction_ids: set[str] = set()
            input_names = [item["name"] for item in selected]
            for _ in range(500):
                response = client.post(
                    f"/v1/jobs/{job_id}/stages",
                    headers=headers,
                    json={
                        "stage": "remove_background",
                        "params": {"inputs": input_names, "preset": "waldlicht-removal-v1"},
                        "authorize_paid": True,
                        "budget_cap_usd": selected_count * REMOVAL_UNIT_USD,
                    },
                )
                response.raise_for_status()
                ended = wait_job(client, headers, job_id, 240)
                state = json.loads((workdir / "remove-background-state.json").read_text(encoding="utf-8"))
                prediction_ids.update(item["prediction_id"] for item in state["items"] if isinstance(item.get("prediction_id"), str))
                if any(item.get("status") == "submission_unknown" for item in state["items"]):
                    removal_entry.update(status="ambiguous_submission", provider_references=sorted(prediction_ids))
                    write_json(OUT / "cost-ledger.json", ledger)
                    raise RuntimeError("remover submission ambiguous")
                if state.get("status") == "completed":
                    break
                if ended["state"] == "failed":
                    raise RuntimeError(ended.get("message") or "removal failed")
                time.sleep(1)
            else:
                removal_entry.update(status="known_predictions_pending", provider_references=sorted(prediction_ids))
                write_json(OUT / "cost-ledger.json", ledger)
                raise RuntimeError("removals timed out")
            removal_entry.update(status="completed_charge_not_authoritatively_reported", provider_references=sorted(prediction_ids))
            write_json(OUT / "cost-ledger.json", ledger)
            ingest = json.loads((workdir / "cutout-cache-ingest.json").read_text(encoding="utf-8"))
            for name in ["remove-background-state.json", "cutout-cache-ingest.json"]:
                shutil.copyfile(workdir / name, OUT / name)
            finish(removal, prediction_ids=sorted(prediction_ids), selected_frames=selected_count, cache_entries=len(ingest["items"]), maximum_inflight=1, all_entries_new=all(item["new_cache_entry"] for item in ingest["items"]))

            exporting = stage("recovery_api_spatial_export_normalize_pack_verify_download")
            response = client.post(
                f"/v1/jobs/{job_id}/stages",
                headers=headers,
                json={
                    "stage": "spatial_export",
                    "params": {
                        "source": "video-output.mp4",
                        "selection_receipt": "automatic-review-result.json",
                        "selection_mode": "automatic_model_validated",
                        "export_preset": "derived-native-160-80-v1",
                        "removal_preset": "waldlicht-removal-v1",
                        "removal_recipe": "wavespeed-image-background-remover-output-v1",
                    },
                },
            )
            response.raise_for_status()
            exported = wait_job(client, headers, job_id, 300)
            if exported["state"] != "completed":
                raise RuntimeError(exported.get("message") or "spatial export failed")
            download = client.get(f"/v1/jobs/{job_id}/download", headers=headers)
            download.raise_for_status()
            (OUT / "api-job-download.zip").write_bytes(download.content)
            copy_names = [
                "atlas-160.png", "atlas-160-manifest.json", "atlas-80.png", "atlas-80-manifest.json",
                "preview-160-native-petrol-3loops.mp4", "preview-80-native-petrol-3loops.mp4",
                "all-frames-160-light.png", "all-frames-160-dark.png", "all-frames-160-petrol.png",
                "all-frames-80-light.png", "all-frames-80-dark.png", "all-frames-80-petrol.png",
                "spatial-export.zip", "spatial-export-result.json", "spatial-verification.json", "spatial-timings.json", "preview.html",
            ]
            for name in copy_names:
                shutil.copyfile(workdir / name, OUT / name)
            with zipfile.ZipFile(OUT / "api-job-download.zip") as archive:
                bad_member = archive.testzip()
                if bad_member is not None:
                    raise RuntimeError(f"API ZIP CRC failure: {bad_member}")
            result = json.loads((OUT / "spatial-export-result.json").read_text(encoding="utf-8"))
            verification = json.loads((OUT / "spatial-verification.json").read_text(encoding="utf-8"))
            finish(exporting, zip_sha256=sha(OUT / "api-job-download.zip"), selected_indices=result["selected_indices"], geometry=result["geometry"], verification_status=verification["status"])

        source_receipt = json.loads((OUT / "source-request-receipt.json").read_text(encoding="utf-8"))
        source_submit = datetime.fromisoformat(source_receipt["timings"][1]["started_utc"].replace("Z", "+00:00"))
        artifact_ready = datetime.now(timezone.utc)
        recovery.update({
            "status": "artifact_ready_pending_parent_visual_inspection",
            "ended_at_utc": utc(),
            "job_id": job_id,
            "selected_candidate": review["selected_candidate"],
            "selected_sampling": sampling,
            "final_outputs": {
                "api_zip": {"file": "api-job-download.zip", "sha256": sha(OUT / "api-job-download.zip")},
                "spatial_zip": {"file": "spatial-export.zip", "sha256": sha(OUT / "spatial-export.zip")},
                "atlas_160": {"file": "atlas-160.png", "sha256": sha(OUT / "atlas-160.png")},
                "atlas_80": {"file": "atlas-80.png", "sha256": sha(OUT / "atlas-80.png")},
            },
            "recovery_pipeline_runtime_seconds": round(time.monotonic() - recovery_start, 6),
            "original_source_submission_to_final_artifact_wall_seconds_including_intervention_gap": round((artifact_ready - source_submit).total_seconds(), 6),
            "intervention_gap_not_subtracted": True,
            "artifact_ready_at_utc": artifact_ready.isoformat().replace("+00:00", "Z"),
            "source_new_and_cache_miss_verified": all(item["new_cache_entry"] for item in ingest["items"]),
        })
        update_report(report, recovery)
        append_trace("recovery_artifact_ready", recovery_start, job_id=job_id, selected_indices=result["selected_indices"], api_zip_sha256=sha(OUT / "api-job-download.zip"))
        return 0
    except Exception as error:
        recovery.update(status="recovery_stopped_or_rejected", ended_at_utc=utc(), error=str(error), recovery_pipeline_runtime_seconds=round(time.monotonic() - recovery_start, 6))
        update_report(report, recovery)
        append_trace("recovery_stopped", recovery_start, error=str(error), no_source_retry=True)
        return 1
    finally:
        stop_server(process)


if __name__ == "__main__":
    raise SystemExit(run())
