import hashlib
import os
from pathlib import Path

from fastapi.testclient import TestClient


REPLAY = Path(__file__).parents[1] / "artifacts" / "replay-existing"


def make_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ANIMATION_API_TOKEN", "test-token")
    monkeypatch.setenv("ANIMATION_PAID_ENABLED", "0")
    monkeypatch.setenv("ANIMATION_MAX_STAGE_USD", "0.025")
    from app import create_app

    app = create_app(db_path=tmp_path / "jobs.sqlite3", data_dir=tmp_path / "jobs")
    return TestClient(app)


def test_ui_shell_and_static_assets_are_public_and_csp_safe(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        page = client.get("/ui/")
        assert page.status_code == 200
        assert 'lang="de"' in page.text
        assert "Animation Werkstatt" in page.text
        assert "test-token" not in page.text
        assert "Content-Security-Policy" in page.headers
        assert "'unsafe-inline'" not in page.headers["Content-Security-Policy"]
        assert client.get("/ui/app.css").status_code == 200
        script = client.get("/ui/app.js")
        assert script.status_code == 200
        assert "sessionStorage" in script.text
        assert "location.pathname" in script.text
        assert "fetch('/v1" not in script.text


def test_public_agent_guide_prompt_and_openapi_are_prefix_accurate(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        page = client.get("/ui/")
        prompt = client.get("/agent-prompt.txt")
        guide = client.get("/agent-guide.md")
        spec = client.get("/openapi.json")
        docs = client.get("/docs")

    assert page.status_code == 200
    assert 'id="agentPrompt"' in page.text
    assert 'id="copyAgentPrompt"' in page.text
    assert "Für Coding-Agents" in page.text
    assert 'href="https://isoani.huecki.com/animation/agent-guide.md"' in page.text
    assert 'href="https://isoani.huecki.com/animation/openapi.json"' in page.text
    assert "test-token" not in page.text

    assert prompt.status_code == 200
    assert prompt.headers["content-type"].startswith("text/plain")
    assert "https://isoani.huecki.com/animation" in prompt.text
    assert "https://isoani.huecki.com/animation/agent-guide.md" in prompt.text
    assert "https://isoani.huecki.com/animation/openapi.json" in prompt.text
    assert "ANIMATION_API_TOKEN" in prompt.text
    assert "test-token" not in prompt.text

    assert guide.status_code == 200
    assert guide.headers["content-type"].startswith("text/markdown")
    assert "ANIMATION_API_TOKEN" in guide.text
    assert "needs_review" in guide.text and "needs_attention" in guide.text
    assert "test-token" not in guide.text

    assert docs.status_code == 200
    assert "./openapi.json" in docs.text
    assert spec.status_code == 200
    schema = spec.json()
    assert schema["servers"] == [{"url": "https://isoani.huecki.com/animation", "description": "Öffentlicher Produktionsendpunkt"}]
    bearer = schema["components"]["securitySchemes"]["bearerAuth"]
    assert bearer == {"type": "http", "scheme": "bearer", "bearerFormat": "API token"}
    assert schema["paths"]["/health"]["get"].get("security") == []
    assert schema["paths"]["/v1/capabilities"]["get"]["security"] == [{"bearerAuth": []}]
    assert schema["paths"]["/v1/jobs"]["post"]["security"] == [{"bearerAuth": []}]


def test_agent_docs_are_allowlisted_not_arbitrary_files(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        assert client.get("/agent-guide.md").status_code == 200
        assert client.get("/agent-prompt.txt").status_code == 200
        assert client.get("/docs/PIPELINE.md").status_code == 404
        assert client.get("/agent/..%2Fapp.py").status_code in (400, 404)


def test_demo_allowlist_serves_only_real_atlas_and_manifest(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        for name in ("atlas.png", "atlas-manifest.json"):
            response = client.get(f"/ui/demo/{name}")
            assert response.status_code == 200
            expected = (REPLAY / name).read_bytes()
            assert hashlib.sha256(response.content).digest() == hashlib.sha256(expected).digest()
        manifest = client.get("/ui/demo/atlas-manifest.json").json()
        assert manifest["schema"] == "animation-pipeline-atlas-v1"
        assert manifest["clip"]["fps"] == 12.0
        assert len(manifest["frames"]) == 16
        assert client.get("/ui/demo/reference.png").status_code == 404
        assert client.get("/ui/demo/replay-report.json").status_code == 404
        assert client.get("/ui/demo/..%2F..%2Fapp.py").status_code in (400, 404)


def test_capabilities_are_authenticated_and_report_server_paid_policy(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        assert client.get("/v1/capabilities").status_code == 401
        response = client.get(
            "/v1/capabilities", headers={"Authorization": "Bearer test-token"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["paid_policy"] == {"enabled": False, "max_stage_usd": 0.025}
        assert body["stages"]["inspect_reference"]["paid"] is False
        assert body["stages"]["generate_facing"]["paid"] is True
        presets = {preset["name"]: preset for preset in body["presets"]}
        assert presets["waldlicht-facing-v1"]["capability"] == "image_edit"
        assert presets["waldlicht-facing-v1"]["quote"]["quoted_usd"] == 0.011
        gemini = presets["gemini-omni-video-3s-v1"]
        assert gemini["model"] == "google/gemini-omni-1.1-flash/image-to-video"
        assert gemini["defaults"] == {"duration": 3, "resolution": "360p", "aspect_ratio": "16:9"}
        assert gemini["quote"]["quoted_usd"] == 0.09
        minimax = presets["minimax-h3-action-3s-480p-v1"]
        assert minimax["defaults"]["duration"] == 3
        assert minimax["defaults"]["resolution"] == "480p"
        assert minimax["parameter_options"] == {
            "duration": [3, 5, 8, 10], "resolution": ["480p", "768p"]
        }


def test_ui_builds_video_params_from_selected_preset_defaults(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        script = client.get("/ui/app.js").text
        assert "videoParamsForPreset" in script
        assert "preset.defaults" in script
        assert "negative_prompt" not in script[script.index("function videoParamsForPreset"):script.index("function renderStageForm")]


def test_ui_exposes_distinct_minimax_source_video_options(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        page = client.get("/ui/").text
        script = client.get("/ui/app.js").text

    assert 'id="sourceDuration"' in page
    assert 'id="sourceResolution"' in page
    assert "Videodauer" in page
    assert "Videoauflösung" in page
    assert '<option value="3" selected>3 Sekunden</option>' in page
    assert '<option value="10">10 Sekunden</option>' in page
    assert '<option value="480p" selected>480p</option>' in page
    assert '<option value="768p">768p</option>' in page
    assert "Quellvideo" in page and "80/160" in page
    assert "sourceDuration" in script and "sourceResolution" in script


def test_ui_exposes_distinct_bounded_sprite_resolution_selector(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        page = client.get("/ui/").text
        script = client.get("/ui/app.js").text
    assert "Sprite-Auflösung" in page
    assert 'id="exportResolution"' in page
    assert '<option value="160" selected>160 × 160 px</option>' in page
    assert '<option value="80">80 × 80 px</option>' in page
    assert "exportResolution" in script


def test_ui_exposes_truthful_automatic_review_trigger_and_candidates(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        page = client.get("/ui/").text
        script = client.get("/ui/app.js").text

    assert 'id="automaticReviewBox"' in page
    assert 'id="startAutomaticReview"' in page
    assert "google/gemini-3.8-flash" in script
    assert "/automatic-review" in script
    assert "automatic_reviews" in script
    assert "selected_candidate" in script
    assert "Lokale Analyse" in script
    assert "kein Qualitätsnachweis" in page
    assert 'id="automaticReviewFramePolicy"' in page
    assert '<option value="8" selected>' in page
    assert "frame_policy: $('#automaticReviewFramePolicy').value" in script
