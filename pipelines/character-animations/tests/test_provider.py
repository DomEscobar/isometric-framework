from __future__ import annotations

import json
from pathlib import Path

import pytest

import provider


class MockTransport:
    """Offline labelled provider HTTP mock; no network or credits."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def request(self, method, url, headers=None, body=None, timeout=30):
        self.calls.append((method, url, dict(headers or {}), body, timeout))
        if not self.replies:
            raise AssertionError("unexpected HTTP call")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def envelope(data: dict) -> tuple[int, dict[str, str], bytes]:
    return 200, {"content-type": "application/json"}, json.dumps({"data": data}).encode()


def test_upload_uses_authenticated_ticket_then_unauthenticated_put(tmp_path: Path) -> None:
    source = tmp_path / "frame.png"
    source.write_bytes(b"png bytes")
    mock = MockTransport([
        envelope({
            "upload": {"method": "PUT", "url": "https://upload.example/file", "headers": {"x-ticket": "yes"}},
            "download_url": "https://media.example/file.png",
        }),
        (200, {}, b""),
    ])
    client = provider.WaveSpeedProvider("secret", transport=mock)

    uploaded = client.upload(source, "image/png")

    assert uploaded == "https://media.example/file.png"
    assert mock.calls[0][0:2] == ("POST", "https://api.wavespeed.ai/api/v3/media/uploads")
    assert mock.calls[0][2]["Authorization"] == "Bearer secret"
    assert json.loads(mock.calls[0][3])["size"] == len(b"png bytes")
    assert mock.calls[1][0:2] == ("PUT", "https://upload.example/file")
    assert "Authorization" not in mock.calls[1][2]
    assert mock.calls[1][3] == b"png bytes"


def test_submit_is_one_shot_and_ambiguous_response_is_not_retried() -> None:
    mock = MockTransport([TimeoutError("lost response")])
    client = provider.WaveSpeedProvider("secret", transport=mock)

    with pytest.raises(provider.AmbiguousSubmission):
        client.submit("meta/muse-image/edit", {"prompt": "turn", "image_urls": ["https://media.example/a.png"]})

    assert len(mock.calls) == 1
    assert mock.calls[0][0] == "POST"


def test_poll_validates_known_prediction_and_output_urls() -> None:
    mock = MockTransport([envelope({"id": "job_123", "status": "completed", "outputs": ["https://output.example/a.png"]})])
    client = provider.WaveSpeedProvider("secret", transport=mock)

    result = client.poll("job_123")

    assert result == {"id": "job_123", "status": "completed", "outputs": ["https://output.example/a.png"]}
    assert mock.calls[0][0] == "GET"


def test_poll_honors_retry_after_once_for_known_id(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = MockTransport([
        (429, {"Retry-After": "2"}, b'{"message":"rate limited"}'),
        envelope({"id": "job_123", "status": "pending", "outputs": []}),
    ])
    sleeps = []
    monkeypatch.setattr(provider.time, "sleep", sleeps.append)
    client = provider.WaveSpeedProvider("secret", transport=mock)

    result = client.poll("job_123")

    assert result["status"] == "pending"
    assert sleeps == [2.0]
    assert [call[0] for call in mock.calls] == ["GET", "GET"]


def test_submit_429_is_not_retried() -> None:
    mock = MockTransport([(429, {"Retry-After": "2"}, b'{"message":"rate limited"}')])
    client = provider.WaveSpeedProvider("secret", transport=mock)

    with pytest.raises(provider.ProviderError, match="429"):
        client.submit("meta/muse-image/edit", {"prompt": "turn", "image_urls": ["https://media.example/a.png"]})

    assert len(mock.calls) == 1


def test_recorded_quotes_are_estimates_and_unsupported_quote_is_rejected() -> None:
    quote = provider.recorded_quote("wavespeed-ai/image-background-remover", units=3)
    assert quote == {"model": "wavespeed-ai/image-background-remover", "units": 3, "quoted_usd": 0.012, "estimate": True, "actual_charge_usd": None, "actual_charge_known": False}
    with pytest.raises(ValueError, match="recorded quote"):
        provider.recorded_quote("unknown/model")


def test_preset_registry_validates_capability_and_builds_recorded_schema() -> None:
    preset = provider.get_preset("waldlicht-facing-v1", "image_edit")
    payload = preset.build_payload(
        {"prompt": "rotate the accepted keeper", "aspect_ratio": "1:1", "output_format": "png"},
        ["https://media.example/reference.png"],
    )

    assert preset.provider == "wavespeed"
    assert preset.model == "meta/muse-image/edit"
    assert payload == {
        "prompt": "rotate the accepted keeper",
        "image_urls": ["https://media.example/reference.png"],
        "aspect_ratio": "1:1",
        "output_format": "png",
    }
    with pytest.raises(ValueError, match="capability"):
        provider.get_preset("waldlicht-facing-v1", "image_to_video")
    with pytest.raises(ValueError, match="unknown preset"):
        provider.get_preset("client/model", "image_edit")


def test_adapter_registry_supports_explicit_alternate_fixture() -> None:
    registry = provider.AdapterRegistry()
    fixture = provider.FixtureAdapter()
    registry.register("fixture", fixture)

    assert registry.get("fixture") is fixture
    assert fixture.submit("fixture/model", {"prompt": "offline"}) == {
        "id": "fixture_prediction",
        "status": "completed",
        "outputs": [],
        "fixture": True,
    }


def test_gemini_omni_video_3s_preset_builds_exact_supported_request() -> None:
    preset = provider.get_preset("gemini-omni-video-3s-v1", "image_to_video")

    payload = preset.build_payload(
        {
            "prompt": "same SE character walking in place",
            "duration": 3,
            "resolution": "360p",
            "aspect_ratio": "16:9",
        },
        ["https://media.example/reference.png"],
    )

    assert preset.model == "google/gemini-omni-1.1-flash/image-to-video"
    assert payload == {
        "image": "https://media.example/reference.png",
        "prompt": "same SE character walking in place",
        "duration": 3,
        "resolution": "360p",
        "aspect_ratio": "16:9",
    }
    description = preset.describe()
    assert description["defaults"] == {"duration": 3, "resolution": "360p", "aspect_ratio": "16:9"}
    assert description["quote"]["quoted_usd"] == 0.09


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"duration": 2}, "duration"),
        ({"duration": 4}, "3-second"),
        ({"resolution": "480p"}, "resolution"),
        ({"aspect_ratio": "1:1"}, "aspect_ratio"),
        ({"seed": -1}, "unsupported Gemini"),
        ({"negative_prompt": "orbit"}, "unsupported Gemini"),
    ],
)
def test_gemini_omni_video_3s_preset_rejects_invalid_or_wan_only_fields(override, message) -> None:
    options = {
        "prompt": "walk in place",
        "duration": 3,
        "resolution": "360p",
        "aspect_ratio": "16:9",
        **override,
    }
    preset = provider.get_preset("gemini-omni-video-3s-v1", "image_to_video")
    with pytest.raises(ValueError, match=message):
        preset.build_payload(options, ["https://media.example/reference.png"])


def test_minimax_h3_video_preset_uses_same_full_resolution_first_and_last_image() -> None:
    preset = provider.get_preset("minimax-h3-ne-source-5s-768p-v1", "image_to_video")
    payload = preset.build_payload(
        {"prompt": "fixed-camera NE walk in place", "duration": 5, "resolution": "768p"},
        ["https://media.example/approved-ne.png"],
    )

    assert preset.model == "wavespeed-ai/minimax-h3/image-to-video"
    assert payload == {
        "prompt": "fixed-camera NE walk in place",
        "image": "https://media.example/approved-ne.png",
        "last_image": "https://media.example/approved-ne.png",
        "duration": 5,
        "resolution": "768p",
    }
    assert preset.describe()["quote"]["quoted_usd"] == 0.20


@pytest.mark.parametrize("duration", [3, 5, 8, 10])
@pytest.mark.parametrize("resolution", ["480p", "768p"])
def test_minimax_h3_action_preset_builds_each_supported_source_option(duration, resolution) -> None:
    preset = provider.get_preset("minimax-h3-action-3s-480p-v1", "image_to_video")
    payload = preset.build_payload(
        {"prompt": "one in-place punch", "duration": duration, "resolution": resolution, "seed": 7},
        ["https://media.example/approved-ne.png"],
    )
    assert payload == {
        "prompt": "one in-place punch", "image": "https://media.example/approved-ne.png",
        "last_image": "https://media.example/approved-ne.png", "duration": duration,
        "resolution": resolution, "seed": 7,
    }
    quote = preset.quote({"duration": duration, "resolution": resolution})
    assert quote["priced_inputs"] == {"duration": duration, "resolution": resolution}
    assert quote["quoted_usd"] == pytest.approx(duration * (0.02 if resolution == "480p" else 0.04))


def test_minimax_h3_action_preset_uses_confirmed_source_defaults() -> None:
    preset = provider.get_preset("minimax-h3-action-3s-480p-v1", "image_to_video")
    payload = preset.build_payload(
        {"prompt": "one in-place punch"}, ["https://media.example/approved-ne.png"]
    )
    assert payload["duration"] == 3
    assert payload["resolution"] == "480p"
    assert preset.describe()["parameter_options"] == {
        "duration": [3, 5, 8, 10], "resolution": ["480p", "768p"]
    }


@pytest.mark.parametrize("override", [
    {"duration": 0}, {"duration": 4}, {"duration": "3"},
    {"resolution": "760p"}, {"resolution": "720p"},
])
def test_minimax_h3_action_preset_strictly_rejects_unsupported_source_options(override) -> None:
    preset = provider.get_preset("minimax-h3-action-3s-480p-v1", "image_to_video")
    with pytest.raises(ValueError):
        preset.build_payload(
            {"prompt": "one in-place punch", **override},
            ["https://media.example/approved-ne.png"],
        )


@pytest.mark.parametrize("override", [{"duration": 4}, {"resolution": "1080p"}, {"aspect_ratio": "1:1"}, {"seed": 1.5}])
def test_minimax_h3_video_preset_rejects_unquoted_or_invalid_fields(override) -> None:
    preset = provider.get_preset("minimax-h3-ne-source-5s-768p-v1", "image_to_video")
    with pytest.raises(ValueError):
        preset.build_payload(
            {"prompt": "walk in place", "duration": 5, "resolution": "768p", **override},
            ["https://media.example/approved-ne.png"],
        )
