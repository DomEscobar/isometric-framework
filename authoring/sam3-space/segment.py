# /// script
# requires-python = ">=3.12"
# dependencies = ["gradio_client==2.7.0", "huggingface_hub==1.31.0"]
# ///
"""Submit one mask request; keep provenance and never automatically resubmit."""
import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path

from gradio_client import Client, handle_file
from huggingface_hub import get_token


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--space", required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--text", default="")
    parser.add_argument("--boxes", default="[]", help="Original-pixel [x1,y1,x2,y2,label] boxes JSON")
    parser.add_argument("--confidence", type=float, default=0.5)
    parser.add_argument("--mask-threshold", type=float, default=0.5)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not args.image.is_file():
        parser.error("Input image does not exist.")
    json.loads(args.boxes)
    args.out.mkdir(parents=True, exist_ok=False)
    request = {"space": args.space, "source_sha256": hashlib.sha256(args.image.read_bytes()).hexdigest(),
               "text": args.text, "boxes": json.loads(args.boxes), "confidence": args.confidence,
               "mask_threshold": args.mask_threshold, "state": "prepared"}
    receipt = args.out / "request.json"
    receipt.write_text(json.dumps(request, indent=2), encoding="utf-8")
    started = time.perf_counter()
    client = Client(args.space, token=get_token(), verbose=False, httpx_kwargs={"timeout": 30},
                    download_files=str(args.out / "downloads"))
    request["session_hash"] = client.session_hash
    receipt.write_text(json.dumps(request, indent=2), encoding="utf-8")
    job = client.submit(handle_file(str(args.image)), args.text, args.boxes,
                        args.confidence, args.mask_threshold, api_name="/segment")
    request["state"] = "submitted"
    receipt.write_text(json.dumps(request, indent=2), encoding="utf-8")
    try:
        deadline = time.monotonic() + 300
        last_status = None
        while not job.done():
            # gradio_client 2.7.0 exposes the server ID through its communicator.
            request["event_id"] = job.communicator.event_id if job.communicator else None
            status = str(job.status().code)
            if status != last_status:
                print(status, flush=True)
                last_status = status
            receipt.write_text(json.dumps(request, indent=2), encoding="utf-8")
            if time.monotonic() >= deadline:
                job.cancel()
                request["cancellation_requested"] = True
                raise TimeoutError()
            time.sleep(1)
        _, files, result = job.result(timeout=300)
    except Exception:
        request["state"] = "unresolved"
        receipt.write_text(json.dumps(request, indent=2), encoding="utf-8")
        raise SystemExit("Request unresolved. Inspect the saved event ID and Space status before retrying; this client did not resubmit.") from None
    for file in files:
        path = Path(file)
        shutil.copy2(path, args.out / path.name)
    request.update(state="completed", elapsed_seconds=time.perf_counter() - started,
                   candidates=len(result["candidates"]), request_id=result["request_id"])
    receipt.write_text(json.dumps(request, indent=2), encoding="utf-8")
    print(json.dumps(request, indent=2))


if __name__ == "__main__":
    main()
