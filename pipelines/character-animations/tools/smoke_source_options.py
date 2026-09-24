#!/usr/bin/env python3
"""Real Chromium smoke for free source-option UI request capture."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "review" / "source-options"
REFERENCE = ROOT / "artifacts" / "replay-existing" / "reference.png"
PORT = 4394
TOKEN = "local-source-options-smoke-token"


def port_is_free() -> bool:
    with socket.socket() as sock:
        return sock.connect_ex(("127.0.0.1", PORT)) != 0


def wait_for_server() -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{PORT}/health", timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("source-options smoke server did not become ready")


def prepare_job(data_dir: Path) -> str:
    sys.path.insert(0, str(ROOT))
    from store import Store

    store = Store(data_dir / "jobs.sqlite3", data_dir / "jobs")
    content = REFERENCE.read_bytes()
    job = store.create_job("reference.png", {}, content)
    facing = store.job_dir(job["id"]) / "facing-output.png"
    facing.write_bytes(content)
    with store.connect() as connection:
        store.upsert_artifact(connection, job["id"], facing.name, "generate_facing", facing)
    artifact = store.get_artifact(job["id"], facing.name)
    store.add_review(job["id"], artifact["name"], artifact["sha256"], "approve")
    return job["id"]


def run_browser(job_id: str) -> dict[str, object]:
    cached = sorted(Path.home().glob(".cache/ms-playwright/chromium-*/chrome-linux/chrome"), reverse=True)
    executable = str(cached[0]) if cached else (shutil.which("chromium") or "/usr/bin/chromium")
    captured: list[dict[str, object]] = []
    errors: list[str] = []
    os.environ.pop("DBUS_SESSION_BUS_ADDRESS", None)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=executable,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.on("pageerror", lambda error: errors.append(str(error)))

        def capture_stage(route) -> None:
            if route.request.method == "POST":
                body = route.request.post_data_json
                captured.append(body)
                route.fulfill(
                    status=202,
                    content_type="application/json",
                    body=json.dumps({"id": "captured-no-provider-call", "job_id": job_id, **body, "state": "queued"}),
                )
            else:
                route.continue_()

        page.route(f"**/v1/jobs/{job_id}/stages", capture_stage)
        page.goto(f"http://127.0.0.1:{PORT}/ui/", wait_until="networkidle")
        page.locator("#token").fill(TOKEN)
        page.locator("#tokenForm button[type=submit]").click()
        expect(page.locator("#connectionState")).to_have_text("Verbunden")
        page.locator(".job-card").click()
        page.locator("#stageName").select_option("generate_video")

        expect(page.locator("#sourceVideoFields")).to_be_visible()
        expect(page.locator("#sourceDuration")).to_have_value("3")
        expect(page.locator("#sourceResolution")).to_have_value("480p")
        default_params = json.loads(page.locator("#stageParams").input_value())
        assert default_params["duration"] == 3
        assert default_params["resolution"] == "480p"

        page.locator("#sourceDuration").select_option("10")
        page.locator("#sourceResolution").select_option("768p")
        page.locator("#authorizePaid").check()
        page.locator("#budgetCap").fill("0.4")
        page.locator("#submitStage").click()
        expect(page.locator("#notice")).to_contain_text("Stufe wurde eingereiht")
        assert len(captured) == 1
        submitted = captured[0]
        assert submitted["params"]["duration"] == 10
        assert submitted["params"]["resolution"] == "768p"
        assert submitted["params"]["preset"] == "minimax-h3-action-3s-480p-v1"
        assert submitted["budget_cap_usd"] == 0.4
        expect(page.locator("#sourceDuration")).to_have_value("10")
        expect(page.locator("#sourceResolution")).to_have_value("768p")

        OUT.mkdir(parents=True, exist_ok=True)
        screenshot = OUT / "source-options-10s-768p.png"
        page.locator("#jobDetail").screenshot(path=str(screenshot))
        assert not errors, errors
        browser_version = browser.version
        browser.close()

    return {
        "status": "PASS",
        "mode": "real Chromium UI with intercepted stage POST; no provider generation",
        "defaults": {"duration": 3, "resolution": "480p"},
        "captured_request": submitted,
        "provider_calls": 0,
        "screenshot": str(screenshot),
        "screenshot_sha256": hashlib.sha256(screenshot.read_bytes()).hexdigest(),
        "browser": browser_version,
    }


def main() -> int:
    if not port_is_free():
        print(f"Refusing to replace listener on 127.0.0.1:{PORT}", file=sys.stderr)
        return 2
    if not REFERENCE.is_file():
        print(f"Missing replay reference: {REFERENCE}", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="source-options-smoke-") as temporary:
        data_dir = Path(temporary)
        job_id = prepare_job(data_dir)
        env = dict(os.environ)
        env.update(
            ANIMATION_API_TOKEN=TOKEN,
            ANIMATION_DATA_DIR=str(data_dir),
            ANIMATION_PAID_ENABLED="1",
            ANIMATION_MAX_STAGE_USD="1",
        )
        process = subprocess.Popen(
            [str(ROOT / ".venv" / "bin" / "python"), "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(PORT)],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            wait_for_server()
            result = run_browser(job_id)
            OUT.mkdir(parents=True, exist_ok=True)
            report = OUT / "browser-smoke.json"
            report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
