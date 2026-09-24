#!/usr/bin/env python3
"""Real browser smoke for the public UI and free inspect flow."""

from __future__ import annotations

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
SCREENSHOTS = ROOT / "artifacts" / "ui-smoke"
REFERENCE = ROOT / "artifacts" / "replay-existing" / "reference.png"
PORT = 4388
TOKEN = "local-ui-smoke-token"


def port_is_free(port: int) -> bool:
    with socket.socket() as sock:
        return sock.connect_ex(("127.0.0.1", port)) != 0


def wait_for_server(url: str, timeout: float = 10) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("UI smoke server did not become ready")


def run_browser(base_url: str) -> dict[str, object]:
    cached = sorted(Path.home().glob(".cache/ms-playwright/chromium-*/chrome-linux/chrome"), reverse=True)
    executable = str(cached[0]) if cached else (shutil.which("chromium") or "/usr/bin/chromium")
    errors: list[str] = []
    os.environ.pop("DBUS_SESSION_BUS_ADDRESS", None)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=executable,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1050})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(f"{base_url}/ui/", wait_until="networkidle")
        page.locator("#demoCanvas[data-frame]").wait_for()

        first = page.evaluate("window.__animationUi.getDemoFrame()")
        page.wait_for_timeout(350)
        later = page.evaluate("window.__animationUi.getDemoFrame()")
        assert first != later, f"demo frame did not progress ({first})"
        page.locator("#demoPlay").click()
        paused = page.evaluate("window.__animationUi.getDemoFrame()")
        page.wait_for_timeout(350)
        paused_later = page.evaluate("window.__animationUi.getDemoFrame()")
        assert paused == paused_later, f"paused demo advanced ({paused} -> {paused_later})"
        assert page.evaluate("window.__animationUi.isDemoPlaying()") is False
        assert page.evaluate("window.__animationUi.apiPrefix") == ""

        page.locator("#token").fill(TOKEN)
        page.locator("#tokenForm button[type=submit]").click()
        expect(page.locator("#connectionState")).to_have_text("Verbunden")
        assert page.evaluate("sessionStorage.getItem('animation-pipeline-token')") == TOKEN
        assert TOKEN not in page.content()

        page.locator("#reference").set_input_files(str(REFERENCE))
        page.locator("#uploadButton").click()
        page.locator("#jobDetail:not(.hidden)").wait_for(timeout=20_000)
        page.locator("#artifactList").get_by_text("reference.png", exact=True).wait_for()
        page.locator(".artifact-button", has_text="reference.png").click()
        page.locator("#artifactPreview img").wait_for()
        assert page.locator("#artifactPreview img").get_attribute("src").startswith("blob:")
        expect(page.locator("#jobStatus")).to_contain_text("Abgeschlossen", timeout=20_000)
        assert "serverseitig gesperrt" in page.locator("#paidPolicy").inner_text()

        SCREENSHOTS.mkdir(parents=True, exist_ok=True)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(9_000)
        desktop = SCREENSHOTS / "desktop.png"
        page.screenshot(path=str(desktop), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(200)
        mobile = SCREENSHOTS / "mobile.png"
        page.screenshot(path=str(mobile), full_page=True)

        assert not errors, errors
        result = {
            "demo_frames": [first, later],
            "paused_frames": [paused, paused_later],
            "job_status": page.locator("#jobStatus").inner_text(),
            "authenticated_blob_preview": True,
            "paid_policy_disabled": True,
            "screenshots": [str(desktop), str(mobile)],
            "browser": browser.version,
            "browser_executable": executable,
        }
        browser.close()
        return result


def main() -> int:
    if not port_is_free(PORT):
        print(f"Refusing to replace listener on 127.0.0.1:{PORT}", file=sys.stderr)
        return 2
    if not REFERENCE.is_file():
        print(f"Missing real replay reference: {REFERENCE}", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="animation-ui-smoke-") as temporary:
        env = dict(os.environ)
        env.update(
            ANIMATION_API_TOKEN=TOKEN,
            ANIMATION_DATA_DIR=temporary,
            ANIMATION_PAID_ENABLED="0",
            ANIMATION_MAX_STAGE_USD="0",
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
            wait_for_server(f"http://127.0.0.1:{PORT}/health")
            result = run_browser(f"http://127.0.0.1:{PORT}")
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
