import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("inspect_registration", ROOT / "skills/consistent-tileset-authoring/scripts/inspect-registration.py")
tool = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(tool)


class InspectRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.guide = self.tmp / "guide.png"
        self.candidate = self.tmp / "candidate.png"
        for path, bridge_x in ((self.guide, 12), (self.candidate, 12)):
            image = Image.new("RGBA", (32, 24), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            draw.rectangle((bridge_x, 8, bridge_x + 7, 14), fill="#b58c55")
            image.save(path)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def recipe(self, observed=None):
        return {"version": 1, "layoutGuide": "guide.png", "candidate": "candidate.png", "pixelTolerance": 1,
                "expectedLandmarks": [{"id": "north-west", "x": 0, "y": 0}, {"id": "south-east", "x": 31, "y": 23}, {"id": "bridge-centre", "x": 15, "y": 11}],
                "observedLandmarks": observed or [{"id": "north-west", "x": 0, "y": 0}, {"id": "south-east", "x": 31, "y": 23}, {"id": "bridge-centre", "x": 15, "y": 11}]}

    def write(self, data, name="recipe.json"):
        path = self.tmp / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_passing_measurement_writes_deterministic_review_artifacts(self):
        result = tool.inspect(self.write(self.recipe()), self.tmp / "pass")
        self.assertTrue(result["passed"])
        self.assertEqual(result["maximumResidual"], 0)
        out = self.tmp / "pass"
        with Image.open(out / "registration-board.png") as board:
            self.assertEqual(board.size, (64, 88))
            self.assertEqual(board.getpixel((2, 20)), (202, 199, 192))
        self.assertTrue(json.loads((out / "provenance.json").read_text())["outputs"]["registration-board.png"])

    def test_matching_outer_corners_do_not_hide_misplaced_interior_bridge(self):
        image = Image.new("RGBA", (32, 24), "#587a52")
        ImageDraw.Draw(image).rectangle((18, 8, 25, 14), fill="#b58c55")
        image.save(self.candidate)
        observed = [{"id": "north-west", "x": 0, "y": 0}, {"id": "south-east", "x": 31, "y": 23}, {"id": "bridge-centre", "x": 21, "y": 11}]
        result = tool.inspect(self.write(self.recipe(observed)), self.tmp / "failed")
        self.assertFalse(result["passed"])
        bridge = next(row for row in result["landmarks"] if row["id"] == "bridge-centre")
        self.assertEqual(bridge["residual"]["distance"], 6)
        self.assertFalse(bridge["withinTolerance"])
        recipe_path = self.write(self.recipe(observed), "failed-cli.json")
        with patch.object(sys, "argv", ["inspect-registration.py", str(recipe_path), "--out", str(self.tmp / "failed-cli")]):
            self.assertEqual(tool.main(), 3)

    def test_rejects_invalid_landmarks_dimension_mismatch_and_existing_output(self):
        bad = self.recipe()
        bad["observedLandmarks"][2]["x"] = float("nan")
        with self.assertRaisesRegex(tool.RegistrationError, "NaN"):
            tool.inspect(self.write(bad, "nan.json"), self.tmp / "nan")
        bad = self.recipe()
        bad["observedLandmarks"][2]["id"] = "north-west"
        with self.assertRaisesRegex(tool.RegistrationError, "duplicate"):
            tool.inspect(self.write(bad, "duplicate.json"), self.tmp / "duplicate")
        bad = self.recipe()
        bad["observedLandmarks"] = bad["observedLandmarks"][:2]
        with self.assertRaisesRegex(tool.RegistrationError, "3.."):
            tool.inspect(self.write(bad, "short.json"), self.tmp / "short")
        Image.new("RGBA", (31, 24)).save(self.candidate)
        with self.assertRaisesRegex(tool.RegistrationError, "dimensions"):
            tool.inspect(self.write(self.recipe(), "dimensions.json"), self.tmp / "dimensions")
        self.candidate.unlink()
        Image.new("RGBA", (32, 24)).save(self.candidate)
        occupied = self.tmp / "occupied"
        occupied.mkdir()
        with self.assertRaisesRegex(tool.RegistrationError, "new directory"):
            tool.inspect(self.write(self.recipe(), "occupied.json"), occupied)

    def test_rejects_missing_ids_out_of_range_noninterior_same_file_and_external_paths(self):
        bad = self.recipe()
        bad["observedLandmarks"][2]["id"] = "path-centre"
        with self.assertRaisesRegex(tool.RegistrationError, "same landmark IDs"):
            tool.inspect(self.write(bad, "ids.json"), self.tmp / "ids")
        bad = self.recipe()
        bad["expectedLandmarks"][2]["x"] = 32
        with self.assertRaisesRegex(tool.RegistrationError, "0..31"):
            tool.inspect(self.write(bad, "range.json"), self.tmp / "range")
        bad = self.recipe()
        bad["expectedLandmarks"] = [{"id": "north-west", "x": 0, "y": 0}, {"id": "north-east", "x": 31, "y": 0}, {"id": "south-east", "x": 31, "y": 23}]
        bad["observedLandmarks"] = list(bad["expectedLandmarks"])
        with self.assertRaisesRegex(tool.RegistrationError, "interior"):
            tool.inspect(self.write(bad, "corners.json"), self.tmp / "corners")
        bad = self.recipe()
        bad["candidate"] = "guide.png"
        with self.assertRaisesRegex(tool.RegistrationError, "different files"):
            tool.inspect(self.write(bad, "same.json"), self.tmp / "same")
        bad = self.recipe()
        bad["candidate"] = "../candidate.png"
        with self.assertRaisesRegex(tool.RegistrationError, "inside"):
            tool.inspect(self.write(bad, "external.json"), self.tmp / "external")
        bad = self.recipe()
        bad["pixelTolerance"] = -1
        recipe_path = self.write(bad, "bad-cli.json")
        with patch.object(sys, "argv", ["inspect-registration.py", str(recipe_path), "--out", str(self.tmp / "bad-cli")]):
            self.assertEqual(tool.main(), 2)


if __name__ == "__main__":
    unittest.main()
