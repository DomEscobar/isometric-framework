#!/usr/bin/env python3
"""Authorized, budget-bounded live API journey for one existing WAN video.

Secrets are read into this harness process only and passed only to its isolated
localhost child. Trace records contain hashes and paths, never secret values or
inline media payloads.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quality_gates import evaluate_atlas, evaluate_cutouts
from store import Store

MODEL = "google/gemini-3.8-flash"
REMOVER = "wavespeed-ai/image-background-remover"
SOURCE = ROOT / "artifacts/review-candidates/wan-existing-accepted-window/source.mp4"
OPENCLAW_DB = Path("/root/.openclaw/state/openclaw.sqlite")
HERMES_ENV = Path("/root/.hermes/.env")
HOST = "127.0.0.1"
PORT = 4391
BASE = f"http://{HOST}:{PORT}"
TOTAL_CAP_USD = 1.0
REVIEW_MAX_OUTPUT = 600
REMOVAL_UNIT_QUOTE = 0.004
PREVIOUS_LEDGERS = [
    ROOT / "artifacts/live-e2e-20260920T212301Z-908cc8/cost-ledger.json",
    ROOT / "artifacts/live-e2e-20260920T220657Z-3883c7/cost-ledger.json",
    ROOT / "artifacts/live-e2e-20260920T221043Z-071236/cost-ledger.json",
]
REMOVER_QUOTE = ROOT / "artifacts/remover-live-quote-20260920T223023Z.json"


def utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def get_json(url: str, *, key: str | None = None, timeout: int = 30) -> tuple[int, dict[str, Any]]:
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read())
            return response.status, value if isinstance(value, dict) else {}
    except urllib.error.HTTPError as error:
        try:
            value = json.loads(error.read())
        except (UnicodeDecodeError, json.JSONDecodeError):
            value = {}
        return error.code, value if isinstance(value, dict) else {}


def load_openrouter_key() -> tuple[str, dict[str, Any]]:
    connection = sqlite3.connect(f"file:{OPENCLAW_DB}?mode=ro", uri=True)
    try:
        row = connection.execute(
            "SELECT name,value,allowed_hosts FROM secret_store_entries WHERE deleted_at_ms IS NULL AND name=?",
            ("OPWNROUTER_KEY_2",),
        ).fetchone()
    finally:
        connection.close()
    if not row:
        raise RuntimeError("authorized OpenRouter credential is absent")
    name, key, allowed_hosts = row
    if name != "OPWNROUTER_KEY_2" or not isinstance(key, str) or not key.startswith("sk-or-") or key.strip() != key:
        raise RuntimeError("authorized OpenRouter credential has invalid shape")
    if "openrouter.ai" not in (allowed_hosts or ""):
        raise RuntimeError("authorized OpenRouter credential is not allowed for openrouter.ai")
    return key, {"store": "read-only OpenClaw sqlite", "name": name, "allowed_host_verified": True, "key_shape_verified": True}


def load_wavespeed_key() -> str:
    values: dict[str, str] = {}
    for raw in HERMES_ENV.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            values[name] = value.strip().strip("\"").strip("'")
    key = values.get("WAVESPEED_API_KEY")
    if not key:
        raise RuntimeError("WaveSpeed credential is absent")
    return key


class Trace:
    def __init__(self, run_dir: Path, run_id: str):
        self.run_dir = run_dir
        self.run_id = run_id
        self.jsonl = run_dir / "trace.jsonl"
        self.markdown = run_dir / "TRACE.md"
        self.events: list[dict[str, Any]] = []
        if self.jsonl.exists():
            for line in self.jsonl.read_text(encoding="utf-8").splitlines():
                value = json.loads(line)
                if isinstance(value, dict) and value.get("run_id") == run_id:
                    self.events.append(value)

    def add(self, event: str, **details: Any) -> dict[str, Any]:
        record = {"run_id": self.run_id, "sequence": len(self.events) + 1, "utc": utc(), "event": event, **details}
        with self.jsonl.open("a", encoding="utf-8") as output:
            output.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
        self.events.append(record)
        lines = [f"# Trace {self.run_id}", "", "Secrets and inline media payloads are excluded.", ""]
        for item in self.events:
            lines.append(f"## {item['sequence']}. {item['event']} — {item['utc']}")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps({key: value for key, value in item.items() if key not in {"run_id", "sequence", "utc", "event"}}, indent=2, sort_keys=True))
            lines.append("```")
            lines.append("")
        self.markdown.write_text("\n".join(lines), encoding="utf-8")
        return record

    def stage_start(self, name: str, **details: Any) -> tuple[float, str]:
        started = utc()
        self.add("stage_start", stage=name, started_at_utc=started, **details)
        return time.monotonic(), started

    def stage_end(self, name: str, marker: tuple[float, str], *, status: str, **details: Any) -> None:
        self.add(
            "stage_end", stage=name, status=status, started_at_utc=marker[1], ended_at_utc=utc(),
            duration_seconds=round(time.monotonic() - marker[0], 6), **details,
        )


class Ledger:
    def __init__(self, path: Path, trace: Trace):
        self.path = path
        self.trace = trace
        self.value: dict[str, Any] = {
            "version": 1, "run_id": trace.run_id, "currency": "USD", "total_cap_usd": TOTAL_CAP_USD,
            "entries": [], "known_billed_cost_usd": 0.0, "open_or_ambiguous_liability_usd": 0.0,
            "maximum_accounted_total_usd": 0.0, "updated_at_utc": utc(),
        }
        for index, previous_path in enumerate(PREVIOUS_LEDGERS, start=1):
            previous = json.loads(previous_path.read_text(encoding="utf-8"))
            if index > 1:
                previous_entries = [item for item in previous.get("entries", []) if item.get("status") != "linked_prior_liability"]
                previous_open = sum(float(item.get("open_liability_usd") or 0) for item in previous_entries)
                previous_known = sum(float(item.get("known_billed_cost_usd") or 0) for item in previous_entries)
            else:
                previous_open = float(previous.get("open_or_ambiguous_liability_usd") or 0)
                previous_known = float(previous.get("known_billed_cost_usd") or 0)
            self.value["entries"].append({
                "id": f"prior-live-e2e-{index}", "stage": "automatic_source_review",
                "provider": "openrouter", "model": MODEL,
                "reserved_worst_case_usd": round(previous_open + previous_known, 9),
                "known_billed_cost_usd": round(previous_known, 9) if previous_known else None,
                "open_liability_usd": round(previous_open, 9), "status": "linked_prior_liability",
                "basis": {"ledger": str(previous_path), "run_id": previous.get("run_id"), "authoritative_reconciliation": "prior receipt preserved; historical missing ID remains unreconciled"},
            })
        self.write()

    def write(self) -> None:
        known = sum(float(item.get("known_billed_cost_usd") or 0) for item in self.value["entries"])
        open_liability = sum(float(item.get("open_liability_usd") or 0) for item in self.value["entries"])
        total = known + open_liability
        if total > TOTAL_CAP_USD + 1e-12:
            raise RuntimeError("shared USD1 ledger cap would be exceeded")
        self.value.update({
            "known_billed_cost_usd": round(known, 9),
            "open_or_ambiguous_liability_usd": round(open_liability, 9),
            "maximum_accounted_total_usd": round(total, 9),
            "updated_at_utc": utc(),
        })
        atomic_json(self.path, self.value)

    def reserve(self, entry_id: str, *, stage: str, provider: str, model: str, amount: float, basis: dict[str, Any]) -> None:
        if any(item["id"] == entry_id for item in self.value["entries"]):
            raise RuntimeError("duplicate ledger entry")
        self.value["entries"].append({
            "id": entry_id, "stage": stage, "provider": provider, "model": model,
            "reserved_worst_case_usd": round(amount, 9), "known_billed_cost_usd": None,
            "open_liability_usd": round(amount, 9), "status": "reserved", "basis": basis,
        })
        self.write()
        self.trace.add("cost_reserved", entry_id=entry_id, stage=stage, amount_usd=amount, maximum_accounted_total_usd=self.value["maximum_accounted_total_usd"], basis=basis)

    def revise_reservation(self, entry_id: str, amount: float, basis: dict[str, Any]) -> None:
        item = next(item for item in self.value["entries"] if item["id"] == entry_id)
        item["reserved_worst_case_usd"] = round(amount, 9)
        item["open_liability_usd"] = round(amount, 9)
        item["basis"] = basis
        item["status"] = "reserved"
        self.write()
        self.trace.add("cost_reservation_revised", entry_id=entry_id, amount_usd=amount, maximum_accounted_total_usd=self.value["maximum_accounted_total_usd"], basis=basis)

    def settle_known(self, entry_id: str, amount: float, provider_reference: str | None) -> None:
        item = next(item for item in self.value["entries"] if item["id"] == entry_id)
        item["known_billed_cost_usd"] = round(amount, 9)
        item["open_liability_usd"] = 0.0
        item["status"] = "known_billed"
        item["provider_reference"] = provider_reference
        self.write()
        self.trace.add("cost_settled_known", entry_id=entry_id, known_billed_cost_usd=amount, provider_reference=provider_reference, maximum_accounted_total_usd=self.value["maximum_accounted_total_usd"])

    def leave_open(self, entry_id: str, *, status: str, references: list[str]) -> None:
        item = next(item for item in self.value["entries"] if item["id"] == entry_id)
        item["status"] = status
        item["provider_references"] = references
        self.write()
        self.trace.add("cost_liability_left_open", entry_id=entry_id, status=status, open_liability_usd=item["open_liability_usd"], provider_references=references)


def port_free() -> None:
    with socket.socket() as probe:
        probe.bind((HOST, PORT))


def start_server(environment: dict[str, str], log_path: Path) -> subprocess.Popen[bytes]:
    log = log_path.open("wb")
    process = subprocess.Popen(
        [str(ROOT / ".venv/bin/python"), "-m", "uvicorn", "app:app", "--host", HOST, "--port", str(PORT), "--log-level", "warning"],
        cwd=ROOT, env=environment, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
    )
    process._animation_log = log  # type: ignore[attr-defined]
    with httpx.Client(base_url=BASE, timeout=5) as client:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"isolated API exited with status {process.returncode}")
            try:
                if client.get("/health").status_code == 200:
                    return process
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
    raise RuntimeError("isolated API did not become healthy")


def stop_server(process: subprocess.Popen[bytes] | None) -> None:
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    if process and hasattr(process, "_animation_log"):
        process._animation_log.close()  # type: ignore[attr-defined]


def wait_terminal(client: httpx.Client, headers: dict[str, str], job_id: str, timeout: float = 180) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/v1/jobs/{job_id}", headers=headers)
        response.raise_for_status()
        job = response.json()
        if job["state"] not in {"queued", "running"}:
            return job
        time.sleep(0.25)
    raise RuntimeError("isolated API stage timed out")


def approve_exact(client: httpx.Client, headers: dict[str, str], job_id: str, artifact: dict[str, Any]) -> None:
    response = client.post(
        f"/v1/jobs/{job_id}/reviews", headers=headers,
        json={"artifact": artifact["name"], "sha256": artifact["sha256"], "decision": "approve"},
    )
    response.raise_for_status()
    receipt = response.json()
    if not receipt.get("approved") or receipt.get("sha256") != artifact["sha256"] or receipt.get("revision") != artifact["revision"]:
        raise RuntimeError("exact technical-gate approval receipt mismatch")


def create_previews(workdir: Path, run_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    frames: list[Image.Image] = []
    for record in manifest["frames"]:
        source = workdir / record["source"]["output"]
        with Image.open(source) as opened:
            frames.append(opened.convert("RGBA"))
    fps = float(manifest["clip"]["fps"])
    duration_ms = max(1, round(1000 / fps))
    native = run_dir / "preview-native.gif"
    enlarged = run_dir / "preview-enlarged-4x.gif"
    frames[0].save(native, save_all=True, append_images=frames[1:], loop=0, duration=duration_ms, disposal=2, transparency=0)
    enlarged_frames = [frame.resize((frame.width * 4, frame.height * 4), Image.Resampling.NEAREST) for frame in frames]
    enlarged_frames[0].save(enlarged, save_all=True, append_images=enlarged_frames[1:], loop=0, duration=duration_ms, disposal=2, transparency=0)
    atlas_target = run_dir / "atlas.png"
    manifest_target = run_dir / "atlas-manifest.json"
    shutil.copyfile(workdir / "atlas.png", atlas_target)
    shutil.copyfile(workdir / "atlas-manifest.json", manifest_target)
    video = run_dir / "preview-native.mp4"
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y", "-framerate", f"{fps:.12g}",
            "-i", str(workdir / "normalized-frame-%04d.png"),
            "-frames:v", str(len(frames)), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video),
        ],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
    )
    frame = manifest["frames"][0]["rect"]
    preview_html = run_dir / "animated-preview.html"
    preview_html.write_text(f"""<!doctype html>
<meta charset=\"utf-8\"><title>Live E2E sprite preview</title>
<style>body{{background:#20242a;color:#eee;font:16px system-ui}} section{{margin:20px}} canvas{{background:repeating-conic-gradient(#888 0 25%,#aaa 0 50%) 0/16px 16px;image-rendering:pixelated}} .enlarged{{width:{frame['width']*4}px;height:{frame['height']*4}px}}</style>
<h1>Actual atlas playback</h1>
<section><h2>Native scale (1 atlas pixel = 1 display pixel)</h2><canvas id=n width={frame['width']} height={frame['height']}></canvas></section>
<section><h2>Optional enlarged view (4× nearest-neighbour)</h2><canvas id=e class=enlarged width={frame['width']} height={frame['height']}></canvas></section>
<p>Timing: {html.escape(str(fps))} FPS from atlas manifest; foot anchor {html.escape(json.dumps(manifest['frames'][0]['anchor']))}.</p>
<script>Promise.all([fetch('atlas-manifest.json').then(r=>r.json()),new Promise((ok,no)=>{{let i=new Image;i.onload=()=>ok(i);i.onerror=no;i.src='atlas.png'}})]).then(([m,img])=>{{let k=0,last=performance.now(),step=1000/m.clip.fps;function draw(t){{if(t-last>=step){{k=(k+Math.floor((t-last)/step))%m.frames.length;last=t-(t-last)%step}}let r=m.frames[k].rect;for(let id of ['n','e']){{let c=document.getElementById(id),x=c.getContext('2d');x.clearRect(0,0,c.width,c.height);x.imageSmoothingEnabled=false;x.drawImage(img,r.x,r.y,r.width,r.height,0,0,c.width,c.height)}}requestAnimationFrame(draw)}}requestAnimationFrame(draw)}})</script>
""", encoding="utf-8")
    for image in enlarged_frames + frames:
        image.close()
    bundle = run_dir / "sprite-export.zip"
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in (atlas_target, manifest_target, native, enlarged, video, preview_html):
            archive.write(path, path.name)
    return {
        "native_gif": {"path": str(native), "sha256": sha256(native), "timing_note": f"GIF integer delay {duration_ms}ms; HTML is authoritative at {fps} FPS"},
        "enlarged_gif": {"path": str(enlarged), "sha256": sha256(enlarged), "label": "optional 4x nearest-neighbour view"},
        "native_video": {"path": str(video), "sha256": sha256(video), "dimensions": [frames[0].width, frames[0].height], "transparency_note": "MP4 is a convenience preview; atlas PNG/GIF retain alpha"},
        "html": {"path": str(preview_html), "sha256": sha256(preview_html), "exact_manifest_fps": fps},
        "atlas": {"path": str(atlas_target), "sha256": sha256(atlas_target)},
        "manifest": {"path": str(manifest_target), "sha256": sha256(manifest_target)},
        "zip": {"path": str(bundle), "sha256": sha256(bundle)},
    }


def write_report(run_dir: Path, report: dict[str, Any]) -> None:
    atomic_json(run_dir / "LIVE_E2E_REPORT.json", report)
    lines = [
        f"# Live E2E report — {report['run_id']}", "",
        f"Status: {report['status']}",
        f"Started: {report['started_at_utc']}",
        f"Ended: {report.get('ended_at_utc')}",
        f"Source: {report['source']['path']}",
        f"Source SHA-256: {report['source']['sha256']}", "",
        "## Result", "", report.get("summary", ""), "",
        "## Cost", "", json.dumps(report.get("cost", {}), indent=2, sort_keys=True), "",
        "## Automatic model decision", "", json.dumps(report.get("automatic_review"), indent=2, sort_keys=True), "",
        "## Technical quality gates", "", json.dumps(report.get("quality_gates"), indent=2, sort_keys=True), "",
        "## Outputs", "", json.dumps(report.get("outputs"), indent=2, sort_keys=True), "",
        "## Scope limits", "",
        "- This is one accepted existing WAN source and one direction only.",
        "- It does not implement or prove multi-direction aggregate export or full autopilot generation.",
        "- Technical alpha/atlas checks are not a visual-quality certificate.",
        "- No new facing or video was generated.",
    ]
    if report.get("error"):
        lines.extend(["", "## Stop/error", "", str(report["error"])])
    (run_dir / "LIVE_E2E_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run() -> tuple[int, Path]:
    run_id = "live-e2e-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)
    run_dir = ROOT / "artifacts" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    os.chmod(run_dir, 0o700)
    trace = Trace(run_dir, run_id)
    ledger = Ledger(run_dir / "cost-ledger.json", trace)
    started = utc()
    report: dict[str, Any] = {
        "run_id": run_id, "status": "running", "started_at_utc": started,
        "source": {"path": str(SOURCE), "sha256": sha256(SOURCE), "bytes": SOURCE.stat().st_size},
        "paid_public_policy_changed": False, "new_video_or_facing_generation": False,
        "quality_gates": {}, "outputs": {},
    }
    process: subprocess.Popen[bytes] | None = None
    try:
        trace.add("run_started", total_cap_usd=TOTAL_CAP_USD, source=report["source"], constraints={"source_video_retries": 0, "max_reviewer_calls": 1, "fallback": False})
        preflight = trace.stage_start("provider_preflight")
        openrouter_key, credential_record = load_openrouter_key()
        key_status, key_data = get_json("https://openrouter.ai/api/v1/key", key=openrouter_key)
        if key_status != 200 or not isinstance(key_data.get("data"), dict):
            raise RuntimeError(f"OpenRouter key verification failed with HTTP {key_status}")
        credits_status, credits_data = get_json("https://openrouter.ai/api/v1/credits", key=openrouter_key)
        models_status, models_data = get_json("https://openrouter.ai/api/v1/models")
        if models_status != 200:
            raise RuntimeError(f"OpenRouter model metadata fetch failed with HTTP {models_status}")
        matches = [item for item in models_data.get("data", []) if isinstance(item, dict) and item.get("id") == MODEL]
        if len(matches) != 1:
            raise RuntimeError("exact OpenRouter reviewer model is absent or ambiguous")
        model = matches[0]
        context_length = model.get("context_length")
        pricing = model.get("pricing")
        if type(context_length) is not int or not isinstance(pricing, dict):
            raise RuntimeError("OpenRouter model context/pricing metadata is invalid")
        prompt_price = float(pricing["prompt"])
        completion_price = float(pricing["completion"])
        architecture = model.get("architecture")
        supported = model.get("supported_parameters")
        if not isinstance(architecture, dict) or not {"text", "image"} <= set(architecture.get("input_modalities", [])):
            raise RuntimeError("exact model does not advertise required modalities")
        if not isinstance(supported, list) or not {"response_format", "max_tokens"} <= set(supported):
            raise RuntimeError("exact model does not advertise required structured parameters")
        key_info = key_data["data"]
        remaining = key_info.get("limit_remaining")
        if credits_status == 200 and isinstance(credits_data.get("data"), dict):
            credits = credits_data["data"]
            total_credits, total_usage = credits.get("total_credits"), credits.get("total_usage")
            if type(total_credits) in (int, float) and type(total_usage) in (int, float) and total_credits - total_usage <= 0:
                raise RuntimeError("OpenRouter credits are unavailable")
        wavespeed_key = load_wavespeed_key()
        ws_status, ws_data = get_json("https://api.wavespeed.ai/api/v3/balance", key=wavespeed_key)
        if ws_status != 200 or not isinstance(ws_data.get("data"), dict):
            raise RuntimeError(f"WaveSpeed balance verification failed with HTTP {ws_status}")
        balance_value = ws_data["data"].get("balance")
        if type(balance_value) not in (int, float) or balance_value < 0.20:
            raise RuntimeError("WaveSpeed balance is insufficient for bounded removals")
        remover_quote = json.loads(REMOVER_QUOTE.read_text(encoding="utf-8"))
        if remover_quote.get("model_id") != REMOVER or remover_quote.get("discounted_price") != REMOVAL_UNIT_QUOTE or remover_quote.get("required") != ["image"]:
            raise RuntimeError("fresh remover quote/schema record is invalid")
        remover_quote_path = run_dir / "remover-live-quote.json"
        shutil.copyfile(REMOVER_QUOTE, remover_quote_path)
        metadata = {
            "fetched_at_utc": utc(), "source": "https://openrouter.ai/api/v1/models", "id": MODEL,
            "canonical_slug": model.get("canonical_slug"), "context_length": context_length,
            "architecture": architecture, "supported_parameters": supported, "pricing": pricing,
            "fixed_run_price_claimed": False,
        }
        metadata_path = run_dir / "openrouter-model-metadata.json"
        atomic_json(metadata_path, metadata)
        trace.stage_end(
            "provider_preflight", preflight, status="passed", openrouter={**credential_record, "key_http_status": key_status, "credits_http_status": credits_status},
            wavespeed={"credential_found": True, "balance_http_status": ws_status, "balance_usd": balance_value},
            reviewer={"model": MODEL, "context_length": context_length, "prompt_usd_per_token": prompt_price, "completion_usd_per_token": completion_price, "metadata_sha256": sha256(metadata_path)},
            remover={"model": REMOVER, "refreshed_unit_quote_usd": REMOVAL_UNIT_QUOTE, "required_fields": ["image"], "quote_sha256": sha256(remover_quote_path), "fetched_at_utc": remover_quote.get("fetched_at_utc")},
        )

        local_marker = trace.stage_start("free_local_candidate_analysis", source_sha256=report["source"]["sha256"])
        import animation_review
        analysis_dir = run_dir / "preflight-analysis"
        analysis_dir.mkdir()
        shutil.copyfile(SOURCE, analysis_dir / "video-output.mp4")
        analysis = animation_review.analyze_candidates(analysis_dir, "video-output.mp4")
        atomic_json(run_dir / "preflight-candidate-analysis.json", analysis)
        trace.stage_end("free_local_candidate_analysis", local_marker, status=analysis["status"], hard_failures=analysis["hard_failures"], candidates=analysis["candidates"], local_scores_are_visual_approval=False)
        if analysis["hard_failures"]:
            raise RuntimeError(f"accepted WAN source failed local gates: {analysis['hard_failures']}")
        bounded_request = animation_review.build_review_request(
            analysis_dir, "video-output.mp4", analysis, max_tokens=REVIEW_MAX_OUTPUT,
            request_binding={
                "request_id": "0" * 32,
                "source_sha256": analysis["source"]["sha256"],
                "source_revision": 1,
            },
        )
        evidence_bound = bounded_request["_review_evidence"]
        max_input = evidence_bound["conservative_input_token_bound"]
        if max_input + REVIEW_MAX_OUTPUT > context_length:
            raise RuntimeError("bounded numbered image evidence exceeds exact model context")
        review_reserve = max_input * prompt_price + REVIEW_MAX_OUTPUT * completion_price
        if type(remaining) in (int, float) and remaining < review_reserve:
            raise RuntimeError("OpenRouter key limit remaining is below the bounded reviewer reservation")
        maximum_selected_frames = min(10, max(candidate["end_source_frame_index"] - candidate["start_source_frame_index"] for candidate in analysis["candidates"]))
        maximum_removal_reserve = maximum_selected_frames * REMOVAL_UNIT_QUOTE
        ledger.reserve("openrouter-source-review", stage="automatic_source_review", provider="openrouter", model=MODEL, amount=review_reserve, basis={"max_input_tokens": max_input, "max_output_tokens": REVIEW_MAX_OUTPUT, "context_length": context_length, "evidence": evidence_bound, "prices_usd_per_token": {"prompt": prompt_price, "completion": completion_price}, "provider_max_price_usd_per_million": {"prompt": prompt_price * 1_000_000, "completion": completion_price * 1_000_000}})
        ledger.reserve("selected-frame-removals", stage="remove_background", provider="wavespeed", model=REMOVER, amount=maximum_removal_reserve, basis={"status": "pre-review maximum-candidate contingency", "maximum_candidate_frames": maximum_selected_frames, "unit_quote_usd": REMOVAL_UNIT_QUOTE})

        port_free()
        data_root = run_dir / "private-service-data"
        os.chmod(run_dir, 0o700)
        store = Store(data_root / "jobs.sqlite3", data_root / "jobs")
        job = store.create_job("reference.png", {"controlled_server_fixture": True, "run_id": run_id}, b"live-e2e-server-fixture")
        job_id = job["id"]
        workdir = store.job_dir(job_id)
        video_target = workdir / "video-output.mp4"
        shutil.copyfile(SOURCE, video_target)
        with store.connect() as connection:
            store.upsert_artifact(connection, job_id, video_target.name, "controlled_server_fixture", video_target)
        artifact = store.get_artifact(job_id, video_target.name)
        if not artifact:
            raise RuntimeError("controlled video fixture was not recorded")
        token = secrets.token_urlsafe(36)
        environment = os.environ.copy()
        environment.update({
            "ANIMATION_API_TOKEN": token, "ANIMATION_DATA_DIR": str(data_root),
            "ANIMATION_REVIEW_ENABLED": "1", "ANIMATION_REVIEW_MAX_USD": str(review_reserve),
            "ANIMATION_REVIEW_MAX_INPUT_TOKENS": str(max_input), "ANIMATION_REVIEW_MAX_OUTPUT_TOKENS": str(REVIEW_MAX_OUTPUT),
            "ANIMATION_REVIEW_MODEL_METADATA_FILE": str(metadata_path), "OPENROUTER_API_KEY": openrouter_key,
            "ANIMATION_PAID_ENABLED": "1", "ANIMATION_MAX_STAGE_USD": "0.20", "WAVESPEED_API_KEY": wavespeed_key,
            "PYTHONUNBUFFERED": "1",
        })
        process = start_server(environment, run_dir / "isolated-server.log")
        headers = {"Authorization": f"Bearer {token}"}
        trace.add("isolated_api_started", base_url=BASE, job_id=job_id, paid_policy_scope="isolated child only", public_policy_changed=False, credential_values_traced=False)
        with httpx.Client(base_url=BASE, timeout=30) as client:
            unauthorized = client.get(f"/v1/jobs/{job_id}")
            if unauthorized.status_code != 401:
                raise RuntimeError("isolated API authentication check failed")
            review_marker = trace.stage_start(
                "automatic_source_review_api", provider="openrouter", model=MODEL,
                sanitized_request={"artifact": artifact["name"], "source_sha256": artifact["sha256"], "source_revision": artifact["revision"], "media_path": str(video_target), "inline_media_payload_traced": False, "fallback": False, "max_output_tokens": REVIEW_MAX_OUTPUT, "max_input_tokens_reserved": max_input},
            )
            response = client.post(
                f"/v1/jobs/{job_id}/automatic-review", headers=headers,
                json={"artifact": artifact["name"], "sha256": artifact["sha256"], "revision": artifact["revision"], "authorize_paid_review": True, "budget_cap_usd": review_reserve},
            )
            response.raise_for_status()
            reviewed_job = wait_terminal(client, headers, job_id, timeout=240)
            review = reviewed_job["automatic_reviews"][0]
            result_path = workdir / "automatic-review-result.json"
            review_result = json.loads(result_path.read_text(encoding="utf-8"))
            trace.stage_end(
                "automatic_source_review_api", review_marker, status=review["status"],
                response_id=review_result.get("response_id"), routed_provider=review_result.get("provider"),
                usage=review_result.get("usage"), decision={key: review_result.get(key) for key in ("status", "provider_decision", "selected_candidate", "issues", "rejection_reason", "self_reported_confidence")},
                schema_validated=review_result.get("provider_decision") in {"approve", "reject", "needs_attention"} and review_result.get("diagnostic", {}).get("phase") != "output_validation",
                diagnostic=review_result.get("diagnostic"), evidence=review_result.get("budget", {}).get("evidence"),
                raw_message=review_result.get("raw_message"),
                retry_decision="no retry; one authorized reviewer call only", result_sha256=sha256(result_path),
            )
            report["automatic_review"] = review_result
            budget = review_result.get("budget") if isinstance(review_result.get("budget"), dict) else {}
            actual_review_cost = budget.get("actual_cost_usd")
            if type(actual_review_cost) in (int, float):
                ledger.settle_known("openrouter-source-review", float(actual_review_cost), review_result.get("response_id"))
            else:
                ledger.leave_open("openrouter-source-review", status="ambiguous_or_cost_unknown", references=[value for value in [review_result.get("response_id")] if isinstance(value, str)])
            if review["status"] != "approved":
                ledger.revise_reservation("selected-frame-removals", 0.0, {"reason": "source not approved; no removals executed"})
                raise RuntimeError(f"Gemini source review did not approve a candidate: {review_result.get('rejection_reason') or review_result.get('reason')}")
            selected = review["selected_candidate"]
            selected_sampling = review["selected_sampling"]
            selected_count = len(selected_sampling["indices"])
            removal_reserve = selected_count * REMOVAL_UNIT_QUOTE
            ledger.revise_reservation("selected-frame-removals", removal_reserve, {"selected_candidate_id": selected["id"], "selected_frame_count": selected_count, "unit_quote_usd": REMOVAL_UNIT_QUOTE, "quote_refreshed_before_submit": True})

            extracted_job = client.get(f"/v1/jobs/{job_id}", headers=headers).json()
            selected_artifacts = [item for item in extracted_job["artifacts"] if item["name"].startswith("selected-frame-") and item["name"].endswith(".png")]
            selected_artifacts.sort(key=lambda item: item["name"])
            extraction = json.loads((workdir / "extract-frames.json").read_text(encoding="utf-8"))
            actual_indices = [item["source_index"] for item in extraction["frames"]]
            expected_indices = selected_sampling["indices"]
            extraction_gate = {
                "status": "passed" if len(selected_artifacts) == selected_count and actual_indices == expected_indices and extraction["source"]["sha256"] == artifact["sha256"] and extraction.get("automatic_selection") is True else "rejected",
                "technical_checks_only": True, "visual_quality_certified": False,
                "source_sha256": extraction["source"]["sha256"], "original_indices": actual_indices,
                "timestamps_seconds": [item["timestamp_seconds"] for item in extraction["frames"]],
                "cycle_duration_seconds": selected_sampling["cycle_duration_seconds"],
                "playback_fps": selected_sampling["playback_fps"], "duration_preserved": True,
                "frame_hashes": {item["name"]: item["sha256"] for item in selected_artifacts},
            }
            atomic_json(run_dir / "extraction-quality-gate.json", extraction_gate)
            report["quality_gates"]["extraction"] = extraction_gate
            trace.add("extraction_quality_gate", **extraction_gate)
            if extraction_gate["status"] != "passed":
                ledger.revise_reservation("selected-frame-removals", 0.0, {"reason": "extraction gate rejected before remover submission"})
                raise RuntimeError("exact source extraction quality gate rejected")
            for selected_artifact in selected_artifacts:
                approve_exact(client, headers, job_id, selected_artifact)
            trace.add("technical_handoff", from_stage="exact_extraction", to_stage="background_removal", approvals=len(selected_artifacts), approval_basis="hash/index/provenance gate; not visual certification")

            removal_marker = trace.stage_start("selected_frame_background_removal", provider="wavespeed", model=REMOVER, selected_frame_count=selected_count, reserved_usd=removal_reserve, sanitized_request={"inputs": [{"path": item["name"], "sha256": item["sha256"]} for item in selected_artifacts], "inline_payloads_traced": False})
            prior_ids: set[str] = set()
            removal_job: dict[str, Any] = {}
            for attempt in range(1, 400):
                response = client.post(
                    f"/v1/jobs/{job_id}/stages", headers=headers,
                    json={"stage": "remove_background", "params": {"inputs": [item["name"] for item in selected_artifacts], "preset": "waldlicht-removal-v1"}, "authorize_paid": True, "budget_cap_usd": removal_reserve},
                )
                response.raise_for_status()
                removal_job = wait_terminal(client, headers, job_id, timeout=180)
                state_path = workdir / "remove-background-state.json"
                state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
                identifiers = [item.get("prediction_id") for item in state.get("items", []) if isinstance(item.get("prediction_id"), str)]
                new_ids = sorted(set(identifiers) - prior_ids)
                prior_ids.update(identifiers)
                trace.add("removal_poll_cycle", attempt=attempt, prediction_ids=identifiers, new_prediction_ids=new_ids, item_statuses=[{"order": item.get("order"), "status": item.get("status"), "prediction_id": item.get("prediction_id")} for item in state.get("items", [])], retry_decision="poll/requeue same known request state" if state.get("status") != "completed" else "completed; no retry")
                if any(item.get("status") == "submission_unknown" for item in state.get("items", [])):
                    ledger.leave_open("selected-frame-removals", status="ambiguous_submission", references=identifiers)
                    raise RuntimeError("WaveSpeed remover submission became ambiguous; no retry performed")
                if state.get("status") == "completed":
                    break
                if removal_job.get("state") == "failed":
                    raise RuntimeError(f"removal stage failed: {removal_job.get('message')}")
                if not identifiers:
                    raise RuntimeError("removal stage needs attention without a known prediction ID")
                time.sleep(1.5)
            else:
                ledger.leave_open("selected-frame-removals", status="known_predictions_pending", references=sorted(prior_ids))
                raise RuntimeError("known remover predictions did not complete within bounded polls")
            trace.stage_end("selected_frame_background_removal", removal_marker, status="completed", prediction_ids=sorted(prior_ids), output_state_sha256=sha256(workdir / "remove-background-state.json"), actual_charge_usd=None, actual_charge_known=False)
            ledger.leave_open("selected-frame-removals", status="completed_charge_not_authoritatively_reported", references=sorted(prior_ids))

            completed_job = client.get(f"/v1/jobs/{job_id}", headers=headers).json()
            cutouts = [item for item in completed_job["artifacts"] if item["name"].startswith("cutout-frame-") and item["name"].endswith(".png")]
            cutouts.sort(key=lambda item: item["name"])
            cutout_gate = evaluate_cutouts(workdir, [item["name"] for item in cutouts])
            atomic_json(run_dir / "cutout-quality-gate.json", cutout_gate)
            report["quality_gates"]["cutouts"] = cutout_gate
            trace.add("cutout_quality_gate", status=cutout_gate["status"], rejection_reasons=cutout_gate["rejection_reasons"], frame_count=len(cutouts), output_hashes={item["name"]: item["sha256"] for item in cutouts}, technical_checks_only=True, visual_quality_certified=False)
            if cutout_gate["status"] != "passed":
                raise RuntimeError(f"cutout alpha/geometry gate rejected: {cutout_gate['rejection_reasons']}")
            for cutout in cutouts:
                approve_exact(client, headers, job_id, cutout)
            trace.add("technical_handoff", from_stage="background_removal", to_stage="atlas_pack", approvals=len(cutouts), approval_basis="alpha/geometry gate; not visual certification")

            pack_marker = trace.stage_start("atlas_pack", provider="local", model=None, input_hashes={item["name"]: item["sha256"] for item in cutouts})
            pack_params = {
                "inputs": [item["name"] for item in cutouts], "image_id": "keeper-walk-ne-live", "action": "walk", "direction": "ne",
                "fps": selected_sampling["playback_fps"], "loop": True,
                "canvas": {"width": 80, "height": 80}, "target_visible_height": 58,
                "target_root": {"x": 40, "y": 72}, "anchor": {"x": 0.5, "y": 0.9},
                "gutter": 2, "columns": 8, "resample": "lanczos",
                "cleanup": {"recipe": "conservative-alpha-fringe-v1", "minimum_visible_alpha": 8},
            }
            response = client.post(f"/v1/jobs/{job_id}/stages", headers=headers, json={"stage": "pack", "params": pack_params})
            response.raise_for_status()
            packed_job = wait_terminal(client, headers, job_id, timeout=180)
            if packed_job["state"] == "failed":
                raise RuntimeError(f"atlas pack failed: {packed_job.get('message')}")
            atlas_gate = evaluate_atlas(workdir, "atlas.png", "atlas-manifest.json")
            atomic_json(run_dir / "atlas-quality-gate.json", atlas_gate)
            report["quality_gates"]["atlas"] = atlas_gate
            trace.stage_end("atlas_pack", pack_marker, status=atlas_gate["status"], atlas_sha256=atlas_gate["atlas_sha256"], manifest_sha256=atlas_gate["manifest_sha256"], frame_count=atlas_gate["frame_count"], fps=atlas_gate["fps"], clip_duration_seconds=atlas_gate["duration_seconds"], foot_anchor=atlas_gate["foot_anchor"], rejection_reasons=atlas_gate["rejection_reasons"], visual_quality_certified=False)
            if atlas_gate["status"] != "passed":
                raise RuntimeError(f"atlas integrity/timing gate rejected: {atlas_gate['rejection_reasons']}")
            manifest = json.loads((workdir / "atlas-manifest.json").read_text(encoding="utf-8"))
            previews = create_previews(workdir, run_dir, manifest)
            report["outputs"] = previews
            trace.add("preview_created", **previews, native_scale=True, optional_enlarged_view_labelled=True, actual_atlas_playback=True)

        report.update({
            "status": "completed_technical_gates_passed_visual_review_pending",
            "summary": "The real reviewer approved one exact source interval; only those native source frames were extracted and removed. Deterministic alpha/geometry and atlas integrity/timing gates passed. Visual acceptability is not certified until the retained atlas/preview is inspected.",
            "job_id": job_id, "selected_candidate": selected,
            "cost": ledger.value, "ended_at_utc": utc(),
        })
        trace.add("run_completed", status=report["status"], outputs=report["outputs"], cost={key: ledger.value[key] for key in ("known_billed_cost_usd", "open_or_ambiguous_liability_usd", "maximum_accounted_total_usd")})
        write_report(run_dir, report)
        return 0, run_dir
    except Exception as error:
        report.update({
            "status": "stopped_or_rejected", "summary": "The live journey stopped without certifying an atlas.",
            "error": str(error), "cost": ledger.value, "ended_at_utc": utc(),
        })
        trace.add("run_stopped", status=report["status"], error=str(error), retry_decision="no unapproved retry", cost={key: ledger.value[key] for key in ("known_billed_cost_usd", "open_or_ambiguous_liability_usd", "maximum_accounted_total_usd")})
        write_report(run_dir, report)
        return 1, run_dir
    finally:
        stop_server(process)
        trace.add("isolated_api_cleanup", process_stopped=True, public_service_untouched=True)
        report["ended_at_utc"] = utc()
        report["cost"] = ledger.value
        write_report(run_dir, report)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    code, run_dir = run()
    print(json.dumps({"status": "completed" if code == 0 else "stopped", "run_dir": str(run_dir), "report": str(run_dir / "LIVE_E2E_REPORT.md")}, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
