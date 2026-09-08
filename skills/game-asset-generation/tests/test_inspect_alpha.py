import importlib.util
from pathlib import Path
import tempfile
import unittest

from PIL import Image

spec = importlib.util.spec_from_file_location(
    "inspect_alpha", Path(__file__).parents[1] / "scripts" / "inspect-alpha.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AlphaInspectionTests(unittest.TestCase):
    def inspect_image(self, image, size=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.png"
            image.save(path)
            original = path.read_bytes()
            report, rgba = module.inspect(path, size)
            self.assertEqual(path.read_bytes(), original)
            return report, rgba

    def test_rgb_checkerboard_is_not_transparency(self):
        image = Image.new("RGB", (8, 8), "white")
        image.putpixel((1, 1), (120, 120, 120))
        report, _ = self.inspect_image(image)
        self.assertFalse(report["has_cutout_alpha"])
        self.assertFalse(report["explicit_alpha"])
        self.assertEqual(report["opaque_pixels"], 64)

    def test_empty_rgba_and_opaque_rgba_are_not_cutouts(self):
        for alpha in [0, 255]:
            report, _ = self.inspect_image(Image.new("RGBA", (4, 4), (2, 3, 4, alpha)))
            self.assertFalse(report["has_cutout_alpha"])

    def test_cutout_bounds_partial_alpha_and_backgrounds(self):
        image = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
        image.putpixel((2, 3), (255, 0, 0, 255))
        image.putpixel((3, 3), (255, 0, 0, 128))
        report, rgba = self.inspect_image(image, (8, 8))
        self.assertEqual(report["nonzero_alpha_bounds"], (2, 3, 4, 4))
        self.assertEqual(report["partial_alpha_pixels"], 1)
        self.assertTrue(report["has_cutout_alpha"])
        self.assertFalse(report["touches_canvas_edge"])
        self.assertEqual(report["visual_quality"], "unverified")
        board = module.comparison(rgba)
        self.assertEqual(board.size, (24, 32))
        self.assertEqual(board.getpixel((2, 27)), (255, 0, 0))
        self.assertNotEqual(board.getpixel((0, 24)), board.getpixel((8, 24)))

    def test_palette_transparency_and_size_drift(self):
        image = Image.new("P", (8, 8), 0)
        image.info["transparency"] = 0
        image.putpixel((0, 1), 1)
        report, _ = self.inspect_image(image, (9, 8))
        self.assertTrue(report["explicit_alpha"])
        self.assertTrue(report["has_cutout_alpha"])
        self.assertTrue(report["touches_canvas_edge"])
        self.assertFalse(report["size_matches"])


if __name__ == "__main__":
    unittest.main()
