#!/usr/bin/env python3
"""Bounded real-pipeline HTTP smoke test for the local API."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import httpx

HOST = "127.0.0.1"
PORT = 4386
START_TIMEOUT_SECONDS = 15.0
JOB_TIMEOUT_SECONDS = 15.0
HTTP_TIMEOUT_SECONDS = 5.0


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_port_free(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((HOST, port))
        except OSError as exc:
            raise RuntimeError(f"{HOST}:{port} is already in use; refusing to stop or replace its owner") from exc


def wait_for_health(client: httpx.Client, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + START_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"server exited before health check (exit {process.returncode})")
        try:
            response = client.get("/health")
            if response.status_code == 200 and response.json() == {"status": "ok"}:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise RuntimeError("server did not become healthy before timeout")


def wait_for_job(client: httpx.Client, headers: dict[str, str], job_id: str) -> dict[str, object]:
    deadline = time.monotonic() + JOB_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        response = client.get(f"/v1/jobs/{job_id}", headers=headers)
        response.raise_for_status()
        job = response.json()
        state = job.get("state")
        if state not in {"queued", "running"}:
            return job
        time.sleep(0.1)
    raise RuntimeError("inspect_reference job did not finish before timeout")


def run_smoke(reference: Path, port: int = PORT) -> dict[str, object]:
    reference = reference.resolve(strict=True)
    if not reference.is_file():
        raise RuntimeError("reference must be a regular file")
    reference_bytes = reference.read_bytes()
    if not 1024 <= port <= 65535:
        raise RuntimeError("port must be between 1024 and 65535")
    assert_port_free(port)
    base_url = f"http://{HOST}:{port}"

    project_root = Path(__file__).resolve().parents[1]
    python = project_root / ".venv" / "bin" / "python"
    if not python.is_file():
        raise RuntimeError("missing .venv; install requirements before running smoke")

    with tempfile.TemporaryDirectory(prefix="animation-api-smoke-") as temporary:
        temp_root = Path(temporary)
        token = secrets.token_urlsafe(32)
        environment = os.environ.copy()
        environment.update(
            {
                "ANIMATION_API_TOKEN": token,
                "ANIMATION_DATA_DIR": str(temp_root / "service-data"),
                "ANIMATION_PAID_ENABLED": "0",
                "ANIMATION_MAX_STAGE_USD": "0",
                "PYTHONUNBUFFERED": "1",
            }
        )
        environment.pop("WAVESPEED_API_KEY", None)
        log_path = temp_root / "server.log"
        with log_path.open("wb") as log:
            process = subprocess.Popen(
                [str(python), "-m", "uvicorn", "app:app", "--host", HOST, "--port", str(port), "--log-level", "warning"],
                cwd=project_root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                with httpx.Client(base_url=base_url, timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=False) as client:
                    wait_for_health(client, process)
                    unauthorized = client.get("/v1/jobs")
                    if unauthorized.status_code != 401:
                        raise RuntimeError(f"unauthorized API request returned {unauthorized.status_code}, expected 401")

                    upload = client.post(
                        "/v1/jobs",
                        headers={"Authorization": f"Bearer {token}"},
                        files={"reference": ("reference.png", reference_bytes, "image/png")},
                        data={"options": json.dumps({"auto_start": True})},
                    )
                    upload.raise_for_status()
                    job_id = upload.json()["id"]
                    headers = {"Authorization": f"Bearer {token}"}
                    job = wait_for_job(client, headers, job_id)
                    if job.get("state") != "completed" or job.get("latest_stage") != "inspect_reference":
                        raise RuntimeError(f"real inspect_reference did not complete: {job.get('state')} {job.get('message')}")

                    artifacts = {item["name"]: item for item in job["artifacts"]}
                    expected_names = {"reference.png", "inspect-reference.json"}
                    if set(artifacts) != expected_names:
                        raise RuntimeError(f"unexpected inspect artifacts: {sorted(artifacts)}")
                    if artifacts["reference.png"]["sha256"] != sha256(reference_bytes):
                        raise RuntimeError("uploaded reference hash changed")

                    inspect_response = client.get(f"/v1/jobs/{job_id}/artifacts/inspect-reference.json", headers=headers)
                    inspect_response.raise_for_status()
                    inspect_record = inspect_response.json()
                    if inspect_record.get("stage") != "inspect_reference":
                        raise RuntimeError("downloaded inspect artifact was not produced by inspect_reference")
                    if inspect_record.get("result", {}).get("details", {}).get("sha256") != sha256(reference_bytes):
                        raise RuntimeError("inspect artifact does not bind the uploaded reference hash")
                    inspect_hash = sha256(inspect_response.content)
                    inspect_artifact = artifacts["inspect-reference.json"]
                    if inspect_hash != inspect_artifact["sha256"]:
                        raise RuntimeError("inspect artifact download hash differs from recorded hash")

                    review = client.post(
                        f"/v1/jobs/{job_id}/reviews",
                        headers=headers,
                        json={"artifact": "inspect-reference.json", "sha256": inspect_hash, "decision": "approve"},
                    )
                    review.raise_for_status()
                    receipt = review.json()
                    if not receipt.get("approved") or receipt.get("sha256") != inspect_hash or receipt.get("revision") != inspect_artifact["revision"]:
                        raise RuntimeError("review receipt does not bind the exact artifact hash and revision")

                    traversal = client.get(f"/v1/jobs/{job_id}/artifacts/..%2Fjobs.sqlite3", headers=headers)
                    if traversal.status_code not in {400, 404}:
                        raise RuntimeError(f"artifact traversal returned unsafe status {traversal.status_code}")

                    download = client.get(f"/v1/jobs/{job_id}/download", headers=headers)
                    download.raise_for_status()
                    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
                        names = archive.namelist()
                        if set(names) != expected_names or any(Path(name).name != name for name in names):
                            raise RuntimeError(f"ZIP contains unexpected or unsafe names: {names}")
                        for name in names:
                            if sha256(archive.read(name)) != artifacts[name]["sha256"]:
                                raise RuntimeError(f"ZIP hash mismatch for {name}")

                    return {
                        "status": "passed",
                        "server": base_url,
                        "pipeline": "real pipeline.run_stage (no injected fake)",
                        "job_id": job_id,
                        "job_state": job["state"],
                        "latest_stage": job["latest_stage"],
                        "reference": {"source": str(reference), "bytes": len(reference_bytes), "sha256": sha256(reference_bytes)},
                        "review": {"artifact": receipt["artifact"], "sha256": receipt["sha256"], "revision": receipt["revision"]},
                        "zip": {"bytes": len(download.content), "sha256": sha256(download.content), "entries": sorted(names)},
                        "security": {"unauthorized_status": unauthorized.status_code, "traversal_status": traversal.status_code},
                    }
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                if process.returncode not in {0, -15}:
                    log.flush()
                    server_log = log_path.read_text(encoding="utf-8", errors="replace")[-4000:]
                    if sys.exc_info()[0] is None:
                        raise RuntimeError(f"server exited unexpectedly ({process.returncode}):\n{server_log}")


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference",
        type=Path,
        default=project_root / "artifacts" / "replay-existing" / "reference.png",
        help="existing accepted PNG reference (default: replay-existing/reference.png)",
    )
    parser.add_argument("--port", type=int, default=PORT, help="isolated localhost port (default: 4386)")
    args = parser.parse_args()
    try:
        result = run_smoke(args.reference, args.port)
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
