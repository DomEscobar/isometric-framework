from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pipeline

ROOT = Path(__file__).resolve().parents[1]
WORKDIR = ROOT / "artifacts" / "gemini-omni-video-3s-01"
ENV_FILE = Path("/root/.hermes/.env")
MAX_POLLS = 30
POLL_SECONDS = 10


def load_key() -> str:
    for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == "WAVESPEED_API_KEY":
            key = value.strip().strip('"').strip("'")
            if key:
                return key
    raise RuntimeError("WAVESPEED_API_KEY is unavailable")


def main() -> None:
    request = json.loads((WORKDIR / "user-request.json").read_text(encoding="utf-8"))
    quote = json.loads((WORKDIR / "quote.json").read_text(encoding="utf-8"))
    if quote.get("estimate") is not True or quote.get("unpriced_inputs") != []:
        raise RuntimeError("stored exact quote is incomplete")
    if float(quote["price"]) > float(request["budget"]["max_usd"]):
        raise RuntimeError("quote exceeds hard cap")
    os.environ["WAVESPEED_API_KEY"] = load_key()
    params = {
        "input": request["input"],
        "preset": request["preset"],
        "prompt": request["prompt"],
        "duration": request["duration"],
        "resolution": request["resolution"],
        "aspect_ratio": request["aspect_ratio"],
        "budget": request["budget"],
    }
    result = pipeline.run_stage("generate_video", WORKDIR, params)
    polls = 0
    while result.get("status") == "needs_attention" and result.get("details", {}).get("safe_resume") is True and polls < MAX_POLLS:
        time.sleep(POLL_SECONDS)
        result = pipeline.run_stage("generate_video", WORKDIR, params)
        polls += 1
    record = {"polls_after_initial_call": polls, "result": result}
    (WORKDIR / "harness-result.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    state = json.loads((WORKDIR / "generate-video-state.json").read_text(encoding="utf-8"))
    print(json.dumps({
        "status": result.get("status"),
        "submission_status": state.get("submission_status"),
        "prediction_id": state.get("prediction_id"),
        "polls": polls,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
