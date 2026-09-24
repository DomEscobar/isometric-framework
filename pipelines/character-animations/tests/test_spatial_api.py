from __future__ import annotations

import hashlib
import io
import json
import shutil
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "artifacts/minimax-ne-source-01/provider-original.mp4"
BASELINE = ROOT / "artifacts/minimax-ne-export-final"
CACHE = ROOT / "review/fast-clean-pipeline/cutout-cache"
AUTH = {"Authorization": "Bearer test-token"}
SELECTED = [66, 67, 69, 70, 71, 73, 74, 75, 77, 78, 79, 81, 82, 84, 85, 86, 88, 89, 90, 92, 93, 94, 96, 97]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _seed_video(app) -> tuple[str, dict]:
    store = app.state.store
    job = store.create_job("reference.png", {}, b"not-used")
    target = store.job_dir(job["id"]) / "video-output.mp4"
    shutil.copyfile(SOURCE, target)
    with store.connect() as connection:
        store.upsert_artifact(connection, job["id"], target.name, "fixture", target)
    return job["id"], store.get_artifact(job["id"], target.name)


def _approve(client: TestClient, job_id: str, artifact: dict) -> None:
    response = client.post(
        f"/v1/jobs/{job_id}/reviews", headers=AUTH,
        json={"artifact": artifact["name"], "sha256": artifact["sha256"], "decision": "approve"},
    )
    assert response.status_code == 201, response.text


def test_authenticated_http_spatial_export_uses_reviewed_selection_and_downloadable_zip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ANIMATION_API_TOKEN", "test-token")
    monkeypatch.setenv("ANIMATION_CUTOUT_CACHE_DIR", str(CACHE))
    from app import create_app

    app = create_app(db_path=tmp_path / "jobs.sqlite3", data_dir=tmp_path / "jobs", start_worker=False)
    job_id, video = _seed_video(app)
    with TestClient(app) as client:
        denied = client.post(f"/v1/jobs/{job_id}/selections", json={})
        assert denied.status_code == 401
        selection = client.post(
            f"/v1/jobs/{job_id}/selections", headers=AUTH,
            json={
                "source_artifact": "video-output.mp4",
                "source_sha256": video["sha256"],
                "source_revision": video["revision"],
                "native_fps": 24.0,
                "cycle_start": 66,
                "cycle_end_exclusive": 98,
                "selected_indices": SELECTED,
            },
        )
        assert selection.status_code == 201, selection.text
        receipt = selection.json()
        _approve(client, job_id, video)
        _approve(client, job_id, receipt)
        queued = client.post(
            f"/v1/jobs/{job_id}/stages", headers=AUTH,
            json={
                "stage": "spatial_export",
                "params": {
                    "source": "video-output.mp4",
                    "selection_receipt": "spatial-selection.json",
                    "selection_mode": "explicit_human_reviewed",
                    "export_preset": "accepted-native-160-80-v1",
                    "removal_preset": "waldlicht-removal-v1",
                    "removal_recipe": "wavespeed-image-background-remover-output-v1"
                },
            },
        )
        assert queued.status_code == 202, queued.text
        assert app.state.runner.process_once() is True
        status = client.get(f"/v1/jobs/{job_id}", headers=AUTH).json()
        assert status["state"] == "completed", status.get("message")
        names = {item["name"] for item in status["artifacts"]}
        assert {"atlas-160.png", "atlas-80.png", "spatial-export.zip", "spatial-timings.json", "spatial-export-result.json"} <= names
        assert _sha(app.state.store.job_dir(job_id) / "atlas-160.png") == _sha(BASELINE / "atlas-160.png")
        assert _sha(app.state.store.job_dir(job_id) / "atlas-80.png") == _sha(BASELINE / "atlas-80.png")
        result = json.loads((app.state.store.job_dir(job_id) / "spatial-export-result.json").read_text())
        assert result["selection_mode"] == "explicit_human_reviewed"
        assert result["provider_call_made"] is False
        download = client.get(f"/v1/jobs/{job_id}/download", headers=AUTH)
        assert download.status_code == 200
        with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
            assert "spatial-export.zip" in archive.namelist()
            with zipfile.ZipFile(io.BytesIO(archive.read("spatial-export.zip"))) as spatial:
                assert {"atlas-160.png", "atlas-80.png", "spatial-verification.json"} <= set(spatial.namelist())


def test_spatial_export_rejects_automatic_label_for_explicit_receipt(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ANIMATION_CUTOUT_CACHE_DIR", str(CACHE))
    workdir = tmp_path
    shutil.copyfile(SOURCE, workdir / "video-output.mp4")
    (workdir / "spatial-selection.json").write_text(json.dumps({
        "schema": "animation-spatial-selection-v1",
        "mode": "explicit_human_reviewed",
        "source": {"file": "video-output.mp4", "sha256": _sha(SOURCE), "revision": 1},
        "native_fps": 24.0,
        "cycle_start": 66,
        "cycle_end_exclusive": 98,
        "selected_indices": SELECTED,
    }))
    import pipeline
    try:
        pipeline.run_stage("spatial_export", workdir, {
            "source": "video-output.mp4",
            "selection_receipt": "spatial-selection.json",
            "selection_mode": "automatic_model_validated",
            "export_preset": "accepted-native-160-80-v1",
            "removal_preset": "waldlicht-removal-v1",
            "removal_recipe": "wavespeed-image-background-remover-output-v1",
        })
    except ValueError as error:
        assert "selection provenance" in str(error)
    else:
        raise AssertionError("explicit receipt was accepted as automatic")


def _mocked_validated_automatic_export(tmp_path, monkeypatch):
    monkeypatch.setenv("ANIMATION_CUTOUT_CACHE_DIR", str(CACHE))
    shutil.copyfile(SOURCE, tmp_path / "video-output.mp4")
    frames = []
    for order, source_index in enumerate(SELECTED):
        name = f"selected-frame-{order:04d}.png"
        shutil.copyfile(BASELINE / "selected-originals" / f"original-frame-{order:04d}.png", tmp_path / name)
        frames.append({"order": order, "source_index": source_index, "file": name})
    (tmp_path / "automatic-review-analysis.json").write_text(json.dumps({
        "source": {"file": "video-output.mp4", "sha256": _sha(SOURCE), "native_fps": 24.0},
        "hard_failures": [],
    }))
    (tmp_path / "automatic-review-result.json").write_text(json.dumps({
        "status": "approved", "approved": True, "provider_decision": "approve",
        "model": "google/gemini-3.8-flash", "source_sha256": _sha(SOURCE),
        "selected_candidate": {
            "id": "mocked-bound-candidate", "start_source_frame_index": 66,
            "end_source_frame_index": 98, "sampling_evidence": {"maximum_native_gap": 3},
        },
    }))
    reviewer_sha = _sha(tmp_path / "automatic-review-result.json")
    from runner import frame_policy
    policy = frame_policy("native")
    (tmp_path / "selection-density-receipt.json").write_text(json.dumps({
        "schema": "animation-selection-density-v1",
        "policy": policy,
        "frame_policy_option": "native",
        "source": {"file": "video-output.mp4", "sha256": _sha(SOURCE), "revision": 1},
        "reviewer_receipt": {"file": "automatic-review-result.json", "sha256": reviewer_sha},
        "sampling": {"indices": SELECTED},
    }))
    density_sha = _sha(tmp_path / "selection-density-receipt.json")
    (tmp_path / "extract-frames.json").write_text(json.dumps({
        "source": {"file": "video-output.mp4", "sha256": _sha(SOURCE)},
        "automatic_selection": True,
        "automatic_review_id": "mocked-review-id",
        "density_selection": {
            "receipt": "selection-density-receipt.json",
            "receipt_sha256": density_sha,
            "policy_sha256": policy["sha256"],
        },
        "frames": frames,
    }))
    import pipeline
    result = pipeline.run_stage("spatial_export", tmp_path, {
        "source": "video-output.mp4",
        "selection_receipt": "automatic-review-result.json",
        "selection_mode": "automatic_model_validated",
        "export_preset": "accepted-native-160-80-v1",
        "removal_preset": "waldlicht-removal-v1",
        "removal_recipe": "wavespeed-image-background-remover-output-v1",
    })

    return result


def test_mocked_validated_automatic_receipt_connects_to_generic_exporter(tmp_path, monkeypatch) -> None:
    result = _mocked_validated_automatic_export(tmp_path, monkeypatch)
    assert result["status"] == "completed"
    assert result["details"]["selection_mode"] == "automatic_model_validated"
    assert result["details"]["selected_indices"] == SELECTED
    assert _sha(tmp_path / "atlas-160.png") == _sha(BASELINE / "atlas-160.png")


def test_stale_frame_policy_hash_is_rejected(tmp_path, monkeypatch) -> None:
    _mocked_validated_automatic_export(tmp_path, monkeypatch)
    extraction_path = tmp_path / "extract-frames.json"
    extraction = json.loads(extraction_path.read_text())
    extraction["density_selection"]["policy_sha256"] = "0" * 64
    extraction_path.write_text(json.dumps(extraction))

    import pipeline
    try:
        pipeline.run_stage("spatial_export", tmp_path, {
            "source": "video-output.mp4",
            "selection_receipt": "automatic-review-result.json",
            "selection_mode": "automatic_model_validated",
            "export_preset": "accepted-native-160-80-v1",
            "removal_preset": "waldlicht-removal-v1",
            "removal_recipe": "wavespeed-image-background-remover-output-v1",
        })
    except ValueError as error:
        assert "frame policy provenance is stale" in str(error)
    else:
        raise AssertionError("stale frame policy hash was accepted")
