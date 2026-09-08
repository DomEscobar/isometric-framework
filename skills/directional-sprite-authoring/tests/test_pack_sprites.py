"""Offline authoring checks; no provider calls or live game changes."""

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pack-sprites.py"
MODULE_SPEC = importlib.util.spec_from_file_location("pack_sprites", SCRIPT)
packer = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(packer)


class PackSpritesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = Image.new("RGBA", (4, 5), (12, 34, 56, 0))
        self.source.putpixel((1, 1), (200, 40, 100, 128))
        self.source.putpixel((2, 3), (90, 80, 70, 255))
        self.source.save(self.base / "pose.png")
        self.spec = {"version": 1, "imageId": "hero", "cell": {"width": 4, "height": 5},
                     "anchor": {"x": 0.5, "y": 0.8},
                     "requiredDirections": ["ne", "se", "sw", "nw"], "requiredActions": ["idle", "walk"],
                     "clips": [{"action": action, "direction": direction, "fps": 8, "loop": True,
                                "frames": ["pose.png", "pose.png"]}
                               for action in ("idle", "walk") for direction in ("ne", "se", "sw", "nw")]}

    def run_pack(self, spec=None, name="out"):
        path = self.base / "spec.json"
        path.write_text(json.dumps(self.spec if spec is None else spec), encoding="utf-8")
        return packer.pack(path, self.base / name)

    def test_pixel_preservation_gutters_order_hashes_and_determinism(self):
        result = self.run_pack()
        with Image.open(self.base / "out/sheet.png") as sheet:
            self.assertEqual(sheet.size, (14, 58))
            occupied = set()
            for texture in result["assets"]["textures"].values():
                frame = texture["frame"]
                x, y = frame["x"], frame["y"]
                self.assertEqual(sheet.crop((x, y, x + 4, y + 5)).tobytes(), self.source.tobytes())
                self.assertEqual(texture["anchor"], {"x": 0.5, "y": 0.8})
                occupied.update((px, py) for px in range(x, x + 4) for py in range(y, y + 5))
            for y in range(sheet.height):
                for x in range(sheet.width):
                    if (x, y) not in occupied:
                        self.assertEqual(sheet.getpixel((x, y)), (0, 0, 0, 0))
        self.assertEqual(result["assets"]["animations"]["hero.idle.ne"]["frames"],
                         ["hero.idle.ne.0000", "hero.idle.ne.0001"])
        self.assertEqual(result["visualAnimations"]["idle"], "hero.idle.ne")
        self.assertEqual(result["visualAnimations"]["directions"]["nw"]["walk"], "hero.walk.nw")
        self.assertEqual(len(result["sourceHashes"]["frames"]["pose.png"]), 64)
        self.run_pack(name="again")
        for filename in ("sheet.png", "runtime.json"):
            self.assertEqual((self.base / "out" / filename).read_bytes(), (self.base / "again" / filename).read_bytes())

    def test_custom_action_is_nonlooping_and_not_native(self):
        self.spec["clips"].append({"action": "attack", "direction": "ne", "fps": 12,
                                   "loop": False, "frames": ["pose.png"]})
        result = self.run_pack()
        self.assertEqual(result["customActions"], {"attack": {"ne": "hero.attack.ne"}})
        self.assertFalse(result["assets"]["animations"]["hero.attack.ne"]["loop"])
        self.assertNotIn("attack", result["visualAnimations"])
        self.assertNotIn("attack", result["visualAnimations"]["directions"]["ne"])

    def test_palette_transparency_is_accepted(self):
        palette = Image.new("P", (4, 5), 0)
        palette.putpalette([0, 0, 0, 255, 0, 0] + [0] * 762)
        palette.putpixel((1, 1), 1)
        palette.save(self.base / "pose.png", transparency=0)
        self.run_pack()

    def test_rejects_false_or_missing_cutout_alpha(self):
        for mode, color in (("RGB", (1, 2, 3)), ("RGBA", (1, 2, 3, 255)),
                            ("RGBA", (1, 2, 3, 0)), ("RGBA", (1, 2, 3, 128))):
            with self.subTest(mode=mode, color=color):
                Image.new(mode, (4, 5), color).save(self.base / "pose.png")
                with self.assertRaisesRegex(ValueError, "alpha|transparent"):
                    self.run_pack()
                self.assertFalse((self.base / "out").exists())

    def test_rejects_dimensions_and_non_png(self):
        Image.new("RGBA", (5, 5), (0, 0, 0, 0)).save(self.base / "pose.png")
        with self.assertRaisesRegex(ValueError, "dimensions"):
            self.run_pack()
        Image.new("RGB", (4, 5)).save(self.base / "pose.png", format="JPEG")
        with self.assertRaisesRegex(ValueError, "decode as PNG"):
            self.run_pack()

    def test_rejects_animated_and_high_bit_depth_png(self):
        second = self.source.copy()
        second.putpixel((1, 1), (1, 2, 3, 255))
        self.source.save(self.base / "pose.png", save_all=True, append_images=[second], duration=100)
        with self.assertRaisesRegex(ValueError, "animated PNG"):
            self.run_pack()
        Image.new("I;16", (4, 5)).save(self.base / "pose.png")
        with self.assertRaisesRegex(ValueError, "bit depth"):
            self.run_pack()

    def test_rejects_matrix_and_duplicate_pairs(self):
        spec = copy.deepcopy(self.spec)
        spec["clips"].pop()
        with self.assertRaisesRegex(ValueError, "missing required"):
            self.run_pack(spec)
        spec = copy.deepcopy(self.spec)
        spec["clips"].append(copy.deepcopy(spec["clips"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate action/direction"):
            self.run_pack(spec)

    def test_schema_and_bounds(self):
        mutations = [lambda s: s.update(unexpected=True), lambda s: s.update(version=True),
                     lambda s: s.update(imageId="constructor"), lambda s: s["anchor"].update(x=1.1),
                     lambda s: s["cell"].update(width=True), lambda s: s["clips"][0].update(direction="up"),
                     lambda s: s["clips"][0].update(loop=1), lambda s: s["clips"][0].update(fps=0),
                     lambda s: s["clips"][0].update(fps=10 ** 500),
                     lambda s: s["requiredDirections"].append("ne"), lambda s: s.update(requiredActions=[]),
                     lambda s: s["clips"][0].update(frames=["pose.png"] * 257),
                     lambda s: s["cell"].update(width=1024, height=1024)]
        for mutation in mutations:
            spec = copy.deepcopy(self.spec)
            mutation(spec)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.run_pack(spec)
            self.assertFalse((self.base / "out").exists())

    def test_frame_paths_cannot_escape_or_be_urls(self):
        for value in ("../pose.png", "/pose.png", "C:/pose.png", "https://example.com/pose.png", "..\\pose.png"):
            spec = copy.deepcopy(self.spec)
            spec["clips"][0]["frames"][0] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.run_pack(spec)

    def test_existing_directory_is_never_overwritten(self):
        self.run_pack()
        before = (self.base / "out/runtime.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.run_pack()
        self.assertEqual((self.base / "out/runtime.json").read_bytes(), before)

    def test_duplicate_json_keys_and_nonfinite_values(self):
        path = self.base / "spec.json"
        for raw in ('{"version":1,"version":1}', '{"fps":NaN}'):
            path.write_text(raw, encoding="utf-8")
            with self.assertRaises(ValueError):
                packer.pack(path, self.base / "out")


if __name__ == "__main__":
    unittest.main()
