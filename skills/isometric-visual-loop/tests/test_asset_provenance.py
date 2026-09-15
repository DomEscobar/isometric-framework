import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import subprocess

from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "asset_provenance.py"
SPEC = importlib.util.spec_from_file_location("asset_provenance", SCRIPT)
gate = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(gate)


class AssetProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); (self.root / "host/art").mkdir(parents=True)
        image = Image.new("RGBA", (4, 4), (0, 0, 0, 0)); image.putpixel((1, 1), (30, 90, 40, 255)); image.save(self.root / "host/art/origin.png")
        image.save(self.root / "host/art/sheet.png")
        self.write("host/art/request.json", {"localJobId": "fixture", "outputSha256": self.hash("host/art/origin.png")})
        manifest = {"assets": {"images": {"hero": {"url": "sheet.png"}}, "textures": {"hero.idle.ne.0000": {"image": "hero", "frame": {"x": 0, "y": 0, "width": 4, "height": 4}, "anchor": {"x": .5, "y": 1}}}, "animations": {"hero.idle.ne": {"frames": ["hero.idle.ne.0000"], "fps": 1, "loop": True}}}}
        self.write("host/art/runtime.json", manifest)
        self.write("host/art/used.json", {"version": 1, "used": {category: {"images": ["hero"] if category == "character" else [], "textures": ["hero.idle.ne.0000"] if category == "character" else [], "animations": ["hero.idle.ne"] if category == "character" else []} for category in ("world", "character", "environment", "ui", "debug")}})
        self.write("host/art/ledger.json", {"version": 1, "images": {"hero": {"origin": self.origin(), "transforms": [{"path": "host/art/sheet.png", "sha256": self.hash("host/art/sheet.png")}] }}, "clips": {"hero.idle.ne": {"mode": "generated-facing", "selectedImage": self.origin()}}})
        self.plan = {"version": 4, "inputRoots": ["host"], "assetPolicy": {"version": 1, "sources": {"world": "generated", "character": "generated", "environment": "generated"}, "characterAnimation": {"animated": "image-to-video-extract-pack", "staticIdle": "generated-facing"}, "coverageLedger": "host/art/ledger.json", "runtime": {"manifest": "host/art/runtime.json", "binding": "host/art/used.json"}}}

    def hash(self, name): return hashlib.sha256((self.root / name).read_bytes()).hexdigest()
    def write(self, name, value): (self.root / name).write_text(json.dumps(value), encoding="utf-8")
    def origin(self): return {"kind": "generated", "record": {"path": "host/art/request.json", "sha256": self.hash("host/art/request.json")}, "output": {"path": "host/art/origin.png", "sha256": self.hash("host/art/origin.png")}}

    def test_static_generated_facing_matches_runtime_pixels(self):
        self.assertTrue(gate.verify(self.plan, self.root)["enforced"])
        image = Image.open(self.root / "host/art/sheet.png"); image.putpixel((1, 1), (31, 90, 40, 255)); image.save(self.root / "host/art/sheet.png")
        ledger = json.loads((self.root / "host/art/ledger.json").read_text()); ledger["images"]["hero"]["transforms"][-1]["sha256"] = self.hash("host/art/sheet.png"); self.write("host/art/ledger.json", ledger)
        with self.assertRaisesRegex(ValueError, "Static generated facing pixels"):
            gate.verify(self.plan, self.root)

    def test_legacy_policy_reports_unenforced(self):
        self.assertEqual(gate.validate_policy({"inputRoots": ["host"]}, self.root), {"enforced": False, "version": "legacy-v1-v3"})
        with self.assertRaisesRegex(ValueError, "require assetPolicy"):
            gate.validate_policy({"version": 4, "inputRoots": ["host"]}, self.root)

    def test_prepared_facing_retains_original_mask_crop_and_rejects_repaint(self):
        origin = self.origin()
        mask = Image.new("L", (4, 4), 255)
        mask.putpixel((1, 1), 128)
        mask.save(self.root / "host/art/mask.png")
        with Image.open(self.root / "host/art/origin.png") as raw:
            prepared = raw.crop((0, 0, 3, 3))
            prepared.putpixel((1, 1), (30, 90, 40, 128))
            prepared.save(self.root / "host/art/prepared.png")
        def evidence(name): return {"path": "host/art/" + name, "sha256": self.hash("host/art/" + name)}
        origin["prepared"] = {"image": evidence("prepared.png"), "mask": evidence("mask.png"),
                              "crop": {"x": 0, "y": 0, "width": 3, "height": 3}}
        self.assertEqual(gate._origin(self.root, self.plan, origin, "Facing"), self.root / "host/art/prepared.png")
        with Image.open(self.root / "host/art/prepared.png") as raw:
            raw.putpixel((1, 1), (99, 20, 30, 255)); raw.save(self.root / "host/art/prepared.png")
        origin["prepared"]["image"] = evidence("prepared.png")
        with self.assertRaisesRegex(ValueError, "prepared pixels differ"):
            gate._origin(self.root, self.plan, origin, "Facing")

    def test_environment_deterministic_animation_needs_generated_art_but_no_character_recipe(self):
        # Synthetic deterministic effect on the original generated-art fixture.
        with Image.open(self.root / "host/art/origin.png") as raw:
            atlas = Image.new("RGBA", (8, 4))
            atlas.paste(raw, (0, 0))
            dim = raw.copy(); dim.putpixel((1, 1), (15, 45, 20, 255))
            atlas.paste(dim, (4, 0)); atlas.save(self.root / "host/art/sheet.png")
        self.write("host/art/effect.json", {"method": "deterministic-brightness", "levels": [1, .5]})
        self.write("host/art/runtime.json", {"assets": {
            "images": {"glow": {"url": "sheet.png"}},
            "textures": {str(index): {"image": "glow", "frame": {"x": index * 4, "y": 0, "width": 4, "height": 4}} for index in range(2)},
            "animations": {"glow.pulse": {"frames": ["0", "1"], "fps": 2, "loop": True}}}})
        self.write("host/art/used.json", {"version": 1, "used": {
            category: {"images": ["glow"] if category == "environment" else [],
                       "textures": ["0", "1"] if category == "environment" else [],
                       "animations": ["glow.pulse"] if category == "environment" else []}
            for category in ("world", "character", "environment", "ui", "debug")}})
        self.write("host/art/ledger.json", {"version": 1, "clips": {}, "images": {
            "glow": {"origin": self.origin(), "transforms": [
                {"path": "host/art/effect.json", "sha256": self.hash("host/art/effect.json")},
                {"path": "host/art/sheet.png", "sha256": self.hash("host/art/sheet.png")}]}}})
        self.assertEqual(gate.verify(self.plan, self.root)["characterClips"], 0)

    def test_one_frame_walk_cannot_claim_static_idle_exception(self):
        manifest = json.loads((self.root / "host/art/runtime.json").read_text())
        manifest["assets"]["animations"] = {"hero.walk.ne": {"frames": ["hero.idle.ne.0000"], "fps": 6, "loop": True}}
        self.write("host/art/runtime.json", manifest)
        binding = json.loads((self.root / "host/art/used.json").read_text())
        binding["used"]["character"]["animations"] = ["hero.walk.ne"]; self.write("host/art/used.json", binding)
        ledger = json.loads((self.root / "host/art/ledger.json").read_text())
        ledger["clips"] = {"hero.walk.ne": {"mode": "generated-facing", "selectedImage": self.origin()}}; self.write("host/art/ledger.json", ledger)
        with self.assertRaisesRegex(ValueError, "Character clip ledger"):
            gate.verify(self.plan, self.root)


class AnimatedChainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.art = self.root / "host/art"; self.art.mkdir(parents=True)
        frames = self.art / "source-frames"; frames.mkdir()
        for index, color in enumerate(((220, 30, 20), (30, 220, 40), (20, 40, 220))):
            image = Image.new("RGB", (12, 12), (0, 0, 0)); image.putpixel((3 + index, 5), color); image.save(frames / f"frame-{index}.png")
        self.video = self.art / "motion.mkv"
        subprocess.run(["ffmpeg", "-v", "error", "-framerate", "6", "-i", str(frames / "frame-%d.png"), "-c:v", "ffv1", "-y", str(self.video)], check=True)
        self.facing = self.art / "facing.png"; Image.open(frames / "frame-0.png").convert("RGBA").save(self.facing)
        self.write("host/art/generation.json", {"localJobId": "generation-fixture", "outputSha256": self.sha(self.facing)})
        extractor = self.script("extract-video.py", "extractor")
        extractor.prepare(self.video, self.art / "review", "#000000", 0)
        recipe_path = self.art / "review/extraction.json"; recipe = self.read(recipe_path)
        recipe["selection"] = {"indices": [0, 1, 2], "fps": 6}; recipe["clip"] = {"imageId": "hero", "action": "walk", "direction": "ne", "loop": True, "anchor": {"x": .5, "y": 1}}
        self.write_path(recipe_path, recipe)
        extractor.export(recipe_path, self.art / "extract")
        packer = self.script("pack-sprites.py", "packer"); packed = packer.pack(self.art / "extract/sprite-pack.json", self.art / "packed")
        packed["assets"]["images"]["hero"]["url"] = "packed/sheet.png"; self.write("host/art/runtime.json", packed)
        self.clip = "hero.walk.ne"; assets = packed["assets"]
        self.write("host/art/used.json", {"version": 1, "used": {category: {"images": (["hero"] if category == "character" else []), "textures": (list(assets["textures"]) if category == "character" else []), "animations": ([self.clip] if category == "character" else [])} for category in ("world", "character", "environment", "ui", "debug")}})
        self.write("host/art/video-job.json", {"localJobId": "video-fixture", "provider": "fixture", "model": "ffv1-fixture", "selectedImageSha256": self.sha(self.facing), "videoSha256": self.sha(self.art / "review/source/motion.mkv")})
        origin = self.origin()
        self.write("host/art/ledger.json", {"version": 1, "images": {"hero": {"origin": origin, "transforms": [{"path": "host/art/packed/sheet.png", "sha256": self.sha(self.art / "packed/sheet.png")}]}}, "clips": {self.clip: {"mode": "image-to-video-extract-pack", "selectedImage": origin, "videoJob": self.evidence("host/art/video-job.json"), "recipe": self.evidence("host/art/review/extraction.json")}}})
        self.plan = {"version": 4, "inputRoots": ["host"], "assetPolicy": {"version": 1, "sources": {"world": "generated", "character": "generated", "environment": "generated"}, "characterAnimation": {"animated": "image-to-video-extract-pack", "staticIdle": "generated-facing"}, "coverageLedger": "host/art/ledger.json", "runtime": {"manifest": "host/art/runtime.json", "binding": "host/art/used.json"}}}

    def script(self, name, module):
        path = SCRIPT.parents[2] / "directional-sprite-authoring/scripts" / name; spec = importlib.util.spec_from_file_location(module, path); loaded = importlib.util.module_from_spec(spec); spec.loader.exec_module(loaded); return loaded
    def sha(self, path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    def read(self, path): return json.loads(Path(path).read_text())
    def write_path(self, path, value): Path(path).write_text(json.dumps(value), encoding="utf-8")
    def write(self, name, value): self.write_path(self.root / name, value)
    def evidence(self, name): return {"path": name, "sha256": self.sha(self.root / name)}
    def origin(self): return {"kind": "generated", "record": self.evidence("host/art/generation.json"), "output": self.evidence("host/art/facing.png")}
    def ledger(self): return self.read(self.art / "ledger.json")
    def save_ledger(self, value): self.write("host/art/ledger.json", value)
    def refresh_recipe(self):
        ledger = self.ledger(); ledger["clips"][self.clip]["recipe"] = self.evidence("host/art/review/extraction.json"); self.save_ledger(ledger)

    def test_valid_replayed_video_chain(self): self.assertEqual(gate.verify(self.plan, self.root)["characterClips"], 1)

    def test_environment_animation_is_not_forced_through_character_i2v_ledger(self):
        binding = self.read(self.art / "used.json")
        binding["used"]["environment"] = binding["used"]["character"]
        binding["used"]["character"] = {"images": [], "textures": [], "animations": []}; self.write("host/art/used.json", binding)
        ledger = self.ledger(); ledger["clips"] = {}; self.save_ledger(ledger)
        self.assertEqual(gate.verify(self.plan, self.root)["characterClips"], 0)

    def test_rejects_rehashed_recipe_timestamp_and_frame_tampering(self):
        prep = self.read(self.art / "review/preparation.json"); prep["decodedFrames"][1]["timeSeconds"] += .01; self.write_path(self.art / "review/preparation.json", prep)
        recipe = self.read(self.art / "review/extraction.json"); recipe["preparation"]["sha256"] = self.sha(self.art / "review/preparation.json"); self.write_path(self.art / "review/extraction.json", recipe); self.refresh_recipe()
        with self.assertRaisesRegex(ValueError, "timestamps"):
            gate.verify(self.plan, self.root)

    def test_rejects_changed_source_and_rehashed_fabricated_decoded_frame(self):
        source = self.art / "review/source/motion.mkv"; source.write_bytes(source.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "source hash"):
            gate.verify(self.plan, self.root)
        # Fresh fixture state is needed because a source mismatch is intentionally terminal.
        self.setUp()
        frame = self.art / "review/frames/frame-000001.png"; image = Image.open(frame); image.putpixel((4, 5), (99, 88, 77, 255)); image.save(frame)
        prep = self.read(self.art / "review/preparation.json"); prep["decodedFrames"][1]["sha256"] = self.sha(frame); self.write_path(self.art / "review/preparation.json", prep)
        recipe = self.read(self.art / "review/extraction.json"); recipe["preparation"]["sha256"] = self.sha(self.art / "review/preparation.json"); self.write_path(self.art / "review/extraction.json", recipe); self.refresh_recipe()
        with self.assertRaisesRegex(ValueError, "pixels differ"):
            gate.verify(self.plan, self.root)

    def test_rejects_runtime_fps_anchor_pixels_and_category_changes(self):
        original = (self.art / "runtime.json").read_text()
        for mutate, text in ((lambda runtime: runtime["assets"]["animations"][self.clip].update(fps=7), "Packed clip"),
                             (lambda runtime: runtime["assets"]["textures"][runtime["assets"]["animations"][self.clip]["frames"][0]].update(anchor={"x": 0, "y": 1}), "anchor")):
            runtime = json.loads(original); mutate(runtime); self.write("host/art/runtime.json", runtime)
            with self.assertRaisesRegex(ValueError, text): gate.verify(self.plan, self.root)
        (self.art / "runtime.json").write_text(original)
        sheet = Image.open(self.art / "packed/sheet.png"); sheet.putpixel((3, 3), (1, 2, 3, 255)); sheet.save(self.art / "packed/sheet.png")
        ledger = self.ledger(); ledger["images"]["hero"]["transforms"][-1]["sha256"] = self.sha(self.art / "packed/sheet.png"); self.save_ledger(ledger)
        with self.assertRaisesRegex(ValueError, "frame pixels"): gate.verify(self.plan, self.root)

    def test_rejects_all_debug_classification_and_unprotected_runtime_source(self):
        binding = self.read(self.art / "used.json")
        binding["used"]["debug"] = binding["used"]["character"]
        binding["used"]["character"] = {"images": [], "textures": [], "animations": []}; self.write("host/art/used.json", binding)
        with self.assertRaisesRegex(ValueError, "generated world, character or environment"):
            gate.verify(self.plan, self.root)
        self.setUp(); self.plan["inputRoots"] = ["host/art/review"]
        with self.assertRaisesRegex(ValueError, "under inputRoots"):
            gate.verify(self.plan, self.root)


if __name__ == "__main__": unittest.main()
