#!/usr/bin/env python3
"""Resume compact8-cold-01 after one malformed reviewer response; never regenerate source."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import animation_review
try:
    import real_cold_e2e as harness
except ModuleNotFoundError:  # Imported as tools.compact8_recovery by tests.
    from tools import real_cold_e2e as harness

OUT = ROOT / "review/compact8-cold-01"
DATA = OUT / "private-service-data"
CACHE = OUT / "cutout-cache"
REVIEW_OUTPUT = 1200
REVIEW_CAP = 0.05
REMOVAL_UNIT = 0.004
MAX_INFLIGHT = 5
INCREMENTAL_CAP = 1.5
SOURCE_SHA = "d04dc78a89a1b85164f86350f77bddb10e17121a3929f8effff9d60f062aa751"
SOURCE_PREDICTION = "90fdbc4b1f6d4203b0f448cc45a652da"
CORE_FILES = [
    "animation_review.py", "pipeline.py", "provider.py", "quality_gates.py", "runner.py",
    "spatial_export.py", "store.py", "app.py", "tools/real_cold_e2e.py", "tools/compact8_recovery.py",
]


def utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_name("." + path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def event(name: str, **data: object) -> None:
    trace = OUT / "redacted-trace.jsonl"
    sequence = sum(1 for _ in trace.open(encoding="utf-8")) + 1
    record = {"sequence": sequence, "utc": utc(), "event": name, "recovery": True, **data}
    with trace.open("a", encoding="utf-8") as output:
        output.write(json.dumps(record, sort_keys=True) + "\n")


def wait_stage_id(database: Path, stage_id: str, timeout: float, interval: float = 0.25) -> dict:
    """Wait for the exact queued stage; unrelated terminal job state cannot satisfy this wait."""
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        with sqlite3.connect(database) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT id,state,error,result_json FROM stage_jobs WHERE id=?", (stage_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError("queued stage disappeared")
        record = dict(row)
        if record["state"] not in {"queued", "running"}:
            record["result"] = json.loads(record.pop("result_json")) if record["result_json"] else None
            return record
        time.sleep(interval)
    raise RuntimeError(f"exact stage {stage_id} timed out")


def automatic_review_for_stage(database: Path, stage_id: str) -> dict:
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT record_json FROM automatic_reviews WHERE stage_job_id=?", (stage_id,),
        ).fetchone()
    if row is None:
        raise RuntimeError("completed automatic-review stage lacks its matching persisted review")
    return json.loads(row[0])


def update_costs(ledger: dict) -> None:
    known = sum(float(entry.get("known_billed_usd") or 0) for entry in ledger["entries"])
    opened = sum(float(entry.get("open_liability_usd") or 0) for entry in ledger["entries"])
    maximum = known + opened
    if maximum > INCREMENTAL_CAP + 1e-12:
        raise RuntimeError("original incremental cap exceeded before charge")
    prior = float(ledger["prior_reconciliation"]["maximum_accounted_usd"])
    ceiling = float(ledger["cumulative_ceiling_usd"])
    if prior + maximum > ceiling + 1e-12:
        raise RuntimeError("cumulative EUR-derived ceiling exceeded before charge")
    ledger.update(
        known_billed_usd=round(known, 9), open_liability_usd=round(opened, 9),
        maximum_accounted_usd=round(maximum, 9), updated_at_utc=utc(),
    )
    write_json(OUT / "cost-ledger.json", ledger)


def set_entry(ledger: dict, entry_id: str, **values: object) -> None:
    entry = next((item for item in ledger["entries"] if item["id"] == entry_id), None)
    if entry is None:
        entry = {"id": entry_id}
        ledger["entries"].append(entry)
    entry.update(values)
    update_costs(ledger)


def finish_report(report: dict, ledger: dict, recovery: dict, *, status: str, error: str | None = None) -> None:
    recovery.update(status=status, ended_at_utc=utc())
    report.update(
        status=status,
        ended_at_utc=utc(),
        cost=ledger,
        recovery=recovery,
        error=error,
        visual_quality_certified=False,
    )
    write_json(OUT / "REPORT.json", report)
    (OUT / "REPORT.md").write_text(
        "# Real cold end-to-end run 01\n\n"
        f"Status: {status}\n\n"
        "The original review failed with provider-supplied incomplete JSON. Recovery reused the immutable paid source and permitted one bounded review retry.\n\n"
        "## Current evidence\n\n" + json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def copy_outputs(workdir: Path) -> None:
    names = [
        "atlas-160.png", "atlas-160-manifest.json", "atlas-80.png", "atlas-80-manifest.json",
        "preview-160-native-petrol-3loops.mp4", "preview-80-native-petrol-3loops.mp4",
        "all-frames-160-light.png", "all-frames-160-dark.png", "all-frames-160-petrol.png",
        "all-frames-80-light.png", "all-frames-80-dark.png", "all-frames-80-petrol.png",
        "spatial-export.zip", "spatial-export-result.json", "spatial-verification.json", "spatial-timings.json",
        "preview.html", "cutout-cache-ingest.json", "extract-frames.json", "selection-density-receipt.json",
        "automatic-review-result.json", "automatic-review-analysis.json", "remove-background-state.json",
    ]
    for name in names:
        if (workdir / name).exists():
            shutil.copyfile(workdir / name, OUT / name)


def main() -> int:
    started = time.monotonic()
    report = json.loads((OUT / "REPORT.json").read_text(encoding="utf-8"))
    ledger = json.loads((OUT / "cost-ledger.json").read_text(encoding="utf-8"))
    receipt = json.loads((OUT / "source-request-receipt.json").read_text(encoding="utf-8"))
    if receipt["prediction_id"] != SOURCE_PREDICTION or receipt["output"]["sha256"] != SOURCE_SHA:
        raise RuntimeError("immutable paid source receipt mismatch")
    if sha(OUT / "source-video.mp4") != SOURCE_SHA:
        raise RuntimeError("immutable paid source file mismatch")
    failed = report.get("automatic_review") or {}
    if (failed.get("diagnostic") or {}).get("type") != "invalid_json" or failed.get("approved") is not False:
        raise RuntimeError("recovery is permitted only for the recorded invalid-JSON review")

    recovery = {
        "status": "running", "started_at_utc": utc(), "source_reused": True,
        "source_generation_requests": 0, "authorized_review_retries": 1,
        "review_retry_policy": "one retry only after a definite HTTP 200 response containing provider-supplied invalid JSON",
        "original_review_preserved": failed,
    }
    process = None
    try:
        with sqlite3.connect(DATA / "jobs.sqlite3") as connection:
            jobs = connection.execute("SELECT id FROM jobs").fetchall()
        if len(jobs) != 1:
            raise RuntimeError("expected exactly one existing cold-run job")
        job_id = jobs[0][0]
        workdir = DATA / "jobs" / job_id
        archive = OUT / "failed-review-01"
        archive.mkdir(exist_ok=True)
        for name in ("automatic-review-raw-message.txt", "automatic-review-result.json"):
            source = workdir / name
            if source.exists() and not (archive / name).exists():
                shutil.copyfile(source, archive / name)

        ork, wsk = harness.load_keys()
        _, keyinfo = harness.get_json("https://openrouter.ai/api/v1/key", ork)
        _, models = harness.get_json("https://openrouter.ai/api/v1/models")
        model = next(item for item in models["data"] if item.get("id") == harness.REVIEW_MODEL)
        supported = set(model.get("supported_parameters") or [])
        if not {"response_format", "structured_outputs", "reasoning", "max_tokens"} <= supported:
            raise RuntimeError("exact reviewer no longer advertises required strict-output/reasoning parameters")
        prompt_price = float(model["pricing"]["prompt"])
        completion_price = float(model["pricing"]["completion"])
        metadata = {
            "fetched_at_utc": utc(), "source": "https://openrouter.ai/api/v1/models", "id": harness.REVIEW_MODEL,
            "canonical_slug": model.get("canonical_slug"), "context_length": int(model["context_length"]),
            "architecture": model["architecture"], "supported_parameters": model["supported_parameters"],
            "pricing": model["pricing"], "fixed_run_price_claimed": False,
        }
        write_json(OUT / "openrouter-model-metadata.json", metadata)

        analysis = json.loads((workdir / "automatic-review-analysis.json").read_text(encoding="utf-8"))
        source_artifact = None
        with sqlite3.connect(DATA / "jobs.sqlite3") as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT name,sha256,revision FROM artifacts WHERE job_id=? AND name='video-output.mp4'", (job_id,),
            ).fetchone()
            source_artifact = dict(row) if row else None
        if not source_artifact or source_artifact["sha256"] != SOURCE_SHA or source_artifact["revision"] != 1:
            raise RuntimeError("existing source artifact revision is not immutable revision 1")
        probe = animation_review.build_review_request(
            workdir, "video-output.mp4", analysis, max_tokens=REVIEW_OUTPUT,
            request_binding={"request_id": "0" * 32, "source_sha256": SOURCE_SHA, "source_revision": 1},
        )
        evidence = probe["_review_evidence"]
        max_input = int(evidence["conservative_input_token_bound"])
        review_reserve = max_input * prompt_price + REVIEW_OUTPUT * completion_price
        if review_reserve > REVIEW_CAP + 1e-12:
            raise RuntimeError("fresh bounded review quote exceeds authorized retry cap")
        removal_reserve = 8 * REMOVAL_UNIT
        set_entry(
            ledger, "new-openrouter-review-retry", reserved_usd=round(review_reserve, 9), known_billed_usd=None,
            open_liability_usd=round(review_reserve, 9), status="reserved",
            basis={"model": harness.REVIEW_MODEL, "max_input_tokens": max_input, "max_output_tokens": REVIEW_OUTPUT,
                   "reasoning": {"effort": "low", "exclude": True}, "strict_json_schema": True,
                   "prices_usd_per_token": {"prompt": prompt_price, "completion": completion_price}},
        )
        set_entry(
            ledger, "new-removals", reserved_usd=removal_reserve, known_billed_usd=None,
            open_liability_usd=removal_reserve, status="reserved",
            basis={"model": harness.REMOVER, "max_frames": 8, "unit_quote_usd": REMOVAL_UNIT,
                   "quote_fetched_for_recovery": True},
        )
        recovery["preflight"] = {
            "review_reserve_usd": review_reserve, "review_cap_usd": REVIEW_CAP,
            "removal_reserve_usd": removal_reserve,
            "attempt_maximum_accounted_usd": ledger["maximum_accounted_usd"],
            "cumulative_maximum_accounted_usd": round(
                ledger["prior_reconciliation"]["maximum_accounted_usd"] + ledger["maximum_accounted_usd"], 9
            ),
            "openrouter_limit_remaining": keyinfo["data"].get("limit_remaining"),
        }
        hashes = {name: sha(ROOT / name) for name in CORE_FILES}
        write_json(OUT / "RECOVERY_FROZEN_CONFIG.json", {
            "files": hashes, "frame_policy": "8", "maximum_inflight": 5, "review_output_tokens": REVIEW_OUTPUT,
            "review_retry_cap_usd": REVIEW_CAP, "source_generation_requests": 0,
        })
        event("recovery_preflight_reserved", **recovery["preflight"])
        finish_report(report, ledger, recovery, status="recovery_running")

        token = secrets.token_urlsafe(36)
        env = os.environ.copy()
        env.update({
            "ANIMATION_API_TOKEN": token, "ANIMATION_DATA_DIR": str(DATA), "ANIMATION_REVIEW_ENABLED": "1",
            "ANIMATION_REVIEW_MAX_USD": str(review_reserve), "ANIMATION_REVIEW_MAX_INPUT_TOKENS": str(max_input),
            "ANIMATION_REVIEW_MAX_OUTPUT_TOKENS": str(REVIEW_OUTPUT),
            "ANIMATION_REVIEW_MODEL_METADATA_FILE": str(OUT / "openrouter-model-metadata.json"),
            "OPENROUTER_API_KEY": ork, "ANIMATION_PAID_ENABLED": "1", "ANIMATION_MAX_STAGE_USD": "0.50",
            "WAVESPEED_API_KEY": wsk, "ANIMATION_REMOVAL_MAX_INFLIGHT": str(MAX_INFLIGHT),
            "ANIMATION_CUTOUT_CACHE_DIR": str(CACHE),
        })
        harness.HOST, harness.PORT = "127.0.0.1", 4418
        harness.BASE = "http://127.0.0.1:4418"
        process = harness.start_server(env, OUT / "isolated-recovery-server.log")
        headers = {"Authorization": f"Bearer {token}"}
        recovery_start = time.monotonic()
        with httpx.Client(base_url=harness.BASE, timeout=30) as client:
            request_started = time.monotonic()
            response = client.post(
                f"/v1/jobs/{job_id}/automatic-review", headers=headers,
                json={"artifact": "video-output.mp4", "sha256": SOURCE_SHA, "revision": 1,
                      "authorize_paid_review": True, "budget_cap_usd": review_reserve, "frame_policy": "8"},
            )
            response.raise_for_status()
            review_stage_id = response.json()["id"]
            review_stage = wait_stage_id(DATA / "jobs.sqlite3", review_stage_id, 300)
            if review_stage["state"] != "completed":
                raise RuntimeError(review_stage.get("error") or "review stage failed")
            retry_review = automatic_review_for_stage(DATA / "jobs.sqlite3", review_stage_id)
            review_result = json.loads((workdir / "automatic-review-result.json").read_text(encoding="utf-8"))
            shutil.copyfile(workdir / "automatic-review-result.json", OUT / "automatic-review-retry-result.json")
            budget = review_result.get("budget") or {}
            actual = budget.get("actual_cost_usd")
            if isinstance(actual, (int, float)):
                set_entry(
                    ledger, "new-openrouter-review-retry", reserved_usd=round(review_reserve, 9),
                    known_billed_usd=round(float(actual), 9), open_liability_usd=0.0, status="known_billed",
                    provider_reference=review_result.get("response_id"),
                    basis=next(x for x in ledger["entries"] if x["id"] == "new-openrouter-review-retry")["basis"],
                )
            else:
                set_entry(
                    ledger, "new-openrouter-review-retry", status="completed_cost_unknown",
                    provider_references=[x for x in [review_result.get("response_id")] if x],
                )
            recovery["review_retry"] = {
                "duration_seconds": round(time.monotonic() - request_started, 6),
                "status": retry_review["status"], "response_id": review_result.get("response_id"),
                "usage": review_result.get("usage"), "budget": budget,
                "reasoning_configuration": {"effort": "low", "exclude": True},
                "strict_json_schema": True,
                "stage_id": review_stage_id,
            }
            event("review_retry_finished", **recovery["review_retry"])
            if retry_review["status"] != "approved":
                set_entry(ledger, "new-removals", reserved_usd=0.0, open_liability_usd=0.0,
                          status="not_started_reviewer_nonapproval")
                raise RuntimeError("authorized review retry did not approve the source")

            sampling = retry_review["selected_sampling"]
            if sampling["frame_policy"]["option"] != "8" or len(sampling["indices"]) != 8:
                raise RuntimeError("approved retry did not produce exact compact8 sampling")
            current = client.get(f"/v1/jobs/{job_id}", headers=headers).json()
            selected = sorted(
                [item for item in current["artifacts"] if item["name"].startswith("selected-frame-")],
                key=lambda item: item["name"],
            )
            if len(selected) != 8:
                raise RuntimeError("automatic extraction did not produce eight selected originals")
            for artifact in selected:
                harness.approve(client, headers, job_id, artifact)

            removal_started = time.monotonic()
            prediction_ids: set[str] = set()
            for _ in range(500):
                queued = client.post(
                    f"/v1/jobs/{job_id}/stages", headers=headers,
                    json={"stage": "remove_background", "params": {
                        "inputs": [item["name"] for item in selected], "preset": "waldlicht-removal-v1"},
                        "authorize_paid": True, "budget_cap_usd": removal_reserve},
                )
                queued.raise_for_status()
                ended = wait_stage_id(DATA / "jobs.sqlite3", queued.json()["id"], 240)
                state = json.loads((workdir / "remove-background-state.json").read_text(encoding="utf-8"))
                prediction_ids.update(
                    item["prediction_id"] for item in state["items"] if isinstance(item.get("prediction_id"), str)
                )
                if any(item.get("status") == "submission_unknown" for item in state["items"]):
                    set_entry(ledger, "new-removals", status="ambiguous_submission",
                              provider_references=sorted(prediction_ids))
                    raise RuntimeError("remover submission ambiguous")
                if state.get("status") == "completed":
                    break
                if ended["state"] == "failed":
                    raise RuntimeError(ended.get("error") or "removal failed")
                time.sleep(1)
            else:
                set_entry(ledger, "new-removals", status="known_predictions_pending",
                          provider_references=sorted(prediction_ids))
                raise RuntimeError("known remover predictions timed out")
            set_entry(
                ledger, "new-removals", status="completed_charge_not_authoritatively_reported",
                provider_references=sorted(prediction_ids),
            )
            ingest = json.loads((workdir / "cutout-cache-ingest.json").read_text(encoding="utf-8"))
            recovery["removal"] = {
                "duration_seconds": round(time.monotonic() - removal_started, 6),
                "prediction_ids": sorted(prediction_ids), "frame_count": len(ingest["items"]),
                "maximum_inflight": state.get("maximum_inflight"),
                "observed_maximum_inflight": state.get("observed_maximum_inflight"),
                "rate_limit_events": state.get("rate_limit_events", 0),
            }
            if recovery["removal"]["observed_maximum_inflight"] != 5:
                raise RuntimeError("actual remover concurrency did not reach five")
            event("recovery_removal_finished", **recovery["removal"])

            export_started = time.monotonic()
            queued = client.post(
                f"/v1/jobs/{job_id}/stages", headers=headers,
                json={"stage": "spatial_export", "params": {
                    "source": "video-output.mp4", "selection_receipt": "automatic-review-result.json",
                    "selection_mode": "automatic_model_validated", "export_preset": "derived-native-160-80-v1",
                    "removal_preset": "waldlicht-removal-v1",
                    "removal_recipe": "wavespeed-image-background-remover-output-v1"}},
            )
            queued.raise_for_status()
            exported = wait_stage_id(DATA / "jobs.sqlite3", queued.json()["id"], 300)
            if exported["state"] != "completed":
                raise RuntimeError(exported.get("error") or "spatial export failed")
            download = client.get(f"/v1/jobs/{job_id}/download", headers=headers)
            download.raise_for_status()
            (OUT / "api-job-download.zip").write_bytes(download.content)
            copy_outputs(workdir)
            with zipfile.ZipFile(OUT / "api-job-download.zip") as archive_zip:
                if archive_zip.testzip() is not None:
                    raise RuntimeError("API ZIP CRC validation failed")
            result = json.loads((OUT / "spatial-export-result.json").read_text(encoding="utf-8"))
            verification = json.loads((OUT / "spatial-verification.json").read_text(encoding="utf-8"))
            if len(result["selected_indices"]) != 8 or verification["status"] != "passed":
                raise RuntimeError("compact8 export verification failed")
            manifests = {
                name: json.loads((OUT / name).read_text(encoding="utf-8"))
                for name in ("atlas-160-manifest.json", "atlas-80-manifest.json")
            }
            for name, manifest in manifests.items():
                frame_count = manifest.get("frame_count", len(manifest.get("frames", [])))
                if frame_count != 8:
                    raise RuntimeError(f"{name} does not contain eight frames")
            recovery["export"] = {
                "duration_seconds": round(time.monotonic() - export_started, 6),
                "verification_status": verification["status"], "selected_indices": result["selected_indices"],
                "geometry": result["geometry"], "api_zip_sha256": sha(OUT / "api-job-download.zip"),
                "spatial_zip_sha256": sha(OUT / "spatial-export.zip"),
            }
            recovery["runtime_seconds"] = round(time.monotonic() - recovery_start, 6)
            recovery["uninterrupted_claimed"] = False
            recovery["source_sha256"] = SOURCE_SHA
            recovery["job_id"] = job_id
            recovery["selected_candidate"] = retry_review["selected_candidate"]
            recovery["selected_sampling"] = sampling
            event("recovery_artifact_ready", **recovery["export"], recovery_runtime_seconds=recovery["runtime_seconds"])

        unchanged = {name: sha(ROOT / name) == value for name, value in hashes.items()}
        write_json(OUT / "recovery-freeze-verification.json", unchanged)
        report["automatic_review_retry"] = review_result
        report["job_id"] = job_id
        report["selected_candidate"] = retry_review["selected_candidate"]
        report["selected_sampling"] = sampling
        report["final_outputs"] = {
            "api_zip": {"file": "api-job-download.zip", "sha256": sha(OUT / "api-job-download.zip")},
            "spatial_zip": {"file": "spatial-export.zip", "sha256": sha(OUT / "spatial-export.zip")},
            "atlas_160_sha256": sha(OUT / "atlas-160.png"), "atlas_80_sha256": sha(OUT / "atlas-80.png"),
        }
        report["source_new_and_cache_miss_verified"] = all(item["new_cache_entry"] for item in ingest["items"])
        finish_report(report, ledger, recovery, status="artifact_ready_pending_parent_visual_inspection")
        return 0
    except Exception as error:
        recovery["runtime_seconds"] = round(time.monotonic() - started, 6)
        event("recovery_stopped", error=str(error))
        finish_report(report, ledger, recovery, status="recovery_stopped_or_rejected", error=str(error))
        return 1
    finally:
        harness.stop_server(process)


if __name__ == "__main__":
    raise SystemExit(main())
