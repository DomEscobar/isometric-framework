import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("prepare_ground", ROOT / "skills/consistent-tileset-authoring/scripts/prepare-ground.py")
tool = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(tool)
verify_spec = importlib.util.spec_from_file_location("verify_world", ROOT / "skills/isometric-visual-loop/scripts/verify-world.py")
verify_world = importlib.util.module_from_spec(verify_spec)
assert verify_spec and verify_spec.loader
verify_spec.loader.exec_module(verify_world)


class PrepareGroundTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.recipe = self.tmp / "recipe.json"
        image = Image.new("RGBA", (5, 3))
        image.putdata([(x * 40, y * 70, 90, 255 if (x + y) % 2 else 0) for y in range(3) for x in range(5)])
        image.save(self.tmp / "source.png")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def prepare(self, recipe, name="out"):
        self.recipe.write_text(json.dumps(recipe), encoding="utf-8")
        tool.run(self.recipe, self.tmp / name)
        return self.tmp / name

    def base(self):
        return {"version": 1, "source": "source.png"}

    def test_identity_preserves_hidden_rgb_and_plate_schema(self):
        coverage = Image.new("L", (5, 3), 255)
        coverage.putpixel((1, 0), 128)
        coverage.putpixel((2, 0), 0)
        coverage.save(self.tmp / "coverage.png")
        out = self.prepare(self.base() | {"coverageMask": "coverage.png", "output": {"origin": [-4, 6]}})
        self.assertEqual(Image.open(self.tmp / "source.png").convert("RGB").tobytes(), Image.open(out / "ground.png").convert("RGB").tobytes())
        manifest = json.loads((out / "manifest.json").read_text())
        self.assertEqual(manifest["textures"]["ground"]["anchor"], {"x": 0, "y": 0})
        self.assertEqual(manifest["placements"]["ground"], {"x": -4, "y": 6})
        self.assertEqual(json.loads((out / "packed-art.json").read_text())["manifest"], "manifest.json")
        self.assertTrue(verify_world.inspect(out / "packed-art.json")["passed"])

    def test_affine_uses_pillow_pixel_centres_and_explicit_policy(self):
        out = self.prepare(self.base() | {"outputToSource": [1, 0, 1, 0, 1, 0], "output": {"width": 4, "height": 3}})
        self.assertEqual(Image.open(out / "ground.png").getpixel((0, 1)), Image.open(self.tmp / "source.png").getpixel((1, 1)))
        with self.assertRaisesRegex(tool.RecipeError, "outside"):
            self.prepare(self.base() | {"outputToSource": [2, 0, 0, 0, 1, 0], "output": {"width": 3, "height": 3}}, "edge")
        out = self.prepare(self.base() | {"output": {"width": 6, "height": 3, "outOfBounds": "transparent"}}, "transparent")
        self.assertEqual(Image.open(out / "ground.png").getpixel((5, 0)), (0, 0, 0, 0))
        with self.assertRaisesRegex(tool.RecipeError, "finite"):
            self.prepare(self.base() | {"outputToSource": [True, 0, 0, 0, 1, 0]}, "boolean")

    def test_masks_chunks_gutters_origin_and_exact_reassembly(self):
        Image.new("L", (5, 3), 128).save(self.tmp / "coverage.png")
        moving = Image.new("L", (5, 3))
        moving.putpixel((1, 0), 255)
        moving.save(self.tmp / "moving.png")
        out = self.prepare(self.base() | {"coverageMask": "coverage.png", "movingMask": "moving.png", "output": {"mode": "chunks", "chunkSize": [3, 2], "gutter": 2, "origin": [-5, 7]}})
        data = json.loads((out / "manifest.json").read_text())
        rebuilt = Image.new("RGBA", (5, 3))
        for identifier, placement in data["placements"].items():
            texture = data["textures"][identifier]
            frame = texture["frame"]
            image = Image.open(out / data["images"][texture["image"]]["url"])
            crop = image.crop((frame["x"], frame["y"], frame["x"] + frame["width"], frame["y"] + frame["height"]))
            rebuilt.paste(crop, (placement["x"] + 5, placement["y"] - 7))
            self.assertEqual(texture["anchor"], {"x": 0, "y": 0})
        self.assertEqual(rebuilt.tobytes(), Image.open(out / "ground.png").tobytes())
        self.assertEqual(Image.open(out / "coverage.png").getpixel((1, 0)), 128)
        self.assertTrue(verify_world.inspect(out / "packed-art.json")["passed"])

    def test_rejects_unsafe_masks_schema_and_resource_shapes(self):
        Image.new("RGB", (5, 3)).save(self.tmp / "rgb.png")
        with self.assertRaisesRegex(tool.RecipeError, "grayscale"):
            self.prepare(self.base() | {"coverageMask": "rgb.png"})
        with self.assertRaisesRegex(tool.RecipeError, "unknown"):
            self.prepare(self.base() | {"extra": 1}, "unknown")
        with self.assertRaisesRegex(tool.RecipeError, "version"):
            self.prepare({"version": True, "source": "source.png"}, "boolean-version")
        with self.assertRaisesRegex(tool.RecipeError, "relative"):
            self.prepare({"version": 1, "source": str((self.tmp / "source.png").resolve())}, "absolute")
        with self.assertRaisesRegex(tool.RecipeError, "chunk count"):
            self.prepare(self.base() | {"output": {"width": 65, "height": 64, "mode": "chunks", "chunkSize": [1, 1], "outOfBounds": "transparent"}}, "chunks")
        with self.assertRaisesRegex(tool.RecipeError, "per-axis"):
            self.prepare(self.base() | {"output": {"mode": "chunks", "chunkSize": [8192, 1], "gutter": 1}}, "gutter")

    def test_deterministic_outputs(self):
        recipe = self.base() | {"output": {"mode": "chunks", "chunkSize": [2, 2], "gutter": 1}}
        first = self.prepare(recipe, "first")
        second = self.prepare(recipe, "second")
        names = ["ground.png", "manifest.json", "packed-art.json", "provenance.json"]
        self.assertEqual([hashlib.sha256((first / name).read_bytes()).hexdigest() for name in names], [hashlib.sha256((second / name).read_bytes()).hexdigest() for name in names])

    def test_bom_recipe_and_concurrent_source_change(self):
        self.recipe.write_text(json.dumps(self.base()), encoding="utf-8-sig")
        tool.run(self.recipe, self.tmp / "bom")
        self.assertTrue((self.tmp / "bom/manifest.json").exists())
        read_png = tool.png

        def read_and_change(path, name):
            result = read_png(path, name)
            if name == "source":
                Image.new("RGBA", result.size, (99, 88, 77, 255)).save(path)
            return result

        with patch.object(tool, "png", side_effect=read_and_change):
            with self.assertRaisesRegex(tool.RecipeError, "input changed"):
                tool.run(self.recipe, self.tmp / "changed")
        self.assertFalse((self.tmp / "changed/manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
