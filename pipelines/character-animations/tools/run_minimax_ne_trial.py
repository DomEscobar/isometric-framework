from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pipeline

WORKDIR = ROOT / "artifacts" / "minimax-ne-source-01"
ENV_FILE = Path("/root/.hermes/.env")
MAX_POLLS = 60
POLL_SECONDS = 10


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def dump(path: Path, value: object) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


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


def update_ledger(status: str, prediction_id: str | None) -> None:
    path = WORKDIR / "cost-ledger.json"
    ledger = json.loads(path.read_text(encoding="utf-8"))
    entry = next(item for item in ledger["entries"] if item["id"] == "minimax-ne-source-01-reservation")
    entry["status"] = status
    entry["prediction_id"] = prediction_id
    entry["actual_charge_usd"] = None
    entry["actual_charge_known"] = False
    ledger["updated_at_utc"] = now()
    dump(path, ledger)


def main() -> None:
    request = json.loads((WORKDIR / "request.json").read_text(encoding="utf-8"))
    quote = json.loads((WORKDIR / "quote.json").read_text(encoding="utf-8"))
    ledger = json.loads((WORKDIR / "cost-ledger.json").read_text(encoding="utf-8"))
    hold = next(item for item in ledger["entries"] if item["id"] == "minimax-ne-source-01-reservation")
    if hold["status"] != "held_before_submission" or hold["prediction_id"] is not None:
        raise RuntimeError("trial is not in a fresh held-before-submission state")
    if quote.get("estimate") is not True or quote.get("unpriced_inputs") != []:
        raise RuntimeError("stored exact quote is incomplete")
    if float(quote["price"]) > float(request["budget"]["max_usd"]):
        raise RuntimeError("undiscounted quote exceeds hard cap")
    if float(ledger["maximum_accounted_with_reservation_eur"]) > float(ledger["authorization"]["ceiling_eur"]):
        raise RuntimeError("cumulative ceiling exceeded")

    os.environ["WAVESPEED_API_KEY"] = load_key()
    params = {
        "input": request["input"],
        "preset": request["preset"],
        "prompt": request["prompt"],
        "duration": request["duration"],
        "resolution": request["resolution"],
        "budget": request["budget"],
    }
    started = now()
    try:
        result = pipeline.run_stage("generate_video", WORKDIR, params)
    except Exception:
        state_path = WORKDIR / "generate-video-state.json"
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            update_ledger(state.get("submission_status", "submission_exception_unknown"), state.get("prediction_id"))
        else:
            update_ledger("pre_submission_failure_no_liability", None)
        raise

    polls = 0
    while result.get("status") == "needs_attention" and result.get("details", {}).get("safe_resume") is True and polls < MAX_POLLS:
        time.sleep(POLL_SECONDS)
        result = pipeline.run_stage("generate_video", WORKDIR, params)
        polls += 1

    state = json.loads((WORKDIR / "generate-video-state.json").read_text(encoding="utf-8"))
    prediction_id = state.get("prediction_id")
    submission_status = state.get("submission_status")
    if submission_status == "submission_unknown":
        ledger_status = "ambiguous_submission_full_reservation_retained_no_retry"
    elif submission_status == "completed":
        ledger_status = "completed_charge_not_authoritatively_reported_full_reservation_retained"
    else:
        ledger_status = f"known_prediction_{submission_status}_full_reservation_retained"
    update_ledger(ledger_status, prediction_id)

    receipt = {
        "started_at_utc": started,
        "ended_at_utc": now(),
        "model": request["model"],
        "prediction_id": prediction_id,
        "submission_status": submission_status,
        "polls_after_initial_call": polls,
        "request": {
            "input": request["input"],
            "input_sha256": request["input_sha256"],
            "first_equals_last": True,
            "prompt": request["prompt"],
            "duration": request["duration"],
            "resolution": request["resolution"],
        },
        "quote": {key: quote[key] for key in ("price", "discounted_price", "currency", "estimate", "unpriced_inputs")},
        "provider_status": state.get("last_readback", {}).get("status"),
        "outputs_count": len(state.get("last_readback", {}).get("outputs", [])),
        "actual_charge_usd": None,
        "actual_charge_known": False,
        "result": result,
        "credential_or_hosted_urls_recorded": False,
    }
    dump(WORKDIR / "request-receipt.json", receipt)
    print(json.dumps({"status": result.get("status"), "submission_status": submission_status, "prediction_id": prediction_id, "polls": polls}, sort_keys=True))
    if submission_status != "completed":
        raise RuntimeError("single submission did not complete; no retry will be made")


if __name__ == "__main__":
    main()
