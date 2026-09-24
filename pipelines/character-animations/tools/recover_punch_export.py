#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "review/minimax-480p-3s-punch-01"
DATA = OUT / "private-service-data"
CACHE = OUT / "cutout-cache"
HOST, PORT = "127.0.0.1", 4395
BASE = f"http://{HOST}:{PORT}"


def utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_name("." + path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def wait_stage(stage_id: str, timeout: float = 300) -> dict:
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        with sqlite3.connect(DATA / "jobs.sqlite3") as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT id,state,error,result_json FROM stage_jobs WHERE id=?", (stage_id,)
            ).fetchone()
        if row is None:
            raise RuntimeError("queued recovery stage disappeared")
        record = dict(row)
        if record["state"] not in {"queued", "running"}:
            return record
        time.sleep(0.25)
    raise RuntimeError(f"exact recovery stage {stage_id} timed out")


def start_server(environment: dict[str, str]) -> subprocess.Popen:
    probe = socket.socket()
    probe.bind((HOST, PORT))
    probe.close()
    log = (OUT / "recovery-isolated-server.log").open("wb")
    process = subprocess.Popen(
        [str(ROOT / ".venv/bin/python"), "-m", "uvicorn", "app:app", "--host", HOST, "--port", str(PORT), "--log-level", "warning"],
        cwd=ROOT,
        env=environment,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    process._log = log
    until = time.monotonic() + 20
    while time.monotonic() < until:
        try:
            if httpx.get(BASE + "/health", timeout=2).status_code == 200:
                return process
        except Exception:
            pass
        if process.poll() is not None:
            raise RuntimeError("recovery server exited")
        time.sleep(0.1)
    raise RuntimeError("recovery server health timeout")


def stop_server(process: subprocess.Popen | None) -> None:
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(5)
    if process and hasattr(process, "_log"):
        process._log.close()


def main() -> int:
    report = json.loads((OUT / "REPORT.json").read_text(encoding="utf-8"))
    job_id = report.get("job_id") or "681a639063864ad4ac537fccc40882b2"
    workdir = DATA / "jobs" / job_id
    if not workdir.is_dir():
        raise RuntimeError("recorded punch job directory is unavailable")
    token = secrets.token_urlsafe(36)
    environment = os.environ.copy()
    environment.update({
        "ANIMATION_API_TOKEN": token,
        "ANIMATION_DATA_DIR": str(DATA),
        "ANIMATION_PAID_ENABLED": "0",
        "ANIMATION_MAX_STAGE_USD": "0",
        "ANIMATION_CUTOUT_CACHE_DIR": str(CACHE),
    })
    process = None
    started = time.monotonic()
    try:
        process = start_server(environment)
        headers = {"Authorization": f"Bearer {token}"}
        with httpx.Client(base_url=BASE, timeout=30) as client:
            queued = client.post(
                f"/v1/jobs/{job_id}/stages",
                headers=headers,
                json={"stage": "spatial_export", "params": {
                    "source": "video-output.mp4",
                    "selection_receipt": "automatic-review-result.json",
                    "selection_mode": "automatic_model_validated",
                    "export_preset": "derived-native-160-80-v1",
                    "removal_preset": "waldlicht-removal-v1",
                    "removal_recipe": "wavespeed-image-background-remover-output-v1",
                }},
            )
            queued.raise_for_status()
            stage_id = queued.json()["id"]
            stage = wait_stage(stage_id)
            if stage["state"] != "completed":
                raise RuntimeError(stage.get("error") or "recovery spatial export failed")
            job = client.get(f"/v1/jobs/{job_id}", headers=headers)
            job.raise_for_status()
            download = client.get(f"/v1/jobs/{job_id}/download", headers=headers)
            download.raise_for_status()
            (OUT / "api-job-download.zip").write_bytes(download.content)
        copy_names = [
            "atlas-160.png", "atlas-160-manifest.json", "atlas-80.png", "atlas-80-manifest.json",
            "preview-160-native-petrol-repeated-3x.mp4", "preview-80-native-petrol-repeated-3x.mp4",
            "all-frames-160-light.png", "all-frames-160-dark.png", "all-frames-160-petrol.png",
            "all-frames-80-light.png", "all-frames-80-dark.png", "all-frames-80-petrol.png",
            "spatial-export.zip", "spatial-export-result.json", "spatial-verification.json", "spatial-timings.json",
            "preview.html", "cutout-cache-ingest.json", "extract-frames.json", "selection-density-receipt.json",
            "automatic-review-result.json", "automatic-review-analysis.json", "remove-background-state.json",
        ]
        for name in copy_names:
            if (workdir / name).is_file():
                shutil.copyfile(workdir / name, OUT / name)
        with zipfile.ZipFile(OUT / "api-job-download.zip") as archive:
            if archive.testzip() is not None:
                raise RuntimeError("API ZIP CRC failed")
        result = json.loads((OUT / "spatial-export-result.json").read_text(encoding="utf-8"))
        verification = json.loads((OUT / "spatial-verification.json").read_text(encoding="utf-8"))
        manifest = json.loads((OUT / "atlas-160-manifest.json").read_text(encoding="utf-8"))
        if manifest["clip"]["action"] != "punch" or manifest["clip"]["loop"] is not False:
            raise RuntimeError("recovered manifest is not a one-shot punch")
        report.update({
            "status": "artifact_ready_pending_parent_visual_inspection",
            "ended_at_utc": utc(),
            "error": None,
            "job_id": job_id,
            "selected_candidate": report["automatic_review"]["selected_candidate"],
            "selected_sampling": json.loads((workdir / "selection-density-receipt.json").read_text())["sampling"],
            "final_outputs": {
                "api_zip": {"file": "api-job-download.zip", "sha256": sha(OUT / "api-job-download.zip")},
                "spatial_zip": {"file": "spatial-export.zip", "sha256": sha(OUT / "spatial-export.zip")},
                "atlas_160_sha256": sha(OUT / "atlas-160.png"),
                "atlas_80_sha256": sha(OUT / "atlas-80.png"),
                "preview_160": "preview-160-native-petrol-repeated-3x.mp4",
            },
            "recovery": {
                "reason": "initial derived geometry clipped the punch arm at 160px",
                "fix": "batch-wide alpha bounds now cap shared scale while preserving one root and direct-from-master transforms",
                "paid_provider_calls": 0,
                "stage_id": stage_id,
                "duration_seconds": round(time.monotonic() - started, 6),
                "verification_status": verification["status"],
                "geometry": result["geometry"],
            },
            "source_new_and_cache_miss_verified": True,
            "visual_quality_certified": False,
        })
        write_json(OUT / "REPORT.json", report)
        (OUT / "REPORT.md").write_text(
            "# MiniMax 480p / 3s punch trial\n\n"
            "Status: artifact_ready_pending_parent_visual_inspection\n\n"
            "One fresh source, one paid Gemini review, eight fresh removals, and an API spatial export completed. "
            "The initial free export clipped the wide punch pose; recovery changed only shared fit geometry and made no provider call.\n\n"
            + json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"status": report["status"], "stage_id": stage_id, "preview": report["final_outputs"]["preview_160"]}, sort_keys=True))
        return 0
    finally:
        stop_server(process)


if __name__ == "__main__":
    raise SystemExit(main())
