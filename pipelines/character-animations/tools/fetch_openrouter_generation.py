#!/usr/bin/env python3
"""Fetch authoritative OpenRouter generation metadata/content without prompts."""

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
    parser.add_argument("generation_id")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.generation_id.startswith("gen-") or len(args.generation_id) > 200:
        raise SystemExit("invalid generation ID")
    key, credential = load_openrouter_key()
    metadata_status, metadata = get_json(
        f"https://openrouter.ai/api/v1/generation?id={args.generation_id}", key=key,
    )
    content_status, content = get_json(
        f"https://openrouter.ai/api/v1/generation/content?id={args.generation_id}", key=key,
    )
    metadata_data = metadata.get("data") if isinstance(metadata.get("data"), dict) else {}
    content_data = content.get("data") if isinstance(content.get("data"), dict) else {}
    output_data = content_data.get("output") if isinstance(content_data.get("output"), dict) else {}
    result = {
        "generation_id": args.generation_id,
        "credential": credential,
        "metadata_http_status": metadata_status,
        "content_http_status": content_status,
        "metadata": {
            key: metadata_data.get(key)
            for key in ("id", "request_id", "created_at", "model", "provider_name", "finish_reason", "tokens_prompt", "tokens_completion", "total_cost", "usage")
        },
        "completion": output_data.get("completion") if isinstance(output_data.get("completion"), str) else None,
        "stored_error": content_data.get("error"),
        "prompt_or_media_stored": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "metadata_http_status": metadata_status, "content_http_status": content_status}, indent=2))
    return 0 if metadata_status == 200 and content_status == 200 else 2


if __name__ == "__main__":
    raise SystemExit(main())
