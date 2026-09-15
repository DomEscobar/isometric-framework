"""Deterministic video extraction fixtures (ffmpeg is optional in CI)."""

import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/extract-video.py"
MODULE_SPEC = importlib.util.spec_from_file_location("extract_video", SCRIPT)
extractor = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(extractor)
HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg and ffprobe are required for video fixtures")
class ExtractVideoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.frames = self.base / "input"; self.frames.mkdir()
        # More than one varied frame makes frame-count and provenance meaningful.
        for index, color in enumerate(((0, 255, 255), (30, 220, 255), (0, 255, 220), (20, 230, 240))):
            image = Image.new("RGB", (48, 40), color)
            ImageDraw.Draw(image).rectangle((8 + index * 3, 8, 22 + index * 3, 32), fill=(220, 40 + index * 20, 80))
            image.save(self.frames / f"frame-{index}.png")
        self.video = self.base / "fixture.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-framerate", "5", "-i", str(self.frames / "frame-%d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(self.video)], check=True)
        extractor.prepare(self.video, self.base / "review", "#00ffff", 48)

    def recipe(self):
        path = self.base / "review" / "extraction.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["selection"] = {"indices": [0, 1, 2, 3], "fps": 6.4}
        value["clip"] = {"imageId": "ranger", "action": "walk", "direction": "ne", "loop": True,
                         "anchor": {"x": .5, "y": .9}}
        path.write_text(json.dumps(value), encoding="utf-8")
        # Editing the recipe never changes the preparation hash stored in it.
        return path

    def test_prepare_cfr_records_actual_timestamped_pngs_and_export_is_reproducible(self):
        prep = json.loads((self.base / "review" / "preparation.json").read_text(encoding="utf-8"))
        self.assertEqual(len(prep["decodedFrames"]), 4)
        self.assertEqual([item["timeSeconds"] for item in prep["decodedFrames"]], sorted(item["timeSeconds"] for item in prep["decodedFrames"]))
        self.assertTrue((self.base / "review" / "contact-board-001.png").is_file())
        self.assertTrue((self.base / "review" / "alpha-board-001.png").is_file())
        recipe = self.recipe()
        spec = extractor.export(recipe, self.base / "export")
        self.assertEqual(spec["clips"][0]["fps"], 6.4)
        provenance = json.loads((self.base / "export" / "provenance.json").read_text(encoding="utf-8"))
        self.assertEqual([item["sourceIndex"] for item in provenance["selected"]], [0, 1, 2, 3])
        self.assertEqual([item["decodedFrameSha256"] for item in provenance["selected"]],
                         [item["sha256"] for item in prep["decodedFrames"]])
        # The emitted spec can pass through the existing packer unchanged.
        packer_path = Path(__file__).resolve().parents[1] / "scripts" / "pack-sprites.py"
        result = subprocess.run([sys.executable, "-B", str(packer_path), str(self.base / "export" / "sprite-pack.json"), "--out", str(self.base / "packed")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_variable_timestamp_fixture_is_preserved_without_forced_fps(self):
        concat = self.base / "concat.txt"
        concat.write_text("".join(f"file '{(self.frames / f'frame-{i}.png').as_posix()}'\nduration {duration}\n" for i, duration in enumerate((.10, .35, .12, .4))) + f"file '{(self.frames / 'frame-3.png').as_posix()}'\n", encoding="utf-8")
        video = self.base / "variable.mkv"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat), "-vsync", "vfr", "-c:v", "ffv1", str(video)], check=True)
        extractor.prepare(video, self.base / "variable-review")
        prep = json.loads((self.base / "variable-review" / "preparation.json").read_text(encoding="utf-8"))
        self.assertGreater(len(prep["decodedFrames"]), 1)
        intervals = [b["timeSeconds"] - a["timeSeconds"] for a, b in zip(prep["decodedFrames"], prep["decodedFrames"][1:])]
        self.assertNotEqual(len(set(intervals)), 1)

    def test_export_refuses_stale_hashes_invalid_author_fields_and_clipping(self):
        recipe = self.recipe()
        value = json.loads(recipe.read_text(encoding="utf-8"))
        value["crop"]["width"] = 1
        recipe.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "crop clips"):
            extractor.export(recipe, self.base / "bad-crop")
        recipe = self.recipe()
        value = json.loads(recipe.read_text(encoding="utf-8")); value["selection"]["indices"] = [99]
        recipe.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(ValueError): extractor.export(recipe, self.base / "out-of-bounds")
        recipe = self.recipe()
        value = json.loads(recipe.read_text(encoding="utf-8")); value["clip"]["unknown"] = True
        recipe.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(ValueError): extractor.export(recipe, self.base / "unknown")
        # A stale prepared frame is caught before output creation.
        frame = self.base / "review" / "frames" / "frame-000000.png"
        frame.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "decoded frame hash"):
            extractor.export(self.recipe(), self.base / "stale-frame")

    def test_selected_frames_can_exclude_an_outlier_crop_and_preview_uses_saved_timing(self):
        review = (self.base / "review" / "review.html").read_text(encoding="utf-8")
        self.assertNotIn("setInterval", review)
        self.assertIn("setTimeout", review)
        recipe = self.recipe()
        value = json.loads(recipe.read_text(encoding="utf-8"))
        first = self.base / "review" / value["preparation"]["file"]
        preparation = json.loads(first.read_text(encoding="utf-8"))
        frame = self.base / "review" / preparation["decodedFrames"][0]["file"]
        bounds = extractor.alpha_bounds(frame, extractor.parse_key("#00ffff"), 48)
        value["selection"]["indices"] = [0]
        left, top = max(0, bounds[0] - 1), max(0, bounds[1] - 1)
        right, bottom = min(48, bounds[2] + 1), min(40, bounds[3] + 1)
        value["crop"] = {"x": left, "y": top, "width": right - left, "height": bottom - top}
        recipe.write_text(json.dumps(value), encoding="utf-8")
        extractor.export(recipe, self.base / "one-frame")
        preview = (self.base / "one-frame" / "preview.html").read_text(encoding="utf-8")
        self.assertIn("156", preview)  # round(1000 / explicit 6.4 FPS)

    def test_preparation_and_source_hashes_are_verified(self):
        recipe = self.recipe()
        source = next((self.base / "review" / "source").iterdir())
        source.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "source hash"):
            extractor.export(recipe, self.base / "stale-source")
        # A modified preparation is rejected by its recipe pin before its schema is trusted.
        extractor.prepare(self.video, self.base / "review-two", "#00ffff", 48)
        recipe = self.base / "review-two" / "extraction.json"
        value = json.loads(recipe.read_text(encoding="utf-8"))
        value["selection"] = {"indices": [0], "fps": 6.4}
        value["clip"] = {"imageId": "ranger", "action": "walk", "direction": "ne", "loop": True, "anchor": {"x": .5, "y": .9}}
        recipe.write_text(json.dumps(value), encoding="utf-8")
        prep = self.base / "review-two" / "preparation.json"
        prep.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "preparation hash"):
            extractor.export(recipe, self.base / "stale-preparation")


class ValidationTests(unittest.TestCase):
    def test_parse_key_and_finite_values_are_strict(self):
        self.assertEqual(extractor.parse_key("#00ffff"), (0, 255, 255))
        for value in ("cyan", "#000", "#00fffg"):
            with self.assertRaises(ValueError): extractor.parse_key(value)
        with self.assertRaises(ValueError): extractor.finite(float("nan"), 0, 1, "x")


if __name__ == "__main__":
    unittest.main()
