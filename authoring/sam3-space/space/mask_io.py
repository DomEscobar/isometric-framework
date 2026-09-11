"""Native-pixel mask exports; independent of GPU/model imports."""
import hashlib
import json
import math
import uuid
from pathlib import Path

import numpy as np
from PIL import Image


def parse_boxes(raw, size):
    values = json.loads(raw or "[]")
    if not isinstance(values, list) or len(values) > 16:
        raise ValueError("Use a list of at most 16 labeled boxes.")
    width, height = size
    boxes, labels = [], []
    for value in values:
        if not isinstance(value, list) or len(value) != 5:
            raise ValueError("Each box must be [x1,y1,x2,y2,label].")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value):
            raise ValueError("Box coordinates and labels must be finite numbers.")
        x1, y1, x2, y2, label = value
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height and label in (0, 1)):
            raise ValueError("Box must be inside the original image; label must be 0 or 1.")
        boxes.append([x1, y1, x2, y2])
        labels.append(int(label))
    return boxes, labels


def export_masks(image, masks, scores, metadata, output_root):
    rgb = image.convert("RGB")
    masks = np.asarray(masks, dtype=bool)
    if masks.ndim != 3 or masks.shape[1:] != (rgb.height, rgb.width):
        raise ValueError("Model masks must match original image dimensions.")
    if len(scores) != len(masks):
        raise ValueError("Each mask needs a score.")
    directory = Path(output_root) / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False)
    original = np.asarray(rgb)
    gallery, paths, candidates = [], [], []
    for index, (mask, score) in enumerate(zip(masks, scores)):
        alpha = Image.fromarray(mask.astype(np.uint8) * 255)
        cutout = rgb.convert("RGBA")
        cutout.putalpha(alpha)
        mask_path = directory / f"mask-{index:02d}.png"
        cutout_path = directory / f"cutout-{index:02d}.png"
        alpha.save(mask_path)
        cutout.save(cutout_path)
        overlay = original.copy()
        overlay[mask] = (original[mask].astype(np.float32) * 0.55 + np.array([255, 0, 180]) * 0.45).astype(np.uint8)
        preview = directory / f"preview-{index:02d}.png"
        Image.fromarray(overlay).save(preview)
        gallery.append((str(preview), f"Mask {index:02d} · score {float(score):.3f}"))
        paths.extend([str(mask_path), str(cutout_path)])
        candidates.append({"index": index, "score": float(score), "pixels": int(mask.sum()),
                           "mask": mask_path.name, "cutout": cutout_path.name,
                           "mask_sha256": hashlib.sha256(mask_path.read_bytes()).hexdigest()})
    record = {**metadata, "request_id": directory.name,
              "source_rgb_sha256": hashlib.sha256(rgb.tobytes()).hexdigest(),
              "width": rgb.width, "height": rgb.height,
              "processing": "Native binary masks; original RGB; no cleanup or resizing",
              "visual_acceptance": "unverified", "candidates": candidates}
    record_path = directory / "result.json"
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    paths.append(str(record_path))
    return gallery, paths, record
