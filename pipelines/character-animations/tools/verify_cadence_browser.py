#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "review/cadence-uninterrupted/phase1-density-proof"
URL = "http://127.0.0.1:4410/preview.html"


def main() -> int:
    cached = sorted(Path.home().glob(".cache/ms-playwright/chromium-*/chrome-linux/chrome"), reverse=True)
    executable = str(cached[0]) if cached else (shutil.which("chromium") or "/usr/bin/chromium")
    console_errors: list[str] = []
    page_errors: list[str] = []
    os.environ.pop("DBUS_SESSION_BUS_ADDRESS", None)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=executable,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        page = browser.new_page(viewport={"width": 640, "height": 480}, device_scale_factor=1)
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto(URL, wait_until="networkidle")
        page.wait_for_function("window.__animationVerification && window.__animationVerification.loaded")
        first = page.evaluate("document.querySelector('#player').toDataURL()")
        first_advances = page.evaluate("window.__animationVerification.frameAdvanceCount")
        page.wait_for_timeout(550)
        second = page.evaluate("document.querySelector('#player').toDataURL()")
        state = page.evaluate("window.__animationVerification")
        screenshot = OUT / "browser-player-native-160.png"
        page.screenshot(path=str(screenshot), full_page=True)
        browser_version = browser.version
        browser.close()
    result = {
        "status": "passed" if (
            state["loaded"] and state["textureDecoded"] and state["rectanglesInBounds"]
            and state["frameAdvanceCount"] > first_advances and first != second
            and not state["errors"] and not console_errors and not page_errors
        ) else "failed",
        "url": URL,
        "browser": browser_version,
        "browser_executable": executable,
        "loaded": state["loaded"],
        "texture_decoded": state["textureDecoded"],
        "rectangles_in_bounds": state["rectanglesInBounds"],
        "frame_advance_count": state["frameAdvanceCount"],
        "canvas_changed": first != second,
        "player_errors": state["errors"],
        "console_errors": console_errors,
        "page_errors": page_errors,
        "screenshot": {"file": screenshot.name, "sha256": hashlib.sha256(screenshot.read_bytes()).hexdigest()},
    }
    (OUT / "browser-verification.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
