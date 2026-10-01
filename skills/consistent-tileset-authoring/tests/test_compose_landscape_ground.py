import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

SCRIPT = Path(__file__).parents[1] / "scripts" / "compose-landscape-ground.py"
SPEC = importlib.util.spec_from_file_location("compose_landscape_ground", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MODULE)


def write_png(path, array): Image.fromarray(array).save(path)
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


class ComposeLandscapeGroundTests(unittest.TestCase):
    def fixture(self):
        root = Path(tempfile.mkdtemp())
        base = np.zeros((8, 8, 4), dtype=np.uint8); base[:] = [20, 100, 30, 255]
        write_png(root / "ground.png", base)
        packed = {"version": 1, "groups": [{"id": "base", "kind": "surface", "composition": {"reference": "ground.png", "origin": [0, 0], "sourceScale": 1}}]}
        (root / "packed-art.json").write_text(json.dumps(packed), "utf8")
        road = np.zeros((8, 8), dtype=np.uint8); road[2:6, 1:7] = 255
        water = np.zeros((8, 8), dtype=np.uint8); water[0, 4] = 255
        edge = np.zeros((8, 8), dtype=np.uint8); edge[2:4, 0:2] = 255
        underlay = np.zeros((8, 8), dtype=np.uint8); underlay[0:2, 3:5] = 255
        for name, data in {"road": road, "water": water, "edge": edge, "underlay": underlay}.items(): write_png(root / f"{name}.png", data)
        (root / "layout.json").write_text('{"host":"synthetic"}', "utf8")
        masks = {name: {"path": f"{name}.png", "sha256": digest(root / f"{name}.png")} for name in ["road", "water", "edge", "underlay"]}; masks["road"]["semantic"] = "road"; masks["water"]["semantic"] = "water"
        geometry = {"version": 1, "coordinateSpace": "projected-pixels", "projection": "host-isometric", "origin": [0, 0], "canvas": [8, 8], "masks": masks, "layout": {"path": "layout.json", "sha256": digest(root / "layout.json")}, "instances": [{"id": "tree-1", "anchor": [3, 0], "transform": {"scale": [2, 2]}, "contactId": "tree-ground"}]}
        (root / "geometry.json").write_text(json.dumps(geometry), "utf8")
        contact = np.zeros((2, 2, 4), dtype=np.uint8); contact[:] = [200, 80, 20, 255]; write_png(root / "contact.png", contact)
        earth = np.zeros((8, 8, 4), dtype=np.uint8); earth[:] = [120, 70, 20, 255]; write_png(root / "earth.png", earth)
        patch = np.zeros((1, 1, 4), dtype=np.uint8); patch[:] = [10, 10, 200, 255]; write_png(root / "tree-underlay.png", patch)
        recipe = {"version": 1, "geometrySource": "geometry.json", "surface": {"packedArt": "packed-art.json", "groundPng": "ground.png"}, "regionalMaterials": {"earth": "earth.png"}, "regionalPaths": [{"id": "main", "mask": "road", "material": "earth"}], "contacts": [{"id": "road-west", "kind": "pathExterior", "insideMask": "road", "outsideMask": "edge", "allowedMask": "edge", "orientation": "west", "edgeWidth": 1, "asset": "contact.png", "anchor": [1, 3], "assetAnchor": [1, 1]}], "protectedMasks": ["road", "water"], "underlays": [{"id": "tree-ground", "instanceId": "tree-1", "family": "tree", "asset": "tree-underlay.png", "assetAnchor": [0, 0], "exportScale": [2, 2], "allowedMask": "underlay"}]}
        path = root / "recipe.json"; path.write_text(json.dumps(recipe), "utf8")
        return root, path, recipe

    def test_composes_binder_surface_deterministically_and_preserves_protected_pixels(self):
        root, recipe_path, _ = self.fixture()
        first = MODULE.run(recipe_path, root / "one")
        second = MODULE.run(recipe_path, root / "two")
        self.assertEqual((root / "one" / "ground.png").read_bytes(), (root / "two" / "ground.png").read_bytes())
        self.assertEqual(first, second)
        image = np.array(Image.open(root / "one" / "ground.png").convert("RGBA"))
        self.assertTrue(np.array_equal(image[2, 1], [200, 80, 20, 255]))
        self.assertTrue(np.array_equal(image[0, 3], [10, 10, 200, 255]))
        self.assertTrue(np.array_equal(image[0, 4], [20, 100, 30, 255]))  # protected water remains base pixels
        packed = json.loads((root / "one" / "packed-art.json").read_text("utf8"))
        self.assertEqual(packed["groups"][0]["composition"]["reference"], "ground.png")
        self.assertEqual(first["passOrder"], ["baseSurface", "regionalContacts", "objectUnderlays"])
        self.assertEqual(first["geometrySource"], "geometry.json")
        self.assertEqual(first["underlays"][0]["scale"], [2, 2])
        self.assertEqual(first["recipeSha256"], digest(recipe_path))
        self.assertEqual(first["inputHashes"]["contact.png"], digest(root / "contact.png"))
        self.assertEqual(first["inputHashes"]["geometry.json"], digest(root / "geometry.json"))
        self.assertTrue(np.array_equal(image[4, 4], [120, 70, 20, 255]))  # regional material replaces base through path mask

    def test_rejects_internal_path_contact_before_writing(self):
        root, recipe_path, recipe = self.fixture()
        recipe["contacts"][0]["allowedMask"] = "road"
        recipe_path.write_text(json.dumps(recipe), "utf8")
        with self.assertRaisesRegex(ValueError, "internal regional-path"):
            MODULE.run(recipe_path, root / "bad")
        self.assertFalse((root / "bad").exists())

    def test_rejects_surface_origin_drift(self):
        root, recipe_path, recipe = self.fixture()
        packed = json.loads((root / "packed-art.json").read_text("utf8")); packed["groups"][0]["composition"]["origin"] = [1, 0]
        (root / "packed-art.json").write_text(json.dumps(packed), "utf8")
        with self.assertRaisesRegex(ValueError, "origin must exactly match"):
            MODULE.run(recipe_path, root / "origin-bad")

    def test_rejects_missing_explicit_export_scale(self):
        root, recipe_path, recipe = self.fixture()
        del recipe["underlays"][0]["exportScale"]
        recipe_path.write_text(json.dumps(recipe), "utf8")
        with self.assertRaisesRegex(ValueError, "assetAnchor and exportScale"):
            MODULE.run(recipe_path, root / "scale-bad")

    def test_rejects_semantic_road_remote_contact_and_overlap(self):
        root, recipe_path, recipe = self.fixture(); geometry = json.loads((root / "geometry.json").read_text())
        extra = np.zeros((8, 8), dtype=np.uint8); extra[7, 7] = 255; write_png(root / "other-road.png", extra)
        geometry["masks"]["otherRoad"] = {"path": "other-road.png", "sha256": digest(root / "other-road.png"), "semantic": "road"}; (root / "geometry.json").write_text(json.dumps(geometry))
        with self.assertRaisesRegex(ValueError, "semantic road/water"):
            MODULE.run(recipe_path, root / "semantic-bad")
        root, recipe_path, recipe = self.fixture(); edge = np.array(Image.open(root / "edge.png")); edge[6:8, 6:8] = 255; write_png(root / "edge.png", edge)
        geometry = json.loads((root / "geometry.json").read_text()); geometry["masks"]["edge"]["sha256"] = digest(root / "edge.png"); (root / "geometry.json").write_text(json.dumps(geometry)); recipe["contacts"][0]["anchor"] = [7, 7]; recipe_path.write_text(json.dumps(recipe))
        with self.assertRaisesRegex(ValueError, "directional exterior band"):
            MODULE.run(recipe_path, root / "remote-bad")
        root, recipe_path, recipe = self.fixture(); duplicate = dict(recipe["contacts"][0]); duplicate["id"] = "overlap"; recipe["contacts"].append(duplicate); recipe_path.write_text(json.dumps(recipe))
        with self.assertRaisesRegex(ValueError, "overlap"):
            MODULE.run(recipe_path, root / "overlap-bad")

    def test_t_junction_missing_mask_bounds_and_project_root(self):
        root, recipe_path, recipe = self.fixture(); road = np.array(Image.open(root / "road.png")); road[:, 3:5] = 255; write_png(root / "road.png", road)
        geometry = json.loads((root / "geometry.json").read_text()); geometry["masks"]["road"]["sha256"] = digest(root / "road.png"); (root / "geometry.json").write_text(json.dumps(geometry)); recipe["contacts"][0]["allowedMask"] = "road"; recipe_path.write_text(json.dumps(recipe))
        with self.assertRaisesRegex(ValueError, "internal regional-path"):
            MODULE.run(recipe_path, root / "junction-bad")
        root, recipe_path, _ = self.fixture(); (root / "edge.png").unlink()
        with self.assertRaisesRegex(ValueError, "missing or exceeds"):
            MODULE.run(recipe_path, root / "missing-bad")
        root, recipe_path, _ = self.fixture(); (root / "edge.png").write_bytes(b"0" * (MODULE.MAX_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "missing or exceeds"):
            MODULE.run(recipe_path, root / "large-bad")
        root, recipe_path, _ = self.fixture(); nested = root / "nested"; nested.mkdir()
        for item in root.iterdir():
            if item != nested: shutil.copy2(item, nested / item.name)
        report = MODULE.run(nested / "recipe.json", root / "out", root)
        self.assertEqual(report["geometrySource"], "nested/geometry.json")

    def test_source_scale_two_scales_pixels_and_uses_foot_anchor(self):
        root, recipe_path, _ = self.fixture(); packed = json.loads((root / "packed-art.json").read_text()); packed["groups"][0]["composition"]["sourceScale"] = 2; (root / "packed-art.json").write_text(json.dumps(packed))
        report = MODULE.run(recipe_path, root / "scaled")
        image = np.array(Image.open(root / "scaled" / "ground.png").convert("RGBA"))
        self.assertEqual(report["underlays"][0]["surfaceSourceScale"], 2)
        self.assertEqual(int(np.all(image[0:2, 3:5] == [10, 10, 200, 255], axis=2).sum()), 3)
        self.assertTrue(np.array_equal(image[0, 4], [20, 100, 30, 255]))

    def test_contact_intent_is_explicit_and_declared_contacts_cannot_be_omitted(self):
        root, recipe_path, recipe = self.fixture()
        geometry_path = root / "geometry.json"
        geometry = json.loads(geometry_path.read_text())
        del geometry["instances"][0]["contactId"]
        geometry_path.write_text(json.dumps(geometry))
        recipe["underlays"] = []
        recipe_path.write_text(json.dumps(recipe))
        with self.assertRaisesRegex(ValueError, "needs contactId"):
            MODULE.run(recipe_path, root / "missing-intent")
        geometry["instances"][0]["contactId"] = "tree-ground"
        geometry_path.write_text(json.dumps(geometry))
        with self.assertRaisesRegex(ValueError, "cover every declared"):
            MODULE.run(recipe_path, root / "omitted-contact")
        geometry["instances"][0]["contactId"] = None
        geometry_path.write_text(json.dumps(geometry))
        self.assertEqual(MODULE.run(recipe_path, root / "explicit-no-contact")["underlays"], [])


if __name__ == "__main__": unittest.main()
