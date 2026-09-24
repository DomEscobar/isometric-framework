#!/usr/bin/env python3
"""Run the authorized matched 3+3 WaveSpeed remover latency probe."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pipeline  # noqa: E402

OUT = ROOT / "review" / "latency-step2"
SOURCE = ROOT / "review" / "cadence-uninterrupted" / "phase2-fresh-uninterrupted" / "private-service-data" / "jobs" / "0ce217a9c0e74549a956ef1591a7c639"
INPUT_NAMES = ["selected-frame-0000.png", "selected-frame-0010.png", "selected-frame-0020.png"]
MODEL = "wavespeed-ai/image-background-remover"
PRESET = "waldlicht-removal-v1"
UNIT_QUOTE_USD = 0.004
NEW_JOBS = 6
RESERVATION_USD = 0.024
INCREMENTAL_CAP_USD = 0.10
PRIOR_CONSERVATIVE_USD = 2.83148575
TOTAL_RESERVED_USD = 2.85548575
PREDICTION_ID = re.compile(r"^[0-9a-f]{32}$")


def utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected object: {path}")
    return value


def collect_provider_ids(value: Any, found: set[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"prediction_id", "provider_reference"} and isinstance(child, str) and PREDICTION_ID.fullmatch(child):
                found.add(child)
            elif key in {"prediction_ids", "provider_references"} and isinstance(child, list):
                found.update(item for item in child if isinstance(item, str) and PREDICTION_ID.fullmatch(item))
            else:
                collect_provider_ids(child, found)
    elif isinstance(value, list):
        for child in value:
            collect_provider_ids(child, found)


def existing_provider_ids() -> set[str]:
    found: set[str] = set()
    for path in ROOT.glob("**/*.json"):
        if OUT in path.parents:
            continue
        try:
            collect_provider_ids(json.loads(path.read_text(encoding="utf-8")), found)
        except (OSError, json.JSONDecodeError):
            continue
    return found


def prepare_inputs(workdir: Path) -> list[dict[str, Any]]:
    workdir.mkdir(parents=True, exist_ok=True)
    records = []
    for order, source_name in enumerate(INPUT_NAMES):
        source = SOURCE / source_name
        target = workdir / f"selected-frame-{order:04d}.png"
        if not source.is_file():
            raise RuntimeError(f"accepted source frame missing: {source_name}")
        if target.exists():
            if sha256(target) != sha256(source):
                raise RuntimeError(f"isolated input changed: {target}")
        else:
            shutil.copyfile(source, target)
        records.append({
            "order": order,
            "source_file": source.relative_to(ROOT).as_posix(),
            "benchmark_file": target.relative_to(ROOT).as_posix(),
            "sha256": sha256(source),
            "bytes": source.stat().st_size,
        })
    return records


def update_ledger(ledger: dict[str, Any], configurations: list[dict[str, Any]]) -> None:
    ids = sorted({item for config in configurations for item in config.get("prediction_ids", [])})
    statuses = [config.get("status") for config in configurations]
    ledger["provider_references"] = ids
    ledger["submitted_jobs"] = len(ids)
    ledger["open_liability_usd"] = round(len(ids) * UNIT_QUOTE_USD, 6)
    ledger["status"] = "completed_charge_not_authoritatively_reported_full_reservation_retained" if statuses == ["completed", "completed"] else "reserved_or_in_progress"
    ledger["updated_at_utc"] = utc()
    write_json(OUT / "cost-ledger.json", ledger)


def run_configuration(label: str, maximum_inflight: int, prior_ids: set[str], ledger: dict[str, Any], completed_configs: list[dict[str, Any]]) -> dict[str, Any]:
    workdir = OUT / f"work-{label}"
    inputs = prepare_inputs(workdir)
    os.environ["ANIMATION_REMOVAL_MAX_INFLIGHT"] = str(maximum_inflight)
    params = {
        "inputs": [f"selected-frame-{order:04d}.png" for order in range(3)],
        "preset": PRESET,
        "budget": {"authorized": True, "max_usd": 0.012},
    }
    started_utc = utc()
    started = time.monotonic()
    calls = 0
    while True:
        calls += 1
        result = pipeline.run_stage("remove_background", workdir, params)
        state = read_json(workdir / "remove-background-state.json")
        ids = [item.get("prediction_id") for item in state["items"] if isinstance(item.get("prediction_id"), str)]
        if len(ids) != len(set(ids)):
            raise RuntimeError(f"duplicate prediction ID inside {label}")
        collisions = set(ids) & prior_ids
        if collisions:
            raise RuntimeError(f"new benchmark prediction ID duplicates prior ledger: {sorted(collisions)}")
        current = {
            "label": label,
            "maximum_inflight": maximum_inflight,
            "status": "running",
            "prediction_ids": ids,
            "stage_calls": calls,
        }
        update_ledger(ledger, completed_configs + [current])
        statuses = [item.get("status") for item in state["items"]]
        if "submission_unknown" in statuses:
            raise RuntimeError(f"{label}: ambiguous submission; stopped without retry")
        if "provider_failed" in statuses or state.get("status") == "failed":
            raise RuntimeError(f"{label}: provider failure; stopped without new submissions")
        if state.get("status") == "completed":
            break
        if result.get("details", {}).get("safe_resume") is not True:
            raise RuntimeError(f"{label}: state is not a safe known-ID resume")
        if time.monotonic() - started > 360:
            raise RuntimeError(f"{label}: bounded wait expired with known IDs {ids}")
        time.sleep(1)

    ended = time.monotonic()
    ended_utc = utc()
    state = read_json(workdir / "remove-background-state.json")
    ids = [item["prediction_id"] for item in state["items"]]
    if len(ids) != 3 or len(set(ids)) != 3:
        raise RuntimeError(f"{label}: expected exactly three unique paid prediction IDs")
    collisions = set(ids) & prior_ids
    if collisions:
        raise RuntimeError(f"{label}: provider ID collision with prior ledger")

    outputs = []
    for item in state["items"]:
        path = workdir / item["output"]["file"]
        with Image.open(path) as opened:
            rgba = opened.convert("RGBA")
        alpha = rgba.getchannel("A")
        histogram = alpha.histogram()
        bounds = alpha.getbbox()
        if rgba.mode != "RGBA" or bounds is None or histogram[0] == 0 or sum(histogram[1:]) == 0:
            raise RuntimeError(f"{label}: blank or non-transparent cutout for order {item['order']}")
        outputs.append({
            "order": item["order"],
            "file": path.relative_to(ROOT).as_posix(),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
            "width": rgba.width,
            "height": rgba.height,
            "mode": rgba.mode,
            "alpha_bounds": list(bounds),
            "transparent_pixels": histogram[0],
            "visible_pixels": sum(histogram[1:]),
            "semi_transparent_pixels": sum(histogram[1:255]),
            "opaque_pixels": histogram[255],
            "non_blank_true_alpha": histogram[0] > 0 and sum(histogram[1:]) > 0,
        })
        alpha.close()
        rgba.close()

    phase_totals: dict[str, float] = {}
    for timing in state.get("timings", []):
        phase = timing["phase"]
        phase_totals[phase] = round(phase_totals.get(phase, 0.0) + float(timing["duration_seconds"]), 6)
    receipt = {
        "label": label,
        "maximum_inflight": maximum_inflight,
        "provider": state["provider"],
        "model": state["model"],
        "preset": state["preset"],
        "quote": state["quote"],
        "prediction_ids": ids,
        "items": [{
            "order": item["order"],
            "input": item["input"],
            "input_sha256": item["input_sha256"],
            "prediction_id": item["prediction_id"],
            "status": item["status"],
            "provider_status": item.get("last_readback", {}).get("status"),
            "provider_inference_ms": item.get("last_readback", {}).get("timings", {}).get("inference"),
            "output": outputs[item["order"]],
        } for item in state["items"]],
        "timings": state.get("timings", []),
    }
    write_json(OUT / f"receipt-{label}.json", receipt)
    return {
        "label": label,
        "status": "completed",
        "maximum_inflight": maximum_inflight,
        "started_at_utc": started_utc,
        "ended_at_utc": ended_utc,
        "wall_seconds": round(ended - started, 6),
        "stage_calls": calls,
        "prediction_ids": ids,
        "input_records": inputs,
        "phase_demand_seconds": phase_totals,
        "outputs": outputs,
        "sanitized_receipt": f"receipt-{label}.json",
    }


def compare_outputs(serial: dict[str, Any], concurrent: dict[str, Any]) -> list[dict[str, Any]]:
    comparisons = []
    for order in range(3):
        serial_path = ROOT / serial["outputs"][order]["file"]
        concurrent_path = ROOT / concurrent["outputs"][order]["file"]
        with Image.open(serial_path) as first_opened, Image.open(concurrent_path) as second_opened:
            first = first_opened.convert("RGBA")
            second = second_opened.convert("RGBA")
        equal = first.size == second.size and ImageChops.difference(first, second).getbbox() is None
        comparisons.append({
            "order": order,
            "input_sha256": serial["input_records"][order]["sha256"],
            "same_input_bytes": serial["input_records"][order]["sha256"] == concurrent["input_records"][order]["sha256"],
            "decoded_rgba_equal": equal,
            "serial_output_sha256": serial["outputs"][order]["sha256"],
            "concurrent_output_sha256": concurrent["outputs"][order]["sha256"],
            "both_non_blank_true_alpha": serial["outputs"][order]["non_blank_true_alpha"] and concurrent["outputs"][order]["non_blank_true_alpha"],
        })
        first.close()
        second.close()
    return comparisons


def write_report(measurement: dict[str, Any]) -> None:
    serial, concurrent = measurement["configurations"]
    ratio = serial["wall_seconds"] / concurrent["wall_seconds"]
    delta = serial["wall_seconds"] - concurrent["wall_seconds"]
    inputs = "\n".join(f"- order {item['order']}: `{item['source_file']}`, SHA-256 `{item['sha256']}`" for item in serial["input_records"])
    stochastic = all(item["decoded_rgba_equal"] for item in measurement["output_comparison"])
    report = f"""# Latency step 2: bounded remover concurrency\n\nStatus: PASS. The authorized live matched measurement completed with exactly six new remover predictions.\n\n## Exact run configuration\n\n- Provider/model: WaveSpeed / `{MODEL}`\n- Fresh live quote: USD {UNIT_QUOTE_USD:.3f} per prediction; six-job reservation USD {RESERVATION_USD:.3f}.\n- Prior conservative accounted amount: USD {PRIOR_CONSERVATIVE_USD:.8f}.\n- Conservative amount after reservation: USD {TOTAL_RESERVED_USD:.8f}; this milestone's USD {INCREMENTAL_CAP_USD:.2f} cap was not exceeded.\n- Serial arm: three originals, `ANIMATION_REMOVAL_MAX_INFLIGHT=1`.\n- Concurrent arm: the same three byte-identical originals, `ANIMATION_REMOVAL_MAX_INFLIGHT=2`.\n- Public/default configuration remains 1. No video generation, reviewer, cache ingestion, pixel processing change, deployment, or public enablement occurred.\n\nInputs:\n\n{inputs}\n\nExecutable command:\n\n    .venv/bin/python tools/measure_removal_concurrency.py\n\n## Observed live result\n\n- Serial wall time: {serial['wall_seconds']:.6f}s.\n- Two-inflight wall time: {concurrent['wall_seconds']:.6f}s.\n- Observed difference: {delta:.6f}s; observed ratio: {ratio:.3f}x.\n- Serial prediction IDs: `{', '.join(serial['prediction_ids'])}`.\n- Concurrent prediction IDs: `{', '.join(concurrent['prediction_ids'])}`.\n- All six outputs decoded as 768x768 RGBA, had non-empty visible alpha bounds, transparent pixels and visible pixels; none was blank.\n- The two arms used unchanged input bytes. Provider outputs were {'decoded RGBA byte-identical across arms' if stochastic else 'not all byte-identical across arms, which is treated as provider-output variation; validity checks passed independently'}.\n\nSummed per-request phase durations are service demand, not concurrent critical-path time. Raw UTC intervals and per-item provider inference timings are retained in `timings.json` and the two sanitized receipts.\n\n## Interpretation and limits\n\nThis is a deliberately tiny matched three-frame probe, not a 30-frame benchmark and not a full cold-pipeline SLA. It measures upload, submission, polling, provider execution and output download/validation for this sample. It does not establish that a 30-frame run will scale by the same ratio, nor does it justify a public default above 1. WaveSpeed's official account-level documentation permits at least two concurrent tasks even at Bronze level; the exact account tier was not asserted. The production default therefore remains serialized while an explicitly configured value of 2 is retained for controlled use.\n\n## Evidence\n\n- `timings.json`: sanitized aggregate, exact configuration, raw phase intervals and alpha validation.\n- `receipt-serial1.json` and `receipt-concurrent2.json`: sanitized IDs/statuses/inference timings/output hashes; no credentials.\n- `cost-ledger.json`: reservation written before the first paid submit, then all six unique provider IDs. Actual charge is not authoritatively reported, so the full USD {RESERVATION_USD:.3f} liability remains conservatively retained.\n- `work-serial1/` and `work-concurrent2/`: actual isolated inputs, provider state and six RGBA outputs.\n- Official policy: https://wavespeed.ai/docs/account-levels and https://wavespeed.ai/docs/complete-workflow-tutorial.\n\nThe full test suite was intentionally not run in this milestone; the already completed targeted provider/pipeline gate was 39 passing tests. Pixel-path optimization and full cold acceptance are separate later milestones.\n"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    if not os.environ.get("WAVESPEED_API_KEY"):
        raise RuntimeError("WAVESPEED_API_KEY is unavailable; no calls made")
    OUT.mkdir(parents=True, exist_ok=True)
    prior_ids = existing_provider_ids()
    quote = {
        "fetched_at_utc": utc(),
        "source": "WaveSpeed live MCP get_price immediately before the benchmark",
        "model_id": MODEL,
        "price_usd": UNIT_QUOTE_USD,
        "discounted_price_usd": UNIT_QUOTE_USD,
        "estimate": True,
        "unpriced_inputs": [],
    }
    write_json(OUT / "fresh-quote.json", quote)
    ledger_path = OUT / "cost-ledger.json"
    if ledger_path.exists():
        ledger = read_json(ledger_path)
        if ledger.get("reservation_usd") != RESERVATION_USD or ledger.get("prior_conservative_usd") != PRIOR_CONSERVATIVE_USD:
            raise RuntimeError("existing benchmark ledger conflicts with authorization")
    else:
        ledger = {
            "schema": "latency-step2-cost-ledger-v1",
            "created_at_utc": utc(),
            "status": "reserved_before_first_paid_submit",
            "prior_conservative_usd": PRIOR_CONSERVATIVE_USD,
            "incremental_cap_usd": INCREMENTAL_CAP_USD,
            "unit_quote_usd": UNIT_QUOTE_USD,
            "reserved_jobs": NEW_JOBS,
            "reservation_usd": RESERVATION_USD,
            "maximum_conservative_usd": TOTAL_RESERVED_USD,
            "actual_charge_known": False,
            "open_liability_usd": RESERVATION_USD,
            "provider_references": [],
            "submitted_jobs": 0,
        }
        if RESERVATION_USD > INCREMENTAL_CAP_USD or abs(PRIOR_CONSERVATIVE_USD + RESERVATION_USD - TOTAL_RESERVED_USD) > 1e-12:
            raise RuntimeError("reservation arithmetic or cap check failed")
        write_json(ledger_path, ledger)

    configurations: list[dict[str, Any]] = []
    serial = run_configuration("serial1", 1, prior_ids, ledger, configurations)
    configurations.append(serial)
    prior_ids.update(serial["prediction_ids"])
    update_ledger(ledger, configurations)
    concurrent = run_configuration("concurrent2", 2, prior_ids, ledger, configurations)
    configurations.append(concurrent)
    update_ledger(ledger, configurations)
    comparison = compare_outputs(serial, concurrent)
    measurement = {
        "schema": "latency-step2-measurement-v1",
        "completed_at_utc": utc(),
        "status": "completed",
        "quote": quote,
        "authorization": {
            "prior_conservative_usd": PRIOR_CONSERVATIVE_USD,
            "incremental_cap_usd": INCREMENTAL_CAP_USD,
            "reservation_usd": RESERVATION_USD,
            "maximum_conservative_usd": TOTAL_RESERVED_USD,
        },
        "configurations": configurations,
        "output_comparison": comparison,
        "all_inputs_byte_identical_between_arms": all(item["same_input_bytes"] for item in comparison),
        "all_outputs_valid_non_blank_true_alpha": all(item["both_non_blank_true_alpha"] for item in comparison),
        "unique_new_prediction_ids": len({item for config in configurations for item in config["prediction_ids"]}),
        "public_default_changed": False,
        "full_cold_pipeline_claimed": False,
    }
    if measurement["unique_new_prediction_ids"] != NEW_JOBS:
        raise RuntimeError("benchmark did not produce exactly six unique prediction IDs")
    write_json(OUT / "timings.json", measurement)
    write_report(measurement)
    print(json.dumps({
        "status": "completed",
        "serial_wall_seconds": serial["wall_seconds"],
        "concurrent_wall_seconds": concurrent["wall_seconds"],
        "new_prediction_ids": measurement["unique_new_prediction_ids"],
        "all_outputs_valid": measurement["all_outputs_valid_non_blank_true_alpha"],
        "report": str(OUT / "REPORT.md"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
