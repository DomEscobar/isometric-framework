#!/usr/bin/env python3
"""Real HTTP smoke for automatic local review, with paid reviewer disabled."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
HOST = "127.0.0.1"
PORT = 4389
BASE = f"http://{HOST}:{PORT}"
REJECTED = ROOT / "artifacts/review-candidates/gemini-rejected-3s/source.mp4"
WAN = ROOT / "artifacts/review-candidates/wan-existing-accepted-window/source.mp4"
OUTPUT = ROOT / "artifacts/automatic-review-http-smoke.json"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def port_free() -> None:
    with socket.socket() as probe:
        try:
            probe.bind((HOST, PORT))
        except OSError as exc:
            raise RuntimeError(f"{HOST}:{PORT} is in use; refusing to replace it") from exc


def fixture_job(store, source: Path) -> tuple[str, dict]:
    job = store.create_job("reference.png", {"smoke_fixture": True}, b"server-side-smoke-placeholder")
    target = store.job_dir(job["id"]) / "video-output.mp4"
    shutil.copyfile(source, target)
    with store.connect() as connection:
        store.upsert_artifact(connection, job["id"], target.name, "server_side_smoke_fixture", target)
    return job["id"], store.get_artifact(job["id"], target.name)


def start_server(environment: dict[str, str], log) -> subprocess.Popen[bytes]:
    process = subprocess.Popen(
        [str(ROOT / ".venv/bin/python"), "-m", "uvicorn", "app:app", "--host", HOST, "--port", str(PORT), "--log-level", "warning"],
        cwd=ROOT, env=environment, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
    )
    with httpx.Client(base_url=BASE, timeout=5) as client:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"isolated server exited with {process.returncode}")
            try:
                if client.get("/health").status_code == 200:
                    return process
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
    raise RuntimeError("isolated server did not become healthy")


def stop_server(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def wait_job(client: httpx.Client, headers: dict[str, str], job_id: str) -> dict:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        response = client.get(f"/v1/jobs/{job_id}", headers=headers)
        response.raise_for_status()
        job = response.json()
        if job["state"] not in {"queued", "running"}:
            return job
        time.sleep(0.2)
    raise RuntimeError(f"automatic review timed out for {job_id}")


def submit(client: httpx.Client, headers: dict[str, str], job_id: str, artifact: dict, authorize: bool) -> None:
    response = client.post(
        f"/v1/jobs/{job_id}/automatic-review", headers=headers,
        json={
            "artifact": artifact["name"], "sha256": artifact["sha256"], "revision": artifact["revision"],
            "authorize_paid_review": authorize, "budget_cap_usd": 0.05 if authorize else None,
        },
    )
    response.raise_for_status()


def run() -> dict:
    port_free()
    from store import Store

    with tempfile.TemporaryDirectory(prefix="automatic-review-http-") as temporary:
        temporary_path = Path(temporary)
        data_root = temporary_path / "service"
        store = Store(data_root / "jobs.sqlite3", data_root / "jobs")
        rejected_id, rejected_artifact = fixture_job(store, REJECTED)
        wan_id, wan_artifact = fixture_job(store, WAN)
        token = secrets.token_urlsafe(32)
        environment = os.environ.copy()
        environment.update({
            "ANIMATION_API_TOKEN": token,
            "ANIMATION_DATA_DIR": str(data_root),
            "ANIMATION_REVIEW_ENABLED": "0",
            "ANIMATION_PAID_ENABLED": "0",
            "ANIMATION_MAX_STAGE_USD": "0",
            "PYTHONUNBUFFERED": "1",
        })
        environment.pop("OPENROUTER_API_KEY", None)
        headers = {"Authorization": f"Bearer {token}"}
        log_path = temporary_path / "server.log"
        with log_path.open("wb") as log:
            process = start_server(environment, log)
            try:
                with httpx.Client(base_url=BASE, timeout=10) as client:
                    unauthorized = client.get(f"/v1/jobs/{rejected_id}")
                    if unauthorized.status_code != 401:
                        raise RuntimeError("automatic review job leaked without authentication")
                    submit(client, headers, rejected_id, rejected_artifact, True)
                    rejected_job = wait_job(client, headers, rejected_id)
                    submit(client, headers, wan_id, wan_artifact, False)
                    wan_job = wait_job(client, headers, wan_id)
                    rejected_review = rejected_job["automatic_reviews"][0]
                    wan_review = wan_job["automatic_reviews"][0]
                    if rejected_review["status"] != "rejected" or rejected_review["paid_transport_called"]:
                        raise RuntimeError("hard rejection did not stop before paid transport")
                    if wan_review["status"] != "needs_attention" or wan_review["candidate_count"] < 1:
                        raise RuntimeError("safe candidates did not persist as disabled-review needs_attention")
                    if wan_review["paid_transport_called"]:
                        raise RuntimeError("disabled reviewer was called")
                    downloads = {}
                    for job_id, job in ((rejected_id, rejected_job), (wan_id, wan_job)):
                        for name in ("video-output.mp4", "automatic-review-analysis.json", "automatic-review-result.json"):
                            response = client.get(f"/v1/jobs/{job_id}/artifacts/{name}", headers=headers)
                            response.raise_for_status()
                            record = next(item for item in job["artifacts"] if item["name"] == name)
                            if digest(response.content) != record["sha256"]:
                                raise RuntimeError(f"download hash mismatch: {job_id}/{name}")
                            downloads[f"{job_id}/{name}"] = {"bytes": len(response.content), "sha256": digest(response.content)}
                    traversal = client.get(f"/v1/jobs/{wan_id}/artifacts/..%2Fjobs.sqlite3", headers=headers)
                    if traversal.status_code not in {400, 404}:
                        raise RuntimeError("path traversal guard failed")
            finally:
                stop_server(process)
            process = start_server(environment, log)
            try:
                with httpx.Client(base_url=BASE, timeout=10) as client:
                    persisted_rejected = client.get(f"/v1/jobs/{rejected_id}", headers=headers).json()
                    persisted_wan = client.get(f"/v1/jobs/{wan_id}", headers=headers).json()
                    if persisted_rejected["automatic_reviews"][0]["source_revision"] != rejected_artifact["revision"]:
                        raise RuntimeError("rejected review revision did not survive restart")
                    if persisted_wan["automatic_reviews"][0]["source_sha256"] != wan_artifact["sha256"]:
                        raise RuntimeError("candidate review hash did not survive restart")
            finally:
                stop_server(process)
        return {
            "status": "passed",
            "http": {"base_url": BASE, "unauthorized_status": unauthorized.status_code, "traversal_status": traversal.status_code},
            "paid_calls": 0,
            "live_vlm_claimed": False,
            "fixtures": {
                "rejected": {"source": str(REJECTED), "job_id": rejected_id, "source_sha256": rejected_artifact["sha256"], "review": rejected_review},
                "wan": {"source": str(WAN), "job_id": wan_id, "source_sha256": wan_artifact["sha256"], "review": wan_review},
            },
            "restart_persistence_verified": True,
            "authenticated_downloads": downloads,
        }


def main() -> int:
    try:
        result = run()
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": "passed", "report": str(OUTPUT), "paid_calls": 0}, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
