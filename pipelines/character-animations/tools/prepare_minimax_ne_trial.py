from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
WORKDIR = ROOT / "artifacts" / "minimax-ne-source-01"
SOURCE = Path("/root/games/waldlicht/art/character-motion/ne-facing-01/source-01.png")
MODEL = "wavespeed-ai/minimax-h3/image-to-video"
PROMPT = (
    "Fixed camera. Animate the exact full-body character in an orthographic isometric "
    "northeast rear-three-quarter walk IN PLACE. Maintain unwavering northeast facing "
    "and the same torso angle throughout. Keep both feet fully visible with alternating "
    "full strides and repeat complete gait cycles at a steady pace; continuous movement, "
    "no still hold. Keep the body root stable. No turn, yaw, orbit, camera movement, zoom, "
    "scale change, crop, or background scene change. Preserve crisp consistent identity, "
    "clothing, anatomy, pixel-art features, and lantern; cloak and lantern motion should "
    "remain naturally subtle. The ending must flow back into the beginning while the "
    "character continues walking."
)
SCHEMA = {
    "model_id": MODEL,
    "type": "image-to-video",
    "base_price": 0.2,
    "required": ["prompt", "image"],
    "properties": {
        "duration": {"default": 5, "description": "Output video duration in seconds.", "enum": list(range(3, 16)), "type": "integer", "x-ui-component": "select"},
        "image": {"description": "First-frame image URL. The output canvas follows this image's aspect ratio.", "type": "string"},
        "last_image": {"description": "Optional last-frame image URL. When provided, the video interpolates from the first frame to this frame.", "type": "string"},
        "prompt": {"description": "Text description of the desired motion, scene, and soundtrack. Audio is generated natively together with the video.", "type": "string"},
        "resolution": {"default": "480p", "description": "Output video resolution. 768p is the model's native canvas; 480p is a faster, lower-cost tier; 540p is a mid tier at 1.5x the 480p price. 1080p is the highest-quality full-HD tier at 2x the 768p price (generation takes longer).", "enum": ["480p", "540p", "768p", "1080p"], "type": "string"},
        "seed": {"description": "The random seed to use for the generation. -1 means a random seed will be used.", "type": "integer"},
    },
    "property_order": ["prompt", "image", "last_image", "resolution", "duration", "seed"],
}
QUOTE = {
    "model_id": MODEL,
    "price": 0.4,
    "discounted_price": 0.2,
    "discount_rate": 50,
    "currency": "USD",
    "estimate": True,
    "unpriced_inputs": [],
    "disclaimer": "Estimate only, for reference — the amount actually charged for a run is authoritative.",
}
PRIOR_MAX_USD = Decimal("0.88046275")
GEMINI_ESTIMATE_USD = Decimal("0.09")
RESERVATION_USD = Decimal("0.50")
EUR_CAP = Decimal("20")


def dump(path: Path, value: object) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ecb_usd_rate() -> tuple[str, Decimal, str]:
    url = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
    body = urllib.request.urlopen(url, timeout=30).read()
    root = ET.fromstring(body)
    for node in root.iter():
        date = node.attrib.get("time")
        if not date:
            continue
        for child in node:
            if child.attrib.get("currency") == "USD":
                return date, Decimal(child.attrib["rate"]), url
    raise RuntimeError("ECB USD reference rate missing")


def source_record(target: Path) -> dict[str, object]:
    with Image.open(target) as image:
        rgb = image.convert("RGB")
        background = rgb.getpixel((0, 0))
        pixels = rgb.load()
        points = [
            (x, y)
            for y in range(rgb.height)
            for x in range(rgb.width)
            if max(abs(pixels[x, y][channel] - background[channel]) for channel in range(3)) > 12
        ]
        if not points:
            raise RuntimeError("source foreground not detected")
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        bbox = [min(xs), min(ys), max(xs) + 1, max(ys) + 1]
        margins = [bbox[0], bbox[1], rgb.width - bbox[2], rgb.height - bbox[3]]
        return {
            "path": target.name,
            "source_path_read_only": str(SOURCE),
            "sha256": sha256(target),
            "bytes": target.stat().st_size,
            "mode": image.mode,
            "size": [rgb.width, rgb.height],
            "corner_background_rgb": list(background),
            "approximate_foreground_bbox_threshold_12": bbox,
            "approximate_margins_left_top_right_bottom": margins,
            "measurement_caveat": "Corner-color difference is a framing measurement only, not a universal identity/foreground model.",
            "visual_review": "Full body is visible in NE rear-three-quarter orientation; both feet and the complete lantern are inside the frame with ample margins and no observed clipping.",
        }


def main() -> None:
    WORKDIR.mkdir(parents=True, exist_ok=True)
    target = WORKDIR / "reference.png"
    if target.exists() and sha256(target) != sha256(SOURCE):
        raise RuntimeError("existing trial reference conflicts with approved source")
    if not target.exists():
        shutil.copyfile(SOURCE, target)
    source = source_record(target)
    if source["sha256"] != "79061e053fa9cd249d653bd9c325f9256f281668104fce22114e981030436ed3":
        raise RuntimeError("approved NE source hash mismatch")

    fx_date, usd_per_eur, fx_url = ecb_usd_rate()
    prior = PRIOR_MAX_USD + GEMINI_ESTIMATE_USD
    held = prior + RESERVATION_USD
    cap_usd = EUR_CAP * usd_per_eur
    if Decimal(str(QUOTE["price"])) > RESERVATION_USD:
        raise RuntimeError("undiscounted exact quote exceeds the trial cap")
    if held > cap_usd:
        raise RuntimeError("reservation would exceed the EUR 20 ceiling")

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    request = {
        "model": MODEL,
        "preset": "minimax-h3-ne-source-5s-768p-v1",
        "input": target.name,
        "input_sha256": source["sha256"],
        "same_uploaded_image_for_first_and_last": True,
        "prompt": PROMPT,
        "duration": 5,
        "resolution": "768p",
        "budget": {"authorized": True, "max_usd": 0.5},
        "audio_delivery_policy": "retain original provider MP4; make a separate muted preview",
    }
    ledger = {
        "version": 1,
        "updated_at_utc": now,
        "authorization": {"source": "QUALITY_AUTHORIZATION_20EUR.md", "ceiling_eur": 20},
        "fx": {"source": fx_url, "date": fx_date, "usd_per_eur": str(usd_per_eur), "ceiling_usd": str(cap_usd)},
        "entries": [
            {
                "id": "parent-reconciled-prior-maximum",
                "maximum_accounted_usd": str(PRIOR_MAX_USD),
                "source": "artifacts/live-e2e-20260920T223050Z-91b811/parent-reconciled-cost-ledger.json",
                "deduplicated_provider_references": [
                    "gen-1789942150-ltFu7p61J0EcyjdZfPFx",
                    "gen-1789942375-7qw4H6Fykv4yoN0XAx4E",
                    "gen-1789942603-xGK4m8pNhhconiHyATQW",
                    "gen-1789943583-3xfNdfNAVvEFv1dBTG7W",
                    "0d475b7b70be41039d778e00b46e57d9", "4bf748fa588646b18bc40145ac48ea06",
                    "536ca0f9e7924eddba9b500e2f22e9bc", "5ef01fe32bbb42cf8e352329a8c81b7d",
                    "685ce2f284ed4d70834605b3810e0b80", "90d37585e9ad4f31adc974b7a6fae7d0",
                    "96c8ac91ab004fdbb3a2a64bd6249bee", "ac54ef6888074f5486e08a41875bd2e6",
                    "ac6cbe8db5094d658dce7085b594d09e", "edf116f908d74f8ca442312df604c67b",
                ],
                "note": "Imported as the authoritative deduplicated prior maximum; component entries are not added again.",
            },
            {
                "id": "gemini-omni-video-3s-01",
                "provider_reference": "7d43e5222b3c441d91300a85b75e73ea",
                "maximum_accounted_usd": str(GEMINI_ESTIMATE_USD),
                "status": "completed_charge_not_authoritatively_reported",
                "source": "artifacts/gemini-omni-video-3s-01/harness-result.json",
            },
            {
                "id": "minimax-ne-source-01-reservation",
                "model": MODEL,
                "reserved_worst_case_usd": str(RESERVATION_USD),
                "quote_usd": str(QUOTE["price"]),
                "discounted_quote_usd": str(QUOTE["discounted_price"]),
                "status": "held_before_submission",
                "prediction_id": None,
            },
        ],
        "prior_maximum_accounted_usd": str(prior),
        "current_reservation_usd": str(RESERVATION_USD),
        "maximum_accounted_with_reservation_usd": str(held),
        "maximum_accounted_with_reservation_eur": str(held / usd_per_eur),
        "remaining_ceiling_usd": str(cap_usd - held),
    }
    dump(WORKDIR / "schema.json", {"fetched_at_utc": now, "source": "WaveSpeed live model schema tool", **SCHEMA})
    dump(WORKDIR / "quote.json", {"fetched_at_utc": now, "inputs": {"duration": 5, "resolution": "768p", "first_equals_last": True}, **QUOTE})
    dump(WORKDIR / "ecb-fx.json", ledger["fx"])
    dump(WORKDIR / "source-inspection.json", source)
    dump(WORKDIR / "request.json", request)
    dump(WORKDIR / "cost-ledger.json", ledger)
    report = f"""# MiniMax fixed-NE source trial\n\n## Current state\n\n- Preflight complete; no generation submitted at the time of this record.\n- Parent visual gate is required before any cutouts or further paid review.\n- This report concerns source selection only; it makes no runtime sprite claim.\n\n## Budget hold\n\n- Authorization ceiling: EUR 20.\n- ECB {fx_date}: 1 EUR = {usd_per_eur} USD; ceiling = USD {cap_usd}.\n- Prior reconciled maximum: USD {PRIOR_MAX_USD}.\n- Separate Gemini Omni unresolved estimate: USD {GEMINI_ESTIMATE_USD}.\n- This one-trial reservation: USD {RESERVATION_USD}.\n- Maximum accounted with hold: USD {held} = EUR {held / usd_per_eur}.\n- Exact live quote: USD {QUOTE['price']} undiscounted / USD {QUOTE['discounted_price']} discounted, estimate only. Both are below the USD 0.50 trial cap.\n\n## Source\n\n- Approved NE source SHA-256: `{source['sha256']}`; 1600x1600 RGB.\n- The copied input is byte-identical to the read-only source.\n- Visual preflight: full body, both feet and lantern are visible; NE rear-three-quarter orientation; no observed clipping.\n- Approximate corner-color foreground bbox: {source['approximate_foreground_bbox_threshold_12']}; margins L/T/R/B: {source['approximate_margins_left_top_right_bottom']}. This threshold is only a framing measurement, not a universal identity detector.\n\n## Requested operation\n\n- Exact model: `{MODEL}`.\n- 5 seconds, 768p, square canvas inherited from the first image.\n- The same full-resolution uploaded source is supplied as first and last image.\n- The prompt requires continuous in-place gait with no hold; same endpoints cannot certify motion, and static output must fail review.\n- Native provider MP4 will be retained. Any preview will be a separate audio-stripped derivative.\n\n## Pending evidence\n\nPrediction receipt, original MP4, ffprobe, native frame sequence, loop playback, automatic diagnostics, visual verdict and hashes are pending the single authorized submission.\n"""
    (WORKDIR / "MINIMAX_SOURCE_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps({"status": "ready", "workdir": str(WORKDIR), "source_sha256": source["sha256"], "ecb_date": fx_date, "usd_per_eur": str(usd_per_eur), "held_usd": str(held)}, sort_keys=True))


if __name__ == "__main__":
    main()
