# /// script
# requires-python = ">=3.12"
# dependencies = ["huggingface_hub==1.31.0"]
# ///
"""Create a private ZeroGPU Space. Never select paid hardware as a fallback."""
import argparse
import json
from pathlib import Path

from huggingface_hub import HfApi, get_token, get_hf_file_metadata, hf_hub_url
from huggingface_hub.utils import HfHubHTTPError, RepositoryNotFoundError

FILES = ["README.md", "requirements.txt", "app.py", "mask_io.py"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Read-only credential/model preflight")
    parser.add_argument("--update", action="store_true", help="Update this previously created Space")
    parser.add_argument("--name", default="sam3-scene-masks")
    parser.add_argument("--receipt", type=Path, default=Path("test-results/sam3-space/deploy.json"))
    args = parser.parse_args()
    if not args.name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in args.name):
        parser.error("Space name must contain only letters, numbers, hyphens or underscores.")
    token = get_token()
    if not token:
        raise SystemExit("No Hugging Face login. Run: uvx hf auth login. Do not put the token in source or chat.")
    api = HfApi(token=token)
    account = api.whoami()
    repo_id = f"{account['name']}/{args.name}"
    revision = "3c879f39826c281e95690f02c7821c4de09afae7"
    get_hf_file_metadata(hf_hub_url("facebook/sam3", "model.safetensors", revision=revision), token=token)
    receipt = {"account": account["name"], "pro": bool(account.get("isPro")),
               "space": repo_id, "model_access": True, "model_revision": revision,
               "requested_hardware": "zero-a10g", "url": f"https://huggingface.co/spaces/{repo_id}"}
    if not args.check:
        folder = Path(__file__).resolve().parent / "space"
        for name in FILES:
            if not (folder / name).is_file():
                raise SystemExit(f"Missing deployment file: {name}")
        try:
            existing = api.space_info(repo_id)
        except RepositoryNotFoundError:
            existing = None
        if existing:
            if not args.update:
                raise SystemExit("Space already exists. Inspect it before explicitly using --update.")
            if not existing.private:
                raise SystemExit("Refusing to upload the model credential to a public Space.")
            api.request_space_hardware(repo_id, hardware="zero-a10g")
            api.add_space_secret(repo_id, key="HF_TOKEN", value=token)
        else:
            api.create_repo(repo_id, repo_type="space", space_sdk="gradio", private=True,
                            space_hardware="zero-a10g", space_secrets=[{"key": "HF_TOKEN", "value": token}])
        commit = api.upload_folder(repo_id=repo_id, repo_type="space", folder_path=folder,
                                   allow_patterns=FILES, commit_message="Add bounded SAM 3 image mask service")
        receipt["commit"] = commit.oid
        runtime = api.get_space_runtime(repo_id)
        receipt["stage"] = str(runtime.stage)
        receipt["hardware"] = str(runtime.hardware)
        receipt["live_inference"] = "unverified"
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    try:
        main()
    except HfHubHTTPError as error:
        code = error.response.status_code if error.response is not None else "unknown"
        # Do not print request headers, tokens, or raw HTTP diagnostics.
        raise SystemExit(f"Hugging Face rejected the request (HTTP {code}). Check model approval, token permissions and ZeroGPU eligibility. No paid fallback requested.") from None
