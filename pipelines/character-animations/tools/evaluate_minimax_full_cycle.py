from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import quality_gates

WORKDIR = ROOT / "artifacts" / "minimax-ne-source-01"
FRAMES = WORKDIR / "native-frames"
START = 12
END_EXCLUSIVE = 42
INDICES = list(range(START, END_EXCLUSIVE, 2))


def main() -> None:
    names = [f"frame-{index + 1:04d}.png" for index in INDICES]
    result = quality_gates.evaluate_motion_sequence(
        FRAMES,
        names,
        native_indices=INDICES,
        native_fps=24.0,
        cycle_end_exclusive=END_EXCLUSIVE,
        expected_facing="ne",
    )
    result["analyzer_caveat"] = "The head-skin orientation feature is identity/background-specific and is not treated as universal visual evidence for this source."
    (WORKDIR / "full-cycle-12-42-motion-gate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    cell = 256
    label = 28
    columns = 5
    rows = (len(INDICES) + columns - 1) // columns
    board = Image.new("RGB", (columns * cell, rows * (cell + label)), (24, 29, 32))
    draw = ImageDraw.Draw(board)
    for order, index in enumerate(INDICES):
        with Image.open(FRAMES / f"frame-{index + 1:04d}.png") as opened:
            frame = opened.convert("RGB").resize((cell, cell), Image.Resampling.LANCZOS)
        x = (order % columns) * cell
        y = (order // columns) * (cell + label)
        board.paste(frame, (x, y))
        draw.text((x + 6, y + cell + 7), f"n{index} t={index/24:.3f}s", fill=(255, 220, 90))
    board.save(WORKDIR / "full-cycle-12-42-contact.png")
    print(json.dumps({"indices": INDICES, "status": result["status"], "rejection_reasons": result["rejection_reasons"]}, indent=2))


if __name__ == "__main__":
    main()
