import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("inspect_ground_support", ROOT / "skills/consistent-tileset-authoring/scripts/inspect-ground-support.py")
tool = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(tool)


class InspectGroundSupportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        Image.new("RGBA", (20, 20), "#597a52").save(self.tmp / "overlay.png")
        Image.new("L", (20, 20), 255).save(self.tmp / "support.png")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def recipe(self, **changes):
        recipe = {"version": 1, "overlay": "overlay.png", "supportMasks": [{"id": "dry", "image": "support.png"}], "footprint": {"halfWidthPx": 1, "halfHeightPx": 1}, "routes": [{"id": "path", "points": [[3, 10], [16, 10]], "clearancePx": 0}]}
        recipe.update(changes)
        return recipe

    def write(self, recipe, name="recipe.json"):
        path = self.tmp / name
        path.write_text(json.dumps(recipe), encoding="utf-8")
        return path

    def test_success_writes_review_measurements_and_refuses_overwrite(self):
        out = self.tmp / "out"
        result = tool.inspect(self.write(self.recipe()), out)
        self.assertTrue(result["passed"])
        self.assertEqual(result["totalSamples"], 14)
        self.assertTrue((out / "ground-support-review.png").is_file())
        self.assertIn("sha256", json.loads((out / "measurements.json").read_text())["inputs"]["tool"])
        with self.assertRaisesRegex(tool.GroundSupportError, "new directory"):
            tool.inspect(self.write(self.recipe(), "again.json"), out)

    def test_endpoints_pass_but_middle_crossing_fails(self):
        mask = Image.new("L", (20, 20), 255)
        mask.putpixel((10, 10), 0)
        mask.save(self.tmp / "support.png")
        result = tool.inspect(self.write(self.recipe()), self.tmp / "middle")
        self.assertFalse(result["passed"])
        self.assertGreater(result["routes"][0]["failedSamples"], 0)
        self.assertEqual(result["routes"][0]["masks"]["dry"]["firstDefect"]["pixel"], [10, 10])
        with patch.object(sys, "argv", ["inspect-ground-support.py", str(self.write(self.recipe(), "failed-cli.json")), "--out", str(self.tmp / "failed-cli")]):
            self.assertEqual(tool.main(), 3)

    def test_footprint_clearance_edge_and_subpixel_are_conservative(self):
        mask = Image.new("L", (20, 20), 255)
        mask.putpixel((8, 10), 0)
        mask.save(self.tmp / "support.png")
        footprint = self.recipe(footprint={"halfWidthPx": 2, "halfHeightPx": 1}, routes=[{"id": "wide", "points": [[10, 10], [10, 10]], "clearancePx": 0}])
        self.assertFalse(tool.inspect(self.write(footprint, "footprint.json"), self.tmp / "footprint")["passed"])
        narrow = self.recipe(routes=[{"id": "buffer", "points": [[10, 10], [10, 10]], "clearancePx": 1}])
        self.assertFalse(tool.inspect(self.write(narrow, "buffer.json"), self.tmp / "buffer")["passed"])
        diagonal = self.recipe(routes=[{"id": "diagonal", "points": [[3.2, 3.2], [5.2, 5.2]], "clearancePx": 0}])
        mask.putpixel((4, 5), 0); mask.save(self.tmp / "support.png")
        self.assertFalse(tool.inspect(self.write(diagonal, "diagonal.json"), self.tmp / "diagonal")["passed"])
        edge = self.recipe(routes=[{"id": "edge", "points": [[0, 0], [1, 0]], "clearancePx": 0}])
        self.assertFalse(tool.inspect(self.write(edge, "edge.json"), self.tmp / "edge")["passed"])

    def test_rejects_nonbinary_mismatch_unsafe_and_invalid_values(self):
        Image.new("L", (20, 20), 128).save(self.tmp / "support.png")
        with self.assertRaisesRegex(tool.GroundSupportError, "binary"):
            tool.inspect(self.write(self.recipe()), self.tmp / "binary")
        Image.new("L", (19, 20), 255).save(self.tmp / "support.png")
        with self.assertRaisesRegex(tool.GroundSupportError, "dimensions"):
            tool.inspect(self.write(self.recipe()), self.tmp / "size")
        Image.new("L", (20, 20), 255).save(self.tmp / "support.png")
        bad = self.recipe(overlay="../overlay.png")
        with self.assertRaisesRegex(tool.GroundSupportError, "inside"):
            tool.inspect(self.write(bad, "unsafe.json"), self.tmp / "unsafe")
        bad = self.recipe(footprint={"halfWidthPx": True, "halfHeightPx": 1})
        with self.assertRaisesRegex(tool.GroundSupportError, "finite"):
            tool.inspect(self.write(bad, "bool.json"), self.tmp / "bool")
        bad = self.recipe(routes=[{"id": "negative", "points": [[3, 3], [4, 3]], "clearancePx": -1}])
        with self.assertRaisesRegex(tool.GroundSupportError, "finite"):
            tool.inspect(self.write(bad, "negative.json"), self.tmp / "negative")
        bad = self.recipe(footprint={"halfWidthPx": 10 ** 1000, "halfHeightPx": 1})
        with self.assertRaisesRegex(tool.GroundSupportError, "finite"):
            tool.inspect(self.write(bad, "huge.json"), self.tmp / "huge")
        bad = self.recipe(footprint={"halfWidthPx": float("inf"), "halfHeightPx": 1})
        with self.assertRaisesRegex(tool.GroundSupportError, "finite JSON"):
            tool.inspect(self.write(bad, "infinite.json"), self.tmp / "infinite")
        bad = self.recipe(routes=[])
        with self.assertRaisesRegex(tool.GroundSupportError, "1.."):
            tool.inspect(self.write(bad, "empty.json"), self.tmp / "empty")
        with patch.object(sys, "argv", ["inspect-ground-support.py", str(self.write(bad, "cli.json")), "--out", str(self.tmp / "cli")]):
            self.assertEqual(tool.main(), 2)

    def test_oversized_routes_and_footprints_reject_before_materializing(self):
        oversized_route = self.recipe(routes=[{"id": "long", "points": [[0, 0], [32768, 0], [0, 0], [32768, 0], [0, 0], [32768, 0]], "clearancePx": 0}])
        with patch.object(tool, "samples", side_effect=AssertionError("samples must not materialize")):
            with self.assertRaisesRegex(tool.GroundSupportError, "route samples"):
                tool.inspect(self.write(oversized_route, "long.json"), self.tmp / "long")
        Image.new("RGBA", (8192, 1), "#597a52").save(self.tmp / "overlay.png")
        Image.new("L", (8192, 1), 255).save(self.tmp / "support.png")
        oversized_footprint = self.recipe(routes=[{"id": "wide", "points": [[1, 0], [2, 0]], "clearancePx": 8192}])
        with patch.object(tool, "footprint_offsets", side_effect=AssertionError("footprint must not materialize")):
            with self.assertRaisesRegex(tool.GroundSupportError, "footprint search"):
                tool.inspect(self.write(oversized_footprint, "wide.json"), self.tmp / "wide")


if __name__ == "__main__":
    unittest.main()
