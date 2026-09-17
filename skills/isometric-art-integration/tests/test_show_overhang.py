import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

spec = importlib.util.spec_from_file_location(
    "show_overhang", Path(__file__).parents[1] / "scripts" / "show-overhang.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def contract(directory, image, width, render_width):
    """A single prop on a 1x1 footprint, so art wider than one tile has to spill."""
    return {
        "version": 1, "pack": "overhang-view-test",
        "projection": {"tileWidth": 64, "tileHeight": 32, "heightPixelsPerUnit": 1},
        "tolerances": {"groundErrorPx": 2, "heightErrorPx": 2},
        "heightReferences": {"standing": 40},
        "assets": [{
            "id": "tree", "kind": "prop", "image": image.name,
            "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            "frame": {"x": 0, "y": 0, "width": width, "height": width},
            "anchor": {"x": 0.5, "y": 1.0}, "render": {"width": render_width},
            "footprint": {"columns": 1, "rows": 1}, "heights": [],
            "overhangPx": 0, "allowedOverhang": "",
            "groundPoints": [
                {"source": {"x": width * 0.25, "y": width}, "grid": {"c": -0.25, "r": -0.25}},
                {"source": {"x": width * 0.75, "y": width}, "grid": {"c": 0.25, "r": 0.25}},
                {"source": {"x": width * 0.5, "y": width * 0.875}, "grid": {"c": 0.25, "r": -0.25}},
            ],
        }],
    }


class ShowOverhangTests(unittest.TestCase):
    def run_on(self, render_width, out="view"):
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        image = directory / "atlas.png"
        Image.new("RGBA", (96, 96), (30, 160, 60, 255)).save(image)
        path = directory / "contract.json"
        path.write_text(json.dumps(contract(directory, image, 96, render_width)), encoding="utf-8")
        return module.inspect(path, directory / out), directory / out

    def test_art_wider_than_its_footprint_yields_a_viewable_band_per_side(self):
        # The report is emitted even though overhangPx is 0 and the contract fails.
        result, output = self.run_on(96)
        self.assertFalse(result["passed"])
        self.assertEqual(len(result["regions"]), 1)
        region = result["regions"][0]
        self.assertRegex(region["regionSha256"], r"^[0-9a-f]{64}$")
        self.assertIsNone(region["classification"])
        self.assertEqual([band["side"] for band in region["bands"]], ["left", "right"])
        for band in region["bands"]:
            self.assertTrue((output / band["view"]).is_file())
            self.assertIsNotNone(band["groundClearancePx"])
        self.assertEqual(json.loads((output / "overhang.json").read_text(encoding="utf-8")), result)

    def test_art_inside_its_footprint_reports_nothing_to_classify(self):
        result, output = self.run_on(48)
        self.assertEqual(result["regions"], [])
        self.assertEqual(list(output.glob("*.png")), [])

    def test_an_existing_output_directory_is_refused(self):
        with self.assertRaises(FileExistsError):
            self.run_on(96, out=".")


if __name__ == "__main__":
    unittest.main()
