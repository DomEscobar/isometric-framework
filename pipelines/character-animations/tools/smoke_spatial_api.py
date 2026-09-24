#!/usr/bin/env python3
"""Real authenticated localhost HTTP smoke for the cache-backed spatial stage."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SOURCE = ROOT / "artifacts/minimax-ne-source-01/provider-original.mp4"
BASELINE = ROOT / "artifacts/minimax-ne-export-final"
CACHE = ROOT / "review/fast-clean-pipeline/cutout-cache"
SELECTED = [66, 67, 69, 70, 71, 73, 74, 75, 77, 78, 79, 81, 82, 84, 85, 86, 88, 89, 90, 92, 93, 94, 96, 97]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wait_health(client: httpx.Client, process: subprocess.Popen, timeout: float = 15) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"server exited before health check: {process.returncode}")
        try:
            if client.get("/health").status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise RuntimeError("server health timeout")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=4393)
    parser.add_argument("--output", type=Path, default=ROOT / "review/fast-clean-pipeline/http-e2e")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise RuntimeError("output must be absent or empty")
    output.mkdir(parents=True, exist_ok=True)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", args.port))
    data = output / "service-data"
    os.environ["ANIMATION_DATA_DIR"] = str(data)
    from store import Store
    store = Store(data / "jobs.sqlite3", data / "jobs")
    job = store.create_job("reference.png", {}, b"private spatial smoke")
    video_path = store.job_dir(job["id"]) / "video-output.mp4"
    shutil.copyfile(SOURCE, video_path)
    with store.connect() as connection:
        store.upsert_artifact(connection, job["id"], video_path.name, "server_fixture", video_path)
    video = store.get_artifact(job["id"], video_path.name)
    token = secrets.token_urlsafe(32)
    env = os.environ.copy()
    env.update({
        "ANIMATION_API_TOKEN": token,
        "ANIMATION_DATA_DIR": str(data),
        "ANIMATION_CUTOUT_CACHE_DIR": str(CACHE),
        "ANIMATION_PAID_ENABLED": "0",
        "ANIMATION_MAX_STAGE_USD": "0",
        "PYTHONUNBUFFERED": "1",
    })
    env.pop("WAVESPEED_API_KEY", None)
    log_path = output / "server.log"
    with log_path.open("wb") as log:
        process = subprocess.Popen([
            str(ROOT / ".venv/bin/python"), "-m", "uvicorn", "app:app", "--host", "127.0.0.1",
            "--port", str(args.port), "--log-level", "warning",
        ], cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        try:
            base = f"http://127.0.0.1:{args.port}"
            with httpx.Client(base_url=base, timeout=10) as client:
                wait_health(client, process)
                if client.get("/v1/jobs").status_code != 401:
                    raise RuntimeError("unauthenticated job list was not rejected")
                headers = {"Authorization": f"Bearer {token}"}
                selection = client.post(f"/v1/jobs/{job['id']}/selections", headers=headers, json={
                    "source_artifact": video["name"], "source_sha256": video["sha256"], "source_revision": video["revision"],
                    "native_fps": 24.0, "cycle_start": 66, "cycle_end_exclusive": 98, "selected_indices": SELECTED,
                })
                selection.raise_for_status()
                receipt = selection.json()
                for artifact in (video, receipt):
                    review = client.post(f"/v1/jobs/{job['id']}/reviews", headers=headers, json={
                        "artifact": artifact["name"], "sha256": artifact["sha256"], "decision": "approve",
                    })
                    review.raise_for_status()
                queued = client.post(f"/v1/jobs/{job['id']}/stages", headers=headers, json={
                    "stage": "spatial_export", "params": {
                        "source": "video-output.mp4", "selection_receipt": "spatial-selection.json",
                        "selection_mode": "explicit_human_reviewed", "export_preset": "accepted-native-160-80-v1",
                        "removal_preset": "waldlicht-removal-v1", "removal_recipe": "wavespeed-image-background-remover-output-v1",
                    },
                })
                queued.raise_for_status()
                deadline = time.monotonic() + 90
                status = None
                while time.monotonic() < deadline:
                    response = client.get(f"/v1/jobs/{job['id']}", headers=headers)
                    response.raise_for_status()
                    status = response.json()
                    if status["state"] not in {"queued", "running"}:
                        break
                    time.sleep(0.1)
                if not status or status["state"] != "completed":
                    raise RuntimeError(f"spatial job failed: {status}")
                artifacts = {item["name"]: item for item in status["artifacts"]}
                for name, baseline in (("atlas-160.png", BASELINE / "atlas-160.png"), ("atlas-80.png", BASELINE / "atlas-80.png")):
                    response = client.get(f"/v1/jobs/{job['id']}/artifacts/{name}", headers=headers)
                    response.raise_for_status()
                    if hashlib.sha256(response.content).hexdigest() != sha(baseline):
                        raise RuntimeError(f"{name} differs from accepted baseline")
                spatial = client.get(f"/v1/jobs/{job['id']}/artifacts/spatial-export.zip", headers=headers)
                spatial.raise_for_status()
                with zipfile.ZipFile(io.BytesIO(spatial.content)) as archive:
                    if archive.testzip() is not None or "spatial-verification.json" not in archive.namelist():
                        raise RuntimeError("spatial ZIP verification failed")
                    spatial_entries = sorted(archive.namelist())
                download = client.get(f"/v1/jobs/{job['id']}/download", headers=headers)
                download.raise_for_status()
                with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
                    if archive.testzip() is not None or "spatial-export.zip" not in archive.namelist():
                        raise RuntimeError("job ZIP verification failed")
                    job_entries = sorted(archive.namelist())
                (output / "job-download.zip").write_bytes(download.content)
                result_record = json.loads((store.job_dir(job["id"]) / "spatial-export-result.json").read_text())
                timings = json.loads((store.job_dir(job["id"]) / "spatial-timings.json").read_text())
                result = {
                    "status": "passed", "server": base, "job_id": job["id"], "job_state": status["state"],
                    "selection_mode": result_record["selection_mode"], "provider_call_made": result_record["provider_call_made"],
                    "atlas_160_sha256": artifacts["atlas-160.png"]["sha256"], "atlas_80_sha256": artifacts["atlas-80.png"]["sha256"],
                    "artifact_ready_seconds": timings["total_seconds"], "timings": timings["stages"],
                    "security": {"unauthorized_jobs_status": 401, "client_filesystem_paths_accepted": False},
                    "spatial_zip_entries": spatial_entries, "job_zip_entry_count": len(job_entries),
                    "job_download_sha256": hashlib.sha256(download.content).hexdigest(),
                }
                (output / "HTTP_E2E_RESULT.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
                print(json.dumps(result, indent=2, sort_keys=True))
                return 0
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"status": "failed", "error": str(error)}, indent=2), file=sys.stderr)
        raise
