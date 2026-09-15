"""Offline authoring checks; no provider calls or live game changes."""

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "mirror-frames.py"
PACKER = Path(__file__).resolve().parents[1] / "scripts" / "pack-sprites.py"
MODULE = importlib.util.spec_from_file_location("mirror_frames", SCRIPT)
mirrorer = importlib.util.module_from_spec(MODULE)
MODULE.loader.exec_module(mirrorer)
PACK_SPEC = importlib.util.spec_from_file_location("pack_sprites", PACKER)
packer = importlib.util.module_from_spec(PACK_SPEC)
PACK_SPEC.loader.exec_module(packer)


class MirrorFramesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "export"
        self.source.mkdir()
        (self.source / "frames").mkdir()
        first = Image.new("RGBA", (4, 5), (0, 0, 0, 0))
        first.putpixel((0, 1), (200, 10, 10, 255))
        first.putpixel((2, 3), (10, 20, 200, 128))
        first.save(self.source / "frames/frame-0000.png")
        second = Image.new("RGBA", (4, 5), (0, 0, 0, 0))
        second.putpixel((3, 4), (10, 200, 10, 255))
        second.save(self.source / "frames/frame-0001.png")
        self.first, self.second = first, second
        self.write_spec("ne", 0.5)

    def write_spec(self, direction, anchor_x):
        spec = {
            "version": 2,
            "origin": {"kind": "video-extraction", "provenance": "provenance.json"},
            "imageId": "hero",
            "cell": {"width": 4, "height": 5},
            "anchor": {"x": anchor_x, "y": 0.8},
            "requiredDirections": [direction],
            "requiredActions": ["walk"],
            "clips": [{"action": "walk", "direction": direction, "fps": 8, "loop": True,
                       "frames": ["frames/frame-0000.png", "frames/frame-0001.png"]}],
        }
        path = self.source / "sprite-pack.json"
        raw = json.dumps(spec, indent=2) + "\n"
        path.write_text(raw, encoding="utf-8", newline="\n")
        frames = ["frames/frame-0000.png", "frames/frame-0001.png"]
        provenance = {
            "version": 2,
            "spritePackSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "exportedFrames": [
                {"file": name, "sha256": hashlib.sha256((self.source / name).read_bytes()).hexdigest()}
                for name in frames
            ],
        }
        (self.source / "provenance.json").write_text(json.dumps(provenance) + "\n", encoding="utf-8")
        return spec

    def test_horizontal_flip_remaps_ne_to_nw_and_preserves_hashes(self):
        result = mirrorer.mirror(self.source / "sprite-pack.json", self.base / "nw", "nw")
        self.assertEqual(result["origin"], {"kind": "mirrored-extraction", "provenance": "provenance.json"})
        self.assertEqual(result["requiredDirections"], ["nw"])
        self.assertEqual(result["clips"][0]["direction"], "nw")
        self.assertEqual(result["anchor"], {"x": 0.5, "y": 0.8})
        with Image.open(self.base / "nw/frames/frame-0000.png") as flipped:
            self.assertEqual(flipped.getpixel((3, 1)), (200, 10, 10, 255))
            self.assertEqual(flipped.getpixel((1, 3)), (10, 20, 200, 128))
            self.assertEqual(flipped.getpixel((0, 1))[3], 0)
        packed = packer.pack(self.base / "nw/sprite-pack.json", self.base / "packed")
        self.assertEqual(packed["visualAnimations"]["directions"]["nw"]["walk"], "hero.walk.nw")
        self.assertEqual(packed["sourceHashes"]["provenance"],
                         hashlib.sha256((self.base / "nw/provenance.json").read_bytes()).hexdigest())
        mirrorer.mirror(self.source / "sprite-pack.json", self.base / "nw-again", "nw")
        for name in ("sprite-pack.json", "provenance.json", "frames/frame-0000.png", "frames/frame-0001.png"):
            self.assertEqual((self.base / "nw" / name).read_bytes(), (self.base / "nw-again" / name).read_bytes())

    def test_anchor_x_is_mirrored(self):
        self.write_spec("se", 0.8)
        result = mirrorer.mirror(self.source / "sprite-pack.json", self.base / "sw", "sw")
        self.assertAlmostEqual(result["anchor"]["x"], 0.2)
        self.assertEqual(result["clips"][0]["direction"], "sw")

    def test_rejects_front_back_and_chained_mirrors(self):
        with self.assertRaisesRegex(ValueError, r"target direction is not a horizontal facing pair"):
            mirrorer.mirror(self.source / "sprite-pack.json", self.base / "s", "s")
        with self.assertRaisesRegex(ValueError, "horizontal pair of ne is nw"):
            mirrorer.mirror(self.source / "sprite-pack.json", self.base / "se", "se")
        mirrorer.mirror(self.source / "sprite-pack.json", self.base / "nw", "nw")
        with self.assertRaisesRegex(ValueError, "do not chain mirrors"):
            mirrorer.mirror(self.base / "nw/sprite-pack.json", self.base / "ne-again", "ne")

    def test_rejects_stale_source_and_existing_output(self):
        (self.source / "frames/frame-0000.png").write_bytes((self.source / "frames/frame-0001.png").read_bytes())
        with self.assertRaisesRegex(ValueError, "does not bind frame"):
            mirrorer.mirror(self.source / "sprite-pack.json", self.base / "stale", "nw")
        self.write_spec("ne", 0.5)
        mirrorer.mirror(self.source / "sprite-pack.json", self.base / "nw", "nw")
        with self.assertRaisesRegex(ValueError, "already exists"):
            mirrorer.mirror(self.source / "sprite-pack.json", self.base / "nw", "nw")

    def test_east_west_pair(self):
        self.write_spec("e", 0.5)
        result = mirrorer.mirror(self.source / "sprite-pack.json", self.base / "w", "w")
        self.assertEqual(result["clips"][0]["direction"], "w")


if __name__ == "__main__":
    unittest.main()
