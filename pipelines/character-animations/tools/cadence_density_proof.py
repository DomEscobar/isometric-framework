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

import pipeline
from runner import AUTOMATIC_REVIEW_MODEL, DENSITY_POLICY, DENSITY_POLICY_HASH, sparse_cycle_sampling
from spatial_export import lookup_cached_cutout
from store import Store

BASELINE = ROOT / "review/real-cold-e2e-01"
OUT = ROOT / "review/cadence-uninterrupted"
PHASE = OUT / "phase1-density-proof"
SOURCE = BASELINE / "source-video.mp4"
REFERENCE = ROOT / "artifacts/minimax-ne-source-01/reference.png"
ORIGINAL_REVIEW = BASELINE / "automatic-review-result.json"
ORIGINAL_ANALYSIS = BASELINE / "automatic-review-analysis.json"
OLD_CACHE = BASELINE / "recovery-cutout-cache"
SOURCE_SHA256 = "b0a962f49467df55859e838187430d05c3581e044e373f8f19655a1f0db4d2b2"
OLD_REVIEW_SHA256 = "ab0dcdfbbbd4c023ab434c74b38168431f7a3e4465598b0eec99fdfdc7c79a2e"
REMOVAL_UNIT_USD = 0.004
TASK_CAP_USD = 2.0
PRIOR_CUMULATIVE_USD = 2.11847175
HOST = "127.0.0.1"
PORT = 4407
BASE_URL = f"http://{HOST}:{PORT}"


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


def load_wavespeed_key() -> str:
    for line in Path("/root/.hermes/.env").read_text(encoding="utf-8").splitlines():
        if line.startswith("WAVESPEED_API_KEY="):
            value = line.split("=", 1)[1].strip().strip("'\"")
            if value:
                return value
    raise RuntimeError("WaveSpeed credential unavailable")


def get_json(url: str, key: str | None = None) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


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
    log = log_path.open("wb")
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
            if httpx.get(BASE_URL + "/health", timeout=2).status_code == 200:
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


def main() -> int:
    if PHASE.exists():
        raise RuntimeError("phase-1 output already exists; preserving prior artifacts")
    PHASE.mkdir(parents=True)
    PHASE.chmod(0o700)
    started = utc()
    start_mono = time.monotonic()
    report: dict[str, Any] = {
        "status": "running",
        "started_at_utc": started,
        "source_regenerated": False,
        "reviewer_called": False,
        "original_approved_outputs_preserved": True,
        "stages": [],
    }
    write_json(PHASE / "REPORT.json", report)
    process: subprocess.Popen[bytes] | None = None

    def stage(name: str) -> tuple[str, str, float]:
        return name, utc(), time.monotonic()

    def finish(marker: tuple[str, str, float], **details: Any) -> None:
        report["stages"].append({
            "stage": marker[0], "started_at_utc": marker[1], "ended_at_utc": utc(),
            "duration_seconds": round(time.monotonic() - marker[2], 6), **details,
        })
        write_json(PHASE / "REPORT.json", report)

    try:
        preflight = stage("preflight_quote_fx_balance_and_reservation")
        if sha(SOURCE) != SOURCE_SHA256 or sha(ORIGINAL_REVIEW) != OLD_REVIEW_SHA256:
            raise RuntimeError("immutable source or reviewer receipt hash changed")
        wavespeed_key = load_wavespeed_key()
        balance = float(get_json("https://api.wavespeed.ai/api/v3/balance", wavespeed_key)["data"]["balance"])
        fx_xml = urllib.request.urlopen("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml", timeout=30).read().decode()
        usd_per_eur = float(re.search(r"currency=['\"]USD['\"] rate=['\"]([0-9.]+)", fx_xml).group(1))
        fx_date = re.search(r"time=['\"]([0-9-]+)", fx_xml).group(1)
        review = json.loads(ORIGINAL_REVIEW.read_text(encoding="utf-8"))
        candidate = review["selected_candidate"]
        sampling = sparse_cycle_sampling(candidate, native_fps=24.0)
        if sampling["indices"] != list(range(44, 74)) or sampling["playback_fps"] != 24.0:
            raise RuntimeError("density policy did not select exact native cadence")
        removal_reserve = len(sampling["indices"]) * REMOVAL_UNIT_USD
        if removal_reserve > TASK_CAP_USD or PRIOR_CUMULATIVE_USD + removal_reserve > 20 * usd_per_eur:
            raise RuntimeError("density-proof reservation exceeds authorized cap")
        reservation = {
            "fetched_at_utc": utc(),
            "wavespeed_balance_usd": balance,
            "remover": {
                "model": "wavespeed-ai/image-background-remover", "required": ["image"],
                "unit_quote_usd": REMOVAL_UNIT_USD, "quote_source": "fresh WaveSpeed get_price/get_model_schema",
                "maximum_selected_frames": 30, "initial_reserve_usd": removal_reserve,
            },
            "task_cap_usd": TASK_CAP_USD,
            "prior_cumulative_conservative_usd": PRIOR_CUMULATIVE_USD,
            "ecb_fx": {"date": fx_date, "usd_per_eur": usd_per_eur, "ceiling_eur": 20, "ceiling_usd": 20 * usd_per_eur},
        }
        write_json(PHASE / "pricing-reservation.json", reservation, 0o444)
        finish(preflight, reservation=reservation)

        setup = stage("immutable_review_bound_density_extraction_and_cache_inventory")
        data_dir = PHASE / "private-service-data"
        cache_dir = PHASE / "cutout-cache"
        shutil.copytree(OLD_CACHE, cache_dir)
        store = Store(data_dir / "jobs.sqlite3", data_dir / "jobs")
        job = store.create_job("reference.png", {"run": "cadence-density-proof", "review_reuse": "representation-only"}, REFERENCE.read_bytes())
        job_id = job["id"]
        workdir = store.job_dir(job_id)
        shutil.copyfile(SOURCE, workdir / "video-output.mp4")
        shutil.copyfile(ORIGINAL_REVIEW, workdir / "automatic-review-result.json")
        shutil.copyfile(ORIGINAL_ANALYSIS, workdir / "automatic-review-analysis.json")
        with store.connect() as connection:
            store.upsert_artifact(connection, job_id, "video-output.mp4", "retained_source", workdir / "video-output.mp4")
        source_artifact = store.get_artifact(job_id, "video-output.mp4")
        review_id = "reused-" + review["response_id"][-24:].replace("-", "")
        density_receipt = {
            "schema": "animation-selection-density-v1",
            "policy": {**DENSITY_POLICY, "sha256": DENSITY_POLICY_HASH},
            "source": {"file": "video-output.mp4", "sha256": SOURCE_SHA256, "revision": source_artifact["revision"]},
            "reviewer_receipt": {"file": "automatic-review-result.json", "sha256": OLD_REVIEW_SHA256},
            "review_id": review_id,
            "review_model": AUTOMATIC_REVIEW_MODEL,
            "approved_candidate": {
                "id": candidate["id"], "start_source_frame_index": 44, "end_source_frame_index": 74,
            },
            "sampling": sampling,
            "representation_only": True,
            "reviewer_decision_mutated": False,
            "new_reviewer_call_made": False,
        }
        write_json(workdir / "selection-density-receipt.json", density_receipt, 0o444)
        density_sha = sha(workdir / "selection-density-receipt.json")
        extraction = pipeline.run_stage("extract_frames", workdir, {
            "input": "video-output.mp4", "fps": 24.0, "indices": sampling["indices"], "output_prefix": "selected",
            "automatic_review": {
                "id": review_id, "model": AUTOMATIC_REVIEW_MODEL, "source_sha256": SOURCE_SHA256,
                "density_receipt": "selection-density-receipt.json", "density_receipt_sha256": density_sha,
                "density_policy_sha256": DENSITY_POLICY_HASH,
            },
        })
        automatic_stage = store.enqueue_stage(job_id, "automatic_review", {"reuse": "immutable-representation-only"})
        claimed = store.claim_next_stage("density-proof-setup")
        if not claimed or claimed["id"] != automatic_stage["id"]:
            raise RuntimeError("failed to claim synthetic publication stage")
        artifact_names = ["automatic-review-analysis.json", "automatic-review-result.json", "selection-density-receipt.json", *extraction["artifacts"]]
        record = {
            "id": review_id, "status": "approved", "model": AUTOMATIC_REVIEW_MODEL,
            "source_artifact": "video-output.mp4", "source_sha256": SOURCE_SHA256, "source_revision": source_artifact["revision"],
            "analysis_artifact": "automatic-review-analysis.json", "result_artifact": "automatic-review-result.json",
            "candidate_count": len(json.loads(ORIGINAL_ANALYSIS.read_text())["candidates"]), "local_hard_failures": [],
            "selected_candidate": candidate, "selected_sampling": sampling, "reason": None,
            "usage": review.get("usage"), "budget": review.get("budget"), "paid_transport_called": False,
            "response_id": review["response_id"], "provider": review.get("provider"),
            "reuse": {"representation_only": True, "original_reviewer_receipt_sha256": OLD_REVIEW_SHA256},
        }
        store.finish_automatic_review(claimed, {"status": "needs_review", "artifacts": artifact_names, "details": {}}, artifact_names, record)
        selected_paths = [workdir / f"selected-frame-{order:04d}.png" for order in range(30)]
        cached = [lookup_cached_cutout(path, cache_dir, "waldlicht-removal-v1", "wavespeed-image-background-remover-output-v1") for path in selected_paths]
        hits = [order for order, value in enumerate(cached) if value is not None]
        missing = [order for order, value in enumerate(cached) if value is None]
        if hits != list(range(0, 30, 3)) or len(missing) != 20:
            raise RuntimeError(f"unexpected cache inventory: hits={hits}, missing={missing}")
        reservation["remover"].update({"cache_hits": 10, "missing_frames": 20, "revised_reserve_usd": len(missing) * REMOVAL_UNIT_USD})
        write_json(PHASE / "pricing-reservation.json", reservation, 0o444)
        finish(setup, job_id=job_id, sampling=sampling, cache_hit_orders=hits, missing_orders=missing)

        token = secrets.token_urlsafe(36)
        environment = os.environ.copy()
        environment.update({
            "ANIMATION_API_TOKEN": token, "ANIMATION_DATA_DIR": str(data_dir),
            "ANIMATION_PAID_ENABLED": "1", "ANIMATION_MAX_STAGE_USD": "0.50",
            "WAVESPEED_API_KEY": wavespeed_key, "ANIMATION_REMOVAL_MAX_INFLIGHT": "1",
            "ANIMATION_CUTOUT_CACHE_DIR": str(cache_dir), "ANIMATION_REVIEW_ENABLED": "0",
        })
        process = start_server(environment, PHASE / "isolated-server.log")
        headers = {"Authorization": f"Bearer {token}"}
        with httpx.Client(base_url=BASE_URL, timeout=30) as client:
            removal = stage("missing_native_frame_removal_and_cache_ingest")
            missing_names = [f"selected-frame-{order:04d}.png" for order in missing]
            prediction_ids: set[str] = set()
            for _ in range(700):
                response = client.post(f"/v1/jobs/{job_id}/stages", headers=headers, json={
                    "stage": "remove_background", "params": {"inputs": missing_names, "preset": "waldlicht-removal-v1"},
                    "authorize_paid": True, "budget_cap_usd": len(missing_names) * REMOVAL_UNIT_USD,
                })
                response.raise_for_status()
                ended = wait_job(client, headers, job_id, 300)
                state = json.loads((workdir / "remove-background-state.json").read_text(encoding="utf-8"))
                prediction_ids.update(item["prediction_id"] for item in state["items"] if isinstance(item.get("prediction_id"), str))
                if any(item.get("status") == "submission_unknown" for item in state["items"]):
                    raise RuntimeError("remover submission ambiguous; no resubmit")
                if state.get("status") == "completed":
                    break
                if ended["state"] == "failed":
                    raise RuntimeError(ended.get("message") or "removal failed")
                time.sleep(1)
            else:
                raise RuntimeError("known remover predictions timed out")
            ingest = json.loads((workdir / "cutout-cache-ingest.json").read_text(encoding="utf-8"))
            if len(ingest["items"]) != 20 or not all(item["new_cache_entry"] for item in ingest["items"]):
                raise RuntimeError("missing-frame cache ingest mismatch")
            finish(removal, prediction_ids=sorted(prediction_ids), count=20, maximum_inflight=1)

            exporting = stage("authenticated_api_spatial_export_verify_and_download")
            response = client.post(f"/v1/jobs/{job_id}/stages", headers=headers, json={
                "stage": "spatial_export", "params": {
                    "source": "video-output.mp4", "selection_receipt": "automatic-review-result.json",
                    "selection_mode": "automatic_model_validated", "export_preset": "derived-native-160-80-v1",
                    "removal_preset": "waldlicht-removal-v1", "removal_recipe": "wavespeed-image-background-remover-output-v1",
                },
            })
            response.raise_for_status()
            exported = wait_job(client, headers, job_id, 300)
            if exported["state"] != "completed":
                raise RuntimeError(exported.get("message") or "spatial export failed")
            download = client.get(f"/v1/jobs/{job_id}/download", headers=headers)
            download.raise_for_status()
            (PHASE / "api-job-download.zip").write_bytes(download.content)
            with zipfile.ZipFile(PHASE / "api-job-download.zip") as archive:
                if archive.testzip() is not None:
                    raise RuntimeError("API ZIP CRC failure")
            copy_names = [
                "atlas-160.png", "atlas-160-manifest.json", "atlas-80.png", "atlas-80-manifest.json",
                "preview-160-native-petrol-3loops.mp4", "preview-80-native-petrol-3loops.mp4",
                "all-frames-160-light.png", "all-frames-160-dark.png", "all-frames-160-petrol.png",
                "all-frames-80-light.png", "all-frames-80-dark.png", "all-frames-80-petrol.png",
                "spatial-export.zip", "spatial-export-result.json", "spatial-verification.json", "spatial-timings.json",
                "preview.html", "selection-density-receipt.json", "extract-frames.json", "cutout-cache-ingest.json",
                "remove-background-state.json",
            ]
            for name in copy_names:
                shutil.copyfile(workdir / name, PHASE / name)
            finish(exporting, api_zip_sha256=sha(PHASE / "api-job-download.zip"), spatial_zip_sha256=sha(PHASE / "spatial-export.zip"))

        comparison = stage("sparse_vs_dense_native_160_comparison")
        shutil.copyfile(BASELINE / "preview-160-native-petrol-3loops.mp4", PHASE / "original-10frames-160-3loops.mp4")
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-i", str(PHASE / "original-10frames-160-3loops.mp4"),
            "-i", str(PHASE / "preview-160-native-petrol-3loops.mp4"),
            "-filter_complex", "[0:v]fps=24,scale=160:160:flags=neighbor[left];[1:v]fps=24,scale=160:160:flags=neighbor[right];[left][right]hstack=inputs=2[v]",
            "-map", "[v]", "-t", "3.75", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(PHASE / "cadence-comparison-160.mp4"),
        ], check=True, timeout=120)
        index_proof = {
            "source_sha256": SOURCE_SHA256, "approved_interval": [44, 74], "native_fps": 24.0,
            "duration_seconds": 1.25,
            "original_sparse": {"indices": list(range(44, 74, 3)), "frame_count": 10, "playback_fps": 8.0},
            "dense": {"indices": list(range(44, 74)), "frame_count": 30, "playback_fps": 24.0},
            "same_interval": True, "same_duration": True, "synthetic_frames": False,
        }
        write_json(PHASE / "source-index-proof.json", index_proof, 0o444)
        finish(comparison, comparison_file="cadence-comparison-160.mp4", source_index_proof=index_proof)

        spatial = json.loads((PHASE / "spatial-export-result.json").read_text())
        verification = json.loads((PHASE / "spatial-verification.json").read_text())
        report.update({
            "status": "phase1_artifact_ready_pending_independent_visual_inspection",
            "ended_at_utc": utc(), "wall_seconds": round(time.monotonic() - start_mono, 6),
            "job_id": job_id, "sampling": sampling, "verification": verification,
            "cost": {
                "known_billed_usd": 0.0, "open_liability_usd": 0.08,
                "phase1_conservative_maximum_usd": 0.08,
                "task_cap_usd": TASK_CAP_USD,
                "cumulative_conservative_maximum_usd": round(PRIOR_CUMULATIVE_USD + 0.08, 9),
            },
            "outputs": {
                "native_160_mp4": {"file": "preview-160-native-petrol-3loops.mp4", "sha256": sha(PHASE / "preview-160-native-petrol-3loops.mp4")},
                "spatial_zip": {"file": "spatial-export.zip", "sha256": sha(PHASE / "spatial-export.zip")},
                "api_zip": {"file": "api-job-download.zip", "sha256": sha(PHASE / "api-job-download.zip")},
                "atlas_160": {"file": "atlas-160.png", "sha256": sha(PHASE / "atlas-160.png")},
                "atlas_80": {"file": "atlas-80.png", "sha256": sha(PHASE / "atlas-80.png")},
                "comparison": {"file": "cadence-comparison-160.mp4", "sha256": sha(PHASE / "cadence-comparison-160.mp4")},
            },
            "spatial_result": spatial,
        })
        write_json(PHASE / "REPORT.json", report)
        return 0
    except Exception as error:
        report.update(status="phase1_stopped", ended_at_utc=utc(), error=str(error), wall_seconds=round(time.monotonic() - start_mono, 6))
        write_json(PHASE / "REPORT.json", report)
        return 1
    finally:
        stop_server(process)


if __name__ == "__main__":
    raise SystemExit(main())
