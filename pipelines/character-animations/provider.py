"""Typed provider adapters for the animation pipeline.

Only server-configured presets are exposed. Client inputs never contain provider
endpoints or media URLs; job-owned files are uploaded through an authenticated
provider ticket before their server-supplied URLs enter a request.
"""

from __future__ import annotations

import json
import mimetypes
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

API_ROOT = "https://api.wavespeed.ai/api/v3"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


class ProviderError(RuntimeError):
    """A definite provider or protocol failure."""


class AmbiguousSubmission(RuntimeError):
    """A one-shot submit may have reached the provider but returned no safe ID."""


class UrllibTransport:
    def request(self, method: str, url: str, headers: dict[str, str] | None = None, body: bytes | None = None, timeout: int = 30) -> tuple[int, dict[str, str], bytes]:
        request = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, dict(response.headers.items()), response.read()
        except urllib.error.HTTPError as error:
            return error.code, dict(error.headers.items()), error.read()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _https_url(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or len(value) > 4096:
        raise ProviderError(f"invalid {label}")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ProviderError(f"invalid {label}")
    return value


def _envelope(response: tuple[int, dict[str, str], bytes]) -> dict[str, Any]:
    status, _headers, body = response
    if status < 200 or status >= 300:
        raise ProviderError(f"provider HTTP {status}")
    try:
        decoded = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProviderError("provider returned invalid JSON") from error
    if not isinstance(decoded, dict) or not isinstance(decoded.get("data"), dict):
        raise ProviderError("provider response envelope is invalid")
    return decoded["data"]


class WaveSpeedProvider:
    name = "wavespeed"

    def __init__(self, api_key: str, *, transport: Any | None = None) -> None:
        if not isinstance(api_key, str) or not api_key:
            raise ValueError("WaveSpeed API key is required")
        self._api_key = api_key
        self._transport = transport or UrllibTransport()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

    def _known_get(self, url: str, *, headers: dict[str, str], timeout: int) -> tuple[int, dict[str, str], bytes]:
        """Retry one idempotent GET on 429; prediction POSTs stay one-shot."""
        response = self._transport.request("GET", url, headers=headers, timeout=timeout)
        if response[0] != 429:
            return response
        retry_value = next((value for key, value in response[1].items() if key.lower() == "retry-after"), None)
        try:
            retry_after = float(retry_value)
        except (TypeError, ValueError) as error:
            raise ProviderError("provider HTTP 429 without valid Retry-After") from error
        if not 0 <= retry_after <= 60:
            raise ProviderError("provider HTTP 429 Retry-After is outside the bounded wait")
        time.sleep(retry_after)
        return self._transport.request("GET", url, headers=headers, timeout=timeout)

    def upload(self, path: Path, content_type: str | None = None) -> str:
        source = Path(path)
        if not source.is_file() or source.is_symlink():
            raise ValueError("upload source must be a regular file")
        media_type = content_type or mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        ticket = _envelope(self._transport.request(
            "POST",
            f"{API_ROOT}/media/uploads",
            headers=self._headers(),
            body=_json_bytes({"filename": source.name, "content_type": media_type, "size": source.stat().st_size}),
        ))
        upload = ticket.get("upload")
        if not isinstance(upload, dict) or upload.get("method") != "PUT" or not isinstance(upload.get("headers", {}), dict):
            raise ProviderError("provider upload ticket is invalid")
        upload_url = _https_url(upload.get("url"), label="upload ticket URL")
        download_url = _https_url(ticket.get("download_url"), label="uploaded media URL")
        status, _headers, _body = self._transport.request("PUT", upload_url, headers=upload.get("headers", {}), body=source.read_bytes())
        if status < 200 or status >= 300:
            raise ProviderError(f"provider upload HTTP {status}")
        return download_url

    def submit(self, model: str, payload: dict[str, Any]) -> dict[str, Any]:
        if model not in MODEL_SCHEMAS:
            raise ValueError("unsupported configured model")
        try:
            data = _envelope(self._transport.request(
                "POST", f"{API_ROOT}/{model}", headers=self._headers(), body=_json_bytes(payload), timeout=60
            ))
        except (TimeoutError, ConnectionError, OSError) as error:
            # POST is deliberately never retried when no definite HTTP response exists.
            raise AmbiguousSubmission("provider submission outcome is unknown") from error
        prediction_id = data.get("id")
        if not isinstance(prediction_id, str) or not _ID.fullmatch(prediction_id):
            raise AmbiguousSubmission("provider accepted response without a safe prediction ID")
        result = dict(data)
        result["id"] = prediction_id
        return result

    def poll(self, prediction_id: str) -> dict[str, Any]:
        if not isinstance(prediction_id, str) or not _ID.fullmatch(prediction_id):
            raise ValueError("invalid prediction ID")
        data = _envelope(self._known_get(
            f"{API_ROOT}/predictions/{prediction_id}/result", headers=self._headers(), timeout=30
        ))
        if data.get("id") != prediction_id:
            raise ProviderError("prediction ID mismatch")
        outputs = data.get("outputs", [])
        if not isinstance(outputs, list):
            raise ProviderError("prediction outputs are invalid")
        data["outputs"] = [_https_url(item, label="provider output URL") for item in outputs]
        return data

    def download(self, url: str, target: Path, *, maximum_bytes: int = 100 * 1024 * 1024) -> None:
        output_url = _https_url(url, label="provider output URL")
        status, _headers, body = self._known_get(output_url, headers={}, timeout=120)
        if status < 200 or status >= 300:
            raise ProviderError(f"provider output HTTP {status}")
        if not body or len(body) > maximum_bytes:
            raise ProviderError("provider output size is invalid")
        target.write_bytes(body)


MODEL_SCHEMAS: dict[str, dict[str, Any]] = {
    "meta/muse-image/edit": {
        "capability": "image_edit",
        "required": ["prompt", "image_urls"],
        "revision": "waldlicht-recorded-2026-09",
        "source": "waldlicht/art/character-motion/ne-facing-01/schema-01.json",
    },
    "wavespeed-ai/wan-2.2/i2v-720p-ultra-fast": {
        "capability": "image_to_video",
        "required": ["prompt", "image"],
        "revision": "waldlicht-recorded-2026-09",
        "source": "waldlicht/art/character-motion/ne-video-01/schema.json",
    },
    "google/gemini-omni-1.1-flash/image-to-video": {
        "capability": "image_to_video",
        "required": ["image", "prompt"],
        "optional": ["last_image", "aspect_ratio", "duration", "resolution"],
        "properties": {
            "aspect_ratio": {"enum": ["16:9", "9:16"]},
            "duration": {"type": "integer", "minimum": 3, "maximum": 10},
            "resolution": {"enum": ["360p", "720p", "1080p", "4k"]},
        },
        "revision": "wavespeed-live-2026-09-20",
        "source": "artifacts/gemini-omni-video-3s-01/schema.json",
    },
    "wavespeed-ai/minimax-h3/image-to-video": {
        "capability": "image_to_video",
        "required": ["prompt", "image"],
        "optional": ["last_image", "duration", "resolution", "seed"],
        "properties": {
            "duration": {"type": "integer", "minimum": 3, "maximum": 15, "default": 5},
            "resolution": {"enum": ["480p", "540p", "768p", "1080p"], "default": "480p"},
            "seed": {"type": "integer"},
        },
        "revision": "wavespeed-live-2026-09-21",
        "source": "artifacts/minimax-ne-source-01/schema.json",
    },
    "wavespeed-ai/image-background-remover": {
        "capability": "background_removal",
        "required": ["image"],
        "revision": "waldlicht-recorded-2026-09",
        "source": "waldlicht/art/character-motion/se-cutout-01/schema.json",
    },
}

_RECORDED_UNIT_QUOTES = {
    "meta/muse-image/edit": 0.011,
    "wavespeed-ai/wan-2.2/i2v-720p-ultra-fast": 0.10,
    "wavespeed-ai/image-background-remover": 0.004,
    "google/gemini-omni-1.1-flash/image-to-video": 0.09,
    "wavespeed-ai/minimax-h3/image-to-video": 0.20,
}


def recorded_quote(model: str, *, units: int = 1, options: dict[str, Any] | None = None) -> dict[str, Any]:
    if model not in _RECORDED_UNIT_QUOTES or type(units) is not int or units < 1:
        raise ValueError("no supported recorded quote")
    priced_inputs: dict[str, Any] = {}
    unit_quote = _RECORDED_UNIT_QUOTES[model]
    if model == "wavespeed-ai/minimax-h3/image-to-video" and options is not None:
        duration = options.get("duration")
        resolution = options.get("resolution")
        if type(duration) is not int or duration not in {3, 5, 8, 10}:
            raise ValueError("MiniMax quote requires duration 3, 5, 8, or 10")
        if resolution not in {"480p", "768p"}:
            raise ValueError("MiniMax quote requires resolution 480p or 768p")
        unit_quote = duration * (0.02 if resolution == "480p" else 0.04)
        priced_inputs = {"duration": duration, "resolution": resolution}
    quoted = round(unit_quote * units, 6)
    quote = {
        "model": model, "units": units, "quoted_usd": quoted, "estimate": True,
        "actual_charge_usd": None, "actual_charge_known": False,
    }
    if priced_inputs:
        quote["priced_inputs"] = priced_inputs
    return quote


@dataclass(frozen=True)
class Preset:
    name: str
    provider: str
    model: str
    capability: str
    revision: str
    builder: Callable[[dict[str, Any], list[str]], dict[str, Any]]
    defaults: dict[str, Any]
    parameter_options: dict[str, list[Any]] | None = None

    def build_payload(self, options: dict[str, Any], uploaded_urls: list[str]) -> dict[str, Any]:
        return self.builder(options, uploaded_urls)

    def quote(self, options: dict[str, Any] | None = None) -> dict[str, Any]:
        effective = {key: value for key, value in self.defaults.items() if key != "first_equals_last"}
        if options:
            effective.update(options)
        return recorded_quote(self.model, options=effective)

    def describe(self) -> dict[str, Any]:
        description = {
            "name": self.name,
            "provider": self.provider,
            "model": self.model,
            "capability": self.capability,
            "revision": self.revision,
            "recorded_schema": MODEL_SCHEMAS[self.model],
            "quote": self.quote(),
            "defaults": self.defaults,
            "parameter_options": self.parameter_options or {},
        }
        if self.parameter_options:
            description["option_quotes"] = [
                self.quote({"duration": duration, "resolution": resolution})
                for duration in self.parameter_options.get("duration", [])
                for resolution in self.parameter_options.get("resolution", [])
            ]
        return description


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 12000:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _facing_payload(options: dict[str, Any], urls: list[str]) -> dict[str, Any]:
    if len(urls) != 1:
        raise ValueError("facing preset requires exactly one uploaded image")
    allowed = {"prompt", "aspect_ratio", "output_format"}
    if not set(options) <= allowed:
        raise ValueError("unsupported facing parameter")
    aspect = options.get("aspect_ratio", "1:1")
    output_format = options.get("output_format", "png")
    if aspect not in {"21:9", "16:9", "4:3", "3:2", "1:1", "2:3", "3:4", "9:16", "9:21"}:
        raise ValueError("unsupported aspect_ratio")
    if output_format not in {"webp", "png", "jpeg"}:
        raise ValueError("unsupported output_format")
    return {"prompt": _nonempty(options.get("prompt"), "prompt"), "image_urls": urls, "aspect_ratio": aspect, "output_format": output_format}


def _video_payload(options: dict[str, Any], urls: list[str]) -> dict[str, Any]:
    if len(urls) != 1:
        raise ValueError("video preset requires exactly one uploaded image")
    allowed = {"prompt", "negative_prompt", "duration", "seed"}
    if not set(options) <= allowed:
        raise ValueError("unsupported video parameter")
    duration = options.get("duration", 5)
    if duration != 5:
        raise ValueError("only quoted 5-second video jobs are supported")
    seed = options.get("seed", -1)
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    payload = {"prompt": _nonempty(options.get("prompt"), "prompt"), "image": urls[0], "duration": duration, "seed": seed}
    if "negative_prompt" in options:
        payload["negative_prompt"] = _nonempty(options["negative_prompt"], "negative_prompt")
    return payload


def _gemini_omni_video_payload(options: dict[str, Any], urls: list[str]) -> dict[str, Any]:
    if len(urls) != 1:
        raise ValueError("Gemini video preset requires exactly one uploaded image")
    allowed = {"prompt", "duration", "resolution", "aspect_ratio"}
    if not set(options) <= allowed:
        raise ValueError("unsupported Gemini video parameter")
    duration = options.get("duration", 3)
    if type(duration) is not int or not 3 <= duration <= 10:
        raise ValueError("duration must be an integer between 3 and 10")
    if duration != 3:
        raise ValueError("this preset supports only the quoted 3-second operation")
    resolution = options.get("resolution", "360p")
    if resolution not in {"360p", "720p", "1080p", "4k"}:
        raise ValueError("unsupported resolution")
    if resolution != "360p":
        raise ValueError("this preset supports only the quoted 360p operation")
    aspect_ratio = options.get("aspect_ratio", "16:9")
    if aspect_ratio not in {"16:9", "9:16"}:
        raise ValueError("unsupported aspect_ratio")
    if aspect_ratio != "16:9":
        raise ValueError("this preset supports only the quoted 16:9 operation")
    return {
        "image": urls[0],
        "prompt": _nonempty(options.get("prompt"), "prompt"),
        "duration": duration,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
    }


def _removal_payload(options: dict[str, Any], urls: list[str]) -> dict[str, Any]:
    if options or len(urls) != 1:
        raise ValueError("removal preset accepts exactly one uploaded image and no model options")
    return {"image": urls[0]}


def _minimax_h3_video_payload(options: dict[str, Any], urls: list[str]) -> dict[str, Any]:
    if len(urls) != 1:
        raise ValueError("MiniMax H3 video preset requires exactly one uploaded image")
    allowed = {"prompt", "duration", "resolution", "seed"}
    if not set(options) <= allowed:
        raise ValueError("unsupported MiniMax H3 video parameter")
    duration = options.get("duration", 5)
    if duration != 5:
        raise ValueError("this preset supports only the quoted 5-second operation")
    resolution = options.get("resolution", "768p")
    if resolution != "768p":
        raise ValueError("this preset supports only the quoted 768p operation")
    payload = {
        "prompt": _nonempty(options.get("prompt"), "prompt"),
        "image": urls[0],
        "last_image": urls[0],
        "duration": duration,
        "resolution": resolution,
    }
    if "seed" in options:
        if type(options["seed"]) is not int:
            raise ValueError("seed must be an integer")
        payload["seed"] = options["seed"]
    return payload


def _minimax_h3_480p_3s_payload(options: dict[str, Any], urls: list[str]) -> dict[str, Any]:
    if len(urls) != 1:
        raise ValueError("MiniMax H3 video preset requires exactly one uploaded image")
    allowed = {"prompt", "duration", "resolution", "seed"}
    if not set(options) <= allowed:
        raise ValueError("unsupported MiniMax H3 video parameter")
    duration = options.get("duration", 3)
    if type(duration) is not int or duration not in {3, 5, 8, 10}:
        raise ValueError("duration must be one of 3, 5, 8, or 10")
    resolution = options.get("resolution", "480p")
    if resolution not in {"480p", "768p"}:
        raise ValueError("resolution must be 480p or 768p")
    payload = {
        "prompt": _nonempty(options.get("prompt"), "prompt"),
        "image": urls[0],
        "last_image": urls[0],
        "duration": duration,
        "resolution": resolution,
    }
    if "seed" in options:
        if type(options["seed"]) is not int:
            raise ValueError("seed must be an integer")
        payload["seed"] = options["seed"]
    return payload


PRESETS: dict[str, Preset] = {
    "waldlicht-facing-v1": Preset("waldlicht-facing-v1", "wavespeed", "meta/muse-image/edit", "image_edit", "1", _facing_payload, {"aspect_ratio": "1:1", "output_format": "png"}),
    "waldlicht-video-v1": Preset("waldlicht-video-v1", "wavespeed", "wavespeed-ai/wan-2.2/i2v-720p-ultra-fast", "image_to_video", "1", _video_payload, {"duration": 5, "seed": -1}),
    "gemini-omni-video-3s-v1": Preset("gemini-omni-video-3s-v1", "wavespeed", "google/gemini-omni-1.1-flash/image-to-video", "image_to_video", "1", _gemini_omni_video_payload, {"duration": 3, "resolution": "360p", "aspect_ratio": "16:9"}),
    "minimax-h3-ne-source-5s-768p-v1": Preset("minimax-h3-ne-source-5s-768p-v1", "wavespeed", "wavespeed-ai/minimax-h3/image-to-video", "image_to_video", "1", _minimax_h3_video_payload, {"duration": 5, "resolution": "768p", "first_equals_last": True}),
    "minimax-h3-action-3s-480p-v1": Preset(
        "minimax-h3-action-3s-480p-v1", "wavespeed", "wavespeed-ai/minimax-h3/image-to-video",
        "image_to_video", "2", _minimax_h3_480p_3s_payload,
        {"duration": 3, "resolution": "480p", "first_equals_last": True},
        {"duration": [3, 5, 8, 10], "resolution": ["480p", "768p"]},
    ),
    "waldlicht-removal-v1": Preset("waldlicht-removal-v1", "wavespeed", "wavespeed-ai/image-background-remover", "background_removal", "1", _removal_payload, {}),
}


def get_preset(name: str, capability: str) -> Preset:
    preset = PRESETS.get(name)
    if preset is None:
        raise ValueError("unknown preset")
    if preset.capability != capability:
        raise ValueError("preset capability mismatch")
    return preset


def available_presets() -> list[dict[str, Any]]:
    return [PRESETS[name].describe() for name in sorted(PRESETS)]


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, Any] = {}

    def register(self, name: str, adapter: Any) -> None:
        if not isinstance(name, str) or not _ID.fullmatch(name) or name in self._adapters:
            raise ValueError("invalid or duplicate adapter name")
        self._adapters[name] = adapter

    def get(self, name: str) -> Any:
        try:
            return self._adapters[name]
        except KeyError as error:
            raise ValueError("provider adapter is not configured") from error


class FixtureAdapter:
    """Explicit offline alternate adapter fixture; never presented as live."""

    name = "fixture"

    def submit(self, model: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"id": "fixture_prediction", "status": "completed", "outputs": [], "fixture": True}
