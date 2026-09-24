#!/usr/bin/env python3
"""Probe free authoritative OpenRouter reconciliation APIs without exposing keys."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.live_e2e_trace import get_json, load_openrouter_key


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    key, credential = load_openrouter_key()
    status, response = get_json(f"https://openrouter.ai/api/v1/activity?date={args.date}", key=key)
    data = response.get("data")
    error = response.get("error") if isinstance(response.get("error"), dict) else {}
    result = {
        "endpoint": "GET https://openrouter.ai/api/v1/activity",
        "date": args.date,
        "http_status": status,
        "credential": credential,
        "authoritative_activity_available": status == 200 and isinstance(data, list),
        "rows": data if status == 200 and isinstance(data, list) else None,
        "error": {"code": error.get("code"), "message": error.get("message")},
        "limitation": "Activity is daily aggregate data and cannot alone attribute a historical request to an exact time or recover a missing generation ID.",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if status == 200 else 2


if __name__ == "__main__":
    raise SystemExit(main())
