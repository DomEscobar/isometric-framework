import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare-request.py"
SPEC = importlib.util.spec_from_file_location("prepare_request", SCRIPT)
preparer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preparer)


class PrepareRequestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.sheet = Image.new("RGBA", (6, 4), (0, 0, 0, 0))
        for y in range(4):
            for x in range(6):
                self.sheet.putpixel((x, y), (x * 30, y * 40, 90, 255))
        self.sheet.save(self.base / "sheet.png")
        self.layout = Image.new("RGB", (3, 2), (12, 90, 40))
        self.layout.save(self.base / "layout.png")
        self.source_hash = hashlib.sha256((self.base / "sheet.png").read_bytes()).hexdigest()
        self.identity_selection = {"sourceSha256": self.source_hash,
                                   "crop": {"x": 1, "y": 1, "width": 3, "height": 2},
                                   "pixelsSha256": hashlib.sha256(self.sheet.crop((1, 1, 4, 3)).tobytes()).hexdigest()}
        self.spec = {"version": 2, "description": "A measured character facing reference request.",
                     "references": [
                         {"id": "look", "path": "sheet.png", "role": "style", "approval": None, "crop": None},
                         {"id": "layout", "path": "layout.png", "role": "layout", "approval": None, "crop": None},
                         {"id": "hero-ne", "path": "sheet.png", "role": "identity", "approval": "approved",
                          "crop": {"x": 1, "y": 1, "width": 3, "height": 2}},
                     ]}

    def run_prepare(self, spec=None, name="out"):
        path = self.base / "request-spec.json"
        path.write_text(json.dumps(self.spec if spec is None else spec), encoding="utf-8")
        return preparer.prepare(path, self.base / name)

    def test_exact_whole_image_crop_roles_board_and_provenance(self):
        report = self.run_prepare()
        self.assertEqual((self.base / "out/look.png").read_bytes(), (self.base / "sheet.png").read_bytes())
        with Image.open(self.base / "out/hero-ne.png") as crop:
            self.assertEqual(crop.tobytes(), self.sheet.crop((1, 1, 4, 3)).tobytes())
        self.assertEqual([entry["role"] for entry in report["request"]["references"]], ["style", "layout", "identity"])
        hero = report["request"]["references"][2]
        self.assertEqual(hero["sourceSha256"], self.source_hash)
        self.assertEqual(hero["pixelsSha256"], self.identity_selection["pixelsSha256"])
        self.assertEqual(hero["crop"], {"x": 1, "y": 1, "width": 3, "height": 2})
        self.assertEqual(len(report["provenance"]["specSha256"]), 64)
        self.assertEqual(report["provenance"]["boardSha256"], hashlib.sha256((self.base / "out/board.png").read_bytes()).hexdigest())
        with Image.open(self.base / "out/board.png") as board:
            self.assertGreater(board.width, 6)
            self.assertGreater(board.height, 4)

    def test_rejected_identity_and_invalid_crop_are_refused_before_output(self):
        rejected = copy.deepcopy(self.spec)
        rejected["references"][2]["approval"] = "rejected"
        with self.assertRaisesRegex(ValueError, "explicitly approved"):
            self.run_prepare(rejected)
        self.assertFalse((self.base / "out").exists())
        invalid = copy.deepcopy(self.spec)
        invalid["references"][2]["crop"]["width"] = 6
        with self.assertRaisesRegex(ValueError, "outside source"):
            self.run_prepare(invalid)
        self.assertFalse((self.base / "out").exists())

    def test_legacy_matrix_and_calibration_fields_are_rejected(self):
        legacy = copy.deepcopy(self.spec)
        legacy["version"] = 1
        legacy["matrix"] = {"action": "walk", "directions": ["ne", "se"], "calibrationReceipt": "calibration.json"}
        with self.assertRaisesRegex(ValueError, "exactly these keys"):
            self.run_prepare(legacy)

    def test_existing_outputs_are_not_overwritten(self):
        self.run_prepare()
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.run_prepare()

    def test_generated_board_name_is_reserved(self):
        spec = copy.deepcopy(self.spec)
        spec["references"][0]["id"] = "board"
        with self.assertRaisesRegex(ValueError, "reserved"):
            self.run_prepare(spec)
        self.assertFalse((self.base / "out").exists())

    def test_board_width_includes_a_long_label_for_a_narrow_crop(self):
        spec = copy.deepcopy(self.spec)
        spec["references"][2]["id"] = "very-long-approved-identity-reference-id"
        spec["references"][2]["crop"] = {"x": 1, "y": 1, "width": 1, "height": 1}
        report = self.run_prepare(spec)
        label = "very-long-approved-identity-reference-id [identity]"
        measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        required_width = measure.textbbox((0, 0), label)[2] + 8
        with Image.open(self.base / "out/board.png") as board:
            self.assertGreaterEqual(board.width, required_width)
        self.assertEqual(report["request"]["references"][2]["pixels"], {"width": 1, "height": 1})

    def test_paths_and_schema_are_bounded(self):
        for path in ("../sheet.png", "C:/sheet.png", "https://example.test/a.png", "..\\sheet.png"):
            spec = copy.deepcopy(self.spec)
            spec["references"][0]["path"] = path
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.run_prepare(spec)
        spec = copy.deepcopy(self.spec)
        spec["references"][0]["unexpected"] = True
        with self.assertRaises(ValueError):
            self.run_prepare(spec)


if __name__ == "__main__":
    unittest.main()
