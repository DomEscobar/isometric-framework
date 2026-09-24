import hashlib
import io
import json
import os
import sqlite3
import threading
import time
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image


pytestmark = pytest.mark.unit_fake_pipeline


def png_bytes(size=(8, 8), color=(255, 0, 0, 255)):
    buf = io.BytesIO()
    Image.new("RGBA", size, color).save(buf, format="PNG")
    return buf.getvalue()


class FakePipeline:
    def __init__(self):
        self.calls = []

    def run_stage(self, stage, workdir, params):
        self.calls.append((stage, Path(workdir), dict(params)))
        if stage == "inspect_reference":
            data = (Path(workdir) / params["input"]).read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            (Path(workdir) / "inspect.json").write_text(json.dumps({"sha256": sha}), encoding="utf-8")
            return {
                "status": "needs_review",
                "artifacts": ["reference.png", "inspect.json"],
                "details": {"sha256": sha, "width": 8, "height": 8},
            }
        if stage == "generate_facing":
            return {"status": "needs_attention", "artifacts": [], "details": {"blocked": "paid stage not authorized in fake"}}
        raise ValueError(f"unsupported fake stage {stage}")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ANIMATION_API_TOKEN", "test-token")
    monkeypatch.delenv("ANIMATION_PAID_ENABLED", raising=False)
    monkeypatch.delenv("ANIMATION_MAX_STAGE_USD", raising=False)
    from app import create_app

    fake = FakePipeline()
    app = create_app(
        db_path=tmp_path / "jobs.sqlite3",
        data_dir=tmp_path / "data",
        pipeline_module=fake,
        start_worker=True,
    )
    with TestClient(app) as c:
        c.fake_pipeline = fake
        yield c


def auth_headers(token="test-token"):
    return {"Authorization": f"Bearer {token}"}


def create_job(client):
    response = client.post(
        "/v1/jobs",
        headers=auth_headers(),
        files={"reference": ("reference.png", png_bytes(), "image/png")},
        data={"options": json.dumps({"auto_start": True})},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_health_is_public_but_api_requires_configured_token(tmp_path, monkeypatch):
    monkeypatch.delenv("ANIMATION_API_TOKEN", raising=False)
    from app import create_app

    app = create_app(db_path=tmp_path / "jobs.sqlite3", data_dir=tmp_path / "data", pipeline_module=FakePipeline())
    with TestClient(app) as c:
        assert c.get("/health").status_code == 200
        assert c.get("/v1/jobs").status_code == 503


def test_api_rejects_missing_and_wrong_bearer_token(client):
    assert client.get("/v1/jobs").status_code == 401
    assert client.get("/v1/jobs", headers=auth_headers("wrong")).status_code == 401


def test_upload_queues_inspect_reference_and_downloads_safe_zip(client):
    job = create_job(client)
    job_id = job["id"]

    status = client.get(f"/v1/jobs/{job_id}", headers=auth_headers()).json()
    assert status["state"] == "needs_review"
    assert status["latest_stage"] == "inspect_reference"
    artifacts = {a["name"]: a for a in status["artifacts"]}
    assert "reference.png" in artifacts
    assert "inspect.json" in artifacts
    assert artifacts["reference.png"]["sha256"] == hashlib.sha256(png_bytes()).hexdigest()

    zip_response = client.get(f"/v1/jobs/{job_id}/download", headers=auth_headers())
    assert zip_response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(zip_response.content)) as zf:
        names = zf.namelist()
        assert sorted(names) == ["inspect.json", "reference.png"]
        assert zf.read("reference.png") == png_bytes()


def test_review_requires_exact_artifact_sha_and_blocks_stale_hash(client):
    job = create_job(client)
    job_id = job["id"]
    status = client.get(f"/v1/jobs/{job_id}", headers=auth_headers()).json()
    artifact = next(a for a in status["artifacts"] if a["name"] == "reference.png")

    bad = client.post(
        f"/v1/jobs/{job_id}/reviews",
        headers=auth_headers(),
        json={"artifact": "reference.png", "sha256": "0" * 64, "decision": "approve"},
    )
    assert bad.status_code == 409

    ok = client.post(
        f"/v1/jobs/{job_id}/reviews",
        headers=auth_headers(),
        json={"artifact": "reference.png", "sha256": artifact["sha256"], "decision": "approve"},
    )
    assert ok.status_code == 201
    assert ok.json()["approved"] is True


def test_rejects_path_traversal_artifact_names(client):
    job = create_job(client)
    job_id = job["id"]
    response = client.get(f"/v1/jobs/{job_id}/artifacts/..%2Fjobs.sqlite3", headers=auth_headers())
    assert response.status_code in (400, 404)


def test_stage_submission_sanitizes_paid_flags_and_requires_review(client):
    job = create_job(client)
    job_id = job["id"]
    response = client.post(
        f"/v1/jobs/{job_id}/stages",
        headers=auth_headers(),
        json={"stage": "generate_facing", "params": {"paid": False, "authorized": True, "budget_cents": 0}},
    )
    assert response.status_code == 409
    assert "review" in response.text.lower()


def test_sqlite_queue_persistence_marks_incomplete_running_needs_attention(tmp_path, monkeypatch):
    monkeypatch.setenv("ANIMATION_API_TOKEN", "test-token")
    from store import Store

    db = tmp_path / "jobs.sqlite3"
    data_dir = tmp_path / "data"
    store = Store(db, data_dir)
    job = store.create_job("reference.png", {}, b"abc")
    stage_job = store.enqueue_stage(job["id"], "inspect_reference", {"input": "reference.png"})
    claimed = store.claim_next_stage("worker-a")
    assert claimed["id"] == stage_job["id"]

    reopened = Store(db, data_dir)
    changed = reopened.recover_incomplete("restart")
    assert changed == 1
    assert reopened.get_job(job["id"])["state"] == "needs_attention"


def test_runner_serializes_concurrent_process_once_calls(tmp_path):
    from runner import Runner
    from store import Store

    class BlockingPipeline:
        def __init__(self):
            self.active = 0
            self.maximum_active = 0
            self.lock = threading.Lock()

        def run_stage(self, stage, workdir, params):
            with self.lock:
                self.active += 1
                self.maximum_active = max(self.maximum_active, self.active)
            time.sleep(0.1)
            (Path(workdir) / "inspect.json").write_text("{}", encoding="utf-8")
            with self.lock:
                self.active -= 1
            return {"status": "completed", "artifacts": ["inspect.json"], "details": {}}

    store = Store(tmp_path / "jobs.sqlite3", tmp_path / "data")
    for _ in range(2):
        job = store.create_job("reference.png", {}, b"abc")
        store.enqueue_stage(job["id"], "inspect_reference", {"input": "reference.png"})
    pipeline = BlockingPipeline()
    runner = Runner(store, pipeline_module=pipeline)
    threads = [threading.Thread(target=runner.process_once) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert pipeline.maximum_active == 1


def test_approval_is_bound_to_current_artifact_revision(tmp_path):
    from store import Store

    store = Store(tmp_path / "jobs.sqlite3", tmp_path / "data")
    job = store.create_job("reference.png", {}, b"first")
    artifact = store.get_artifact(job["id"], "reference.png")
    store.add_review(job["id"], "reference.png", artifact["sha256"], "approve")
    assert store.has_approval(job["id"], "reference.png") is True

    path = store.job_dir(job["id"]) / "reference.png"
    path.write_bytes(b"second")
    with store.connect() as connection:
        store.upsert_artifact(connection, job["id"], "reference.png", "upload", path)

    assert store.has_approval(job["id"], "reference.png") is False


def test_background_removal_is_treated_as_paid_stage():
    from runner import PAID_STAGES

    assert "remove_background" in PAID_STAGES


def test_runner_preserves_server_authorized_budget(tmp_path):
    from runner import Runner
    from store import Store

    class RecordingPipeline:
        params = None

        def run_stage(self, stage, workdir, params):
            self.params = params
            return {"status": "needs_attention", "artifacts": [], "details": {}}

    store = Store(tmp_path / "jobs.sqlite3", tmp_path / "data")
    job = store.create_job("reference.png", {}, b"abc")
    store.enqueue_stage(
        job["id"],
        "generate_facing",
        {"input": "reference.png", "budget": {"authorized": True, "max_usd": 0.01}},
    )
    pipeline = RecordingPipeline()
    Runner(store, pipeline_module=pipeline).process_once()

    assert pipeline.params["budget"] == {"authorized": True, "max_usd": 0.01}


def test_upload_rejects_oversized_body_and_dimensions(client):
    from app import MAX_REQUEST_BYTES, MAX_UPLOAD_BYTES

    declared = client.post(
        "/v1/jobs",
        headers={**auth_headers(), "Content-Length": str(MAX_REQUEST_BYTES + 1)},
        content=b"",
    )
    assert declared.status_code == 413

    too_large = client.post(
        "/v1/jobs",
        headers=auth_headers(),
        files={"reference": ("reference.png", b"x" * (MAX_UPLOAD_BYTES + 1), "image/png")},
        data={"options": "{}"},
    )
    assert too_large.status_code == 413

    wide = client.post(
        "/v1/jobs",
        headers=auth_headers(),
        files={"reference": ("reference.png", png_bytes(size=(4097, 1)), "image/png")},
        data={"options": "{}"},
    )
    assert wide.status_code == 413


def test_stage_rejects_client_urls_after_review(client):
    job = create_job(client)
    artifact = next(item for item in job["artifacts"] if item["name"] == "reference.png")
    approved = client.post(
        f"/v1/jobs/{job['id']}/reviews",
        headers=auth_headers(),
        json={"artifact": "reference.png", "sha256": artifact["sha256"], "decision": "approve"},
    )
    assert approved.status_code == 201

    response = client.post(
        f"/v1/jobs/{job['id']}/stages",
        headers=auth_headers(),
        json={"stage": "generate_facing", "params": {"input": "https://example.invalid/a.png"}},
    )
    assert response.status_code == 422


def test_paid_stage_requires_server_policy_even_with_client_authorization(client):
    job = create_job(client)
    artifact = next(item for item in job["artifacts"] if item["name"] == "reference.png")
    client.post(
        f"/v1/jobs/{job['id']}/reviews",
        headers=auth_headers(),
        json={"artifact": "reference.png", "sha256": artifact["sha256"], "decision": "approve"},
    )
    calls_before = len(client.fake_pipeline.calls)
    response = client.post(
        f"/v1/jobs/{job['id']}/stages",
        headers=auth_headers(),
        json={
            "stage": "generate_facing",
            "params": {"input": "reference.png", "prompt": "turn northeast"},
            "authorize_paid": True,
            "budget_cap_usd": 0.01,
        },
    )
    assert response.status_code == 403
    assert len(client.fake_pipeline.calls) == calls_before


@pytest.mark.parametrize("duration", [3, 5, 8, 10])
@pytest.mark.parametrize("resolution", ["480p", "768p"])
def test_api_persists_each_valid_minimax_source_option(tmp_path, monkeypatch, duration, resolution):
    monkeypatch.setenv("ANIMATION_API_TOKEN", "test-token")
    monkeypatch.setenv("ANIMATION_PAID_ENABLED", "1")
    monkeypatch.setenv("ANIMATION_MAX_STAGE_USD", "1")
    from app import create_app

    app = create_app(db_path=tmp_path / "jobs.sqlite3", data_dir=tmp_path / "data")
    store = app.state.store
    job = store.create_job("reference.png", {}, png_bytes())
    facing = store.job_dir(job["id"]) / "facing-output.png"
    facing.write_bytes(png_bytes())
    with store.connect() as connection:
        store.upsert_artifact(connection, job["id"], facing.name, "generate_facing", facing)
    artifact = store.get_artifact(job["id"], "facing-output.png")
    store.add_review(job["id"], artifact["name"], artifact["sha256"], "approve")
    with TestClient(app) as api:
        response = api.post(
            f"/v1/jobs/{job['id']}/stages", headers=auth_headers(),
            json={
                "stage": "generate_video",
                "params": {
                    "input": "facing-output.png", "preset": "minimax-h3-action-3s-480p-v1",
                    "prompt": "one in-place punch", "duration": duration, "resolution": resolution,
                },
                "authorize_paid": True, "budget_cap_usd": 1,
            },
        )
    assert response.status_code == 202, response.text
    assert response.json()["params"]["duration"] == duration
    assert response.json()["params"]["resolution"] == resolution


@pytest.mark.parametrize("invalid", [
    {"duration": 0}, {"duration": 4}, {"duration": "3"},
    {"resolution": "760p"}, {"resolution": "720p"},
])
def test_api_rejects_invalid_minimax_source_options_before_queue(tmp_path, monkeypatch, invalid):
    monkeypatch.setenv("ANIMATION_API_TOKEN", "test-token")
    monkeypatch.setenv("ANIMATION_PAID_ENABLED", "1")
    monkeypatch.setenv("ANIMATION_MAX_STAGE_USD", "1")
    from app import create_app

    app = create_app(db_path=tmp_path / "jobs.sqlite3", data_dir=tmp_path / "data")
    store = app.state.store
    job = store.create_job("reference.png", {}, png_bytes())
    facing = store.job_dir(job["id"]) / "facing-output.png"
    facing.write_bytes(png_bytes())
    with store.connect() as connection:
        store.upsert_artifact(connection, job["id"], facing.name, "generate_facing", facing)
    artifact = store.get_artifact(job["id"], "facing-output.png")
    store.add_review(job["id"], artifact["name"], artifact["sha256"], "approve")
    params = {
        "input": "facing-output.png", "preset": "minimax-h3-action-3s-480p-v1",
        "prompt": "one in-place punch", "duration": 3, "resolution": "480p", **invalid,
    }
    with TestClient(app) as api:
        response = api.post(
            f"/v1/jobs/{job['id']}/stages", headers=auth_headers(),
            json={"stage": "generate_video", "params": params, "authorize_paid": True, "budget_cap_usd": 1},
        )
    assert response.status_code == 422
    with store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM stage_jobs").fetchone()[0] == 0


def test_api_applies_minimax_source_defaults_before_persisting(tmp_path, monkeypatch):
    monkeypatch.setenv("ANIMATION_API_TOKEN", "test-token")
    monkeypatch.setenv("ANIMATION_PAID_ENABLED", "1")
    monkeypatch.setenv("ANIMATION_MAX_STAGE_USD", "1")
    from app import create_app

    app = create_app(db_path=tmp_path / "jobs.sqlite3", data_dir=tmp_path / "data")
    store = app.state.store
    job = store.create_job("reference.png", {}, png_bytes())
    facing = store.job_dir(job["id"]) / "facing-output.png"
    facing.write_bytes(png_bytes())
    with store.connect() as connection:
        store.upsert_artifact(connection, job["id"], facing.name, "generate_facing", facing)
    artifact = store.get_artifact(job["id"], facing.name)
    store.add_review(job["id"], artifact["name"], artifact["sha256"], "approve")
    with TestClient(app) as api:
        response = api.post(
            f"/v1/jobs/{job['id']}/stages", headers=auth_headers(),
            json={
                "stage": "generate_video",
                "params": {"input": facing.name, "preset": "minimax-h3-action-3s-480p-v1", "prompt": "punch"},
                "authorize_paid": True, "budget_cap_usd": 1,
            },
        )
    assert response.status_code == 202, response.text
    assert response.json()["params"]["duration"] == 3
    assert response.json()["params"]["resolution"] == "480p"


def test_cors_is_not_permissive(client):
    response = client.options(
        "/v1/jobs",
        headers={"Origin": "https://evil.invalid", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in response.headers

