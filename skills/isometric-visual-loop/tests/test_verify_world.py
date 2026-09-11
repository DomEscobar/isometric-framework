"""Synthetic regressions for packed-art defects and acceptance evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from PIL import Image, ImageDraw

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/verify-world.py"
SPEC = importlib.util.spec_from_file_location("verify_world", SCRIPT)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)
PREPARER = SCRIPT.parents[2] / "consistent-tileset-authoring" / "scripts" / "prepare-ground.py"
PREPARER_SPEC = importlib.util.spec_from_file_location("prepare_ground", PREPARER)
preparer = importlib.util.module_from_spec(PREPARER_SPEC)
PREPARER_SPEC.loader.exec_module(preparer)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / "game"
        self.game.mkdir()
        self.art = self.game / "art.json"
        self.manifest = self.game / "manifest.json"
        self.image = self.game / "sheet.png"
        atlas = Image.new("RGBA", (32, 16))
        draw = ImageDraw.Draw(atlas)
        draw.rectangle((5, 4, 10, 12), fill=(30, 90, 50, 255))
        draw.rectangle((21, 4, 26, 12), fill=(60, 120, 80, 255))
        atlas.save(self.image)
        self.assets = {"images": {"actor": {"url": "sheet.png"}},
                       "textures": {f"pose-{i}": {"image": "actor", "frame": {"x": i*16, "y": 0, "width": 16, "height": 16}, "anchor": {"x": .5, "y": .8125}} for i in range(2)},
                       "animations": {"walk-ne": {"frames": ["pose-0", "pose-1"], "fps": 6, "loop": True}}}
        self.check = {"version": 1, "manifest": "manifest.json", "groups": [{"id": "actor", "kind": "cutout", "clips": ["walk-ne"], "minDistinctFrames": 2, "margin": 1, "maxComponents": 1, "bounds": [5, 8, 8, 10]}]}
        self.save(self.manifest, self.assets)
        self.save(self.art, self.check)
        self.plan = self.game / "acceptance.json"
        self.plan_data = {"version": 1, "root": "..", "inputRoots": ["game"], "artChecks": ["game/art.json"], "reviewMode": "independent", "requirements": [
            {"id": "appearance", "description": "Whole actor and readable scene", "domain": "visual", "views": ["desktop", "mobile"]},
            {"id": "walk", "description": "Stable NE walking cycle", "domain": "motion", "views": ["desktop"]}]}
        self.save(self.plan, self.plan_data)
        self.baseline, self.candidate, self.review = [self.root / f"{s}.json" for s in ("baseline", "candidate", "review")]

    def save(self, path, data):
        path.write_text(json.dumps(data), encoding="utf-8")

    def receipt(self):
        gate.freeze(self.plan, self.baseline)
        gate.snapshot(self.baseline, self.candidate)
        # Fixture media bytes validate receipt plumbing, not real media quality.
        for name in ("desktop.png", "mobile.png", "walk.webm"):
            (self.root / name).write_bytes(b"synthetic evidence for hash tests")
        self.review_data = {"candidateSha256": gate.digest(self.candidate), "reviewMode": "independent", "verdicts": [
            {"id": "appearance", "status": "pass", "reviewer": "fixture-reviewer", "notes": "Inspected scene and packed frames", "evidence": [self.evidence("desktop.png", "image", "desktop"), self.evidence("mobile.png", "image", "mobile")]},
            {"id": "walk", "status": "pass", "reviewer": "fixture-reviewer", "notes": "Inspected movement and wrap", "evidence": [self.evidence("walk.webm", "motion", "desktop")]}]}
        self.save(self.review, self.review_data)

    def evidence(self, name, kind, view):
        return {"path": name, "sha256": gate.digest(self.root / name), "kind": kind, "view": view}

    def test_good_art_and_full_fresh_review(self):
        report = gate.inspect(self.art)
        self.assertTrue(report["passed"])
        before = self.image.read_bytes()
        gate.preview(report, self.root / "preview.html")
        self.assertIn("Packed art inspection", (self.root / "preview.html").read_text())
        self.assertEqual(before, self.image.read_bytes())
        self.receipt()
        self.assertTrue(gate.accept(self.baseline, self.candidate, self.review)["passed"])

    def test_contract_change_blocks_existing_baseline(self):
        contract = self.root / "PROJECT_CONTRACT.md"
        contract.write_text("A complete playable world", encoding="utf-8")
        self.plan_data["contract"] = "PROJECT_CONTRACT.md"
        self.save(self.plan, self.plan_data)
        gate.freeze(self.plan, self.baseline)
        gate.protected(self.baseline)
        contract.write_text("Only one decorative scene", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Protected project contract changed"):
            gate.protected(self.baseline)

    def test_missing_contract_rejected_before_freeze(self):
        self.plan_data["contract"] = "missing.md"
        self.save(self.plan, self.plan_data)
        with self.assertRaisesRegex(ValueError, "Contract must be"):
            gate.freeze(self.plan, self.baseline)
        self.assertFalse(self.baseline.exists())

    def test_complete_documented_plan_has_valid_production_coverage(self):
        example = SCRIPT.parent.parent / "references/acceptance-plan.example.json"
        plan = gate.read(example)
        (self.root / "PROJECT_CONTRACT.md").write_text("Illustrative test scope", encoding="utf-8")
        self.save(self.plan, plan)
        _, validated, _ = gate.plan_state(self.plan)
        self.assertEqual(validated["version"], 3)
        self.assertEqual(set(c["stage"] for c in validated["production"]["checks"]),
                         set(gate.production_tools().STAGES))

    def test_wide_assembly_keeps_pixel_budget_and_crop_padding(self):
        atlas = Image.new("RGBA", (1152, 16))
        ImageDraw.Draw(atlas).rectangle((2, 2, 1149, 13), fill=(30, 90, 120, 255))
        atlas.save(self.image)
        self.assets["textures"] = {"strip": {"image": "actor"}}
        self.assets["animations"] = {}
        self.check["groups"] = [{"id": "joined-strip", "kind": "cutout", "textures": ["strip"],
                                 "margin": 1, "bounds": [1100, 10, 1152, 16]}]
        self.save(self.manifest, self.assets)
        self.save(self.art, self.check)
        self.assertTrue(gate.inspect(self.art)["passed"])
        # Wide assemblies do not waive protected transparent margins.
        ImageDraw.Draw(atlas).rectangle((0, 2, 1149, 13), fill=(30, 90, 120, 255))
        atlas.save(self.image)
        self.assertFalse(gate.inspect(self.art)["passed"])
        # The previous 1024-square pixel budget remains the upper bound.
        Image.new("RGBA", (2048, 1024)).save(self.image)
        with self.assertRaisesRegex(ValueError, "1048576 pixels"):
            gate.inspect(self.art)
        Image.new("RGBA", (4097, 2)).save(self.image)
        with self.assertRaisesRegex(ValueError, "4096 per side"):
            gate.inspect(self.art)

    def test_surface_reconstructs_exact_rgba_and_keeps_cutout_rules(self):
        reference = Image.new("RGBA", (8, 4), (12, 34, 56, 0))
        for y in range(4):
            for x in range(8): reference.putpixel((x, y), (x * 20, y * 40, 90, 255 if x != 3 else 0))
        reference.save(self.game / "ground.png")
        reference.crop((0, 0, 4, 4)).save(self.image)
        reference.crop((4, 0, 8, 4)).save(self.game / "right.png")
        self.assets = {"images": {"left": {"url": "sheet.png"}, "right": {"url": "right.png"}},
                       "textures": {"left": {"image": "left", "frame": {"x": 0, "y": 0, "width": 4, "height": 4}, "anchor": {"x": 0, "y": 0}},
                                    "right": {"image": "right", "frame": {"x": 0, "y": 0, "width": 4, "height": 4}, "anchor": {"x": 0, "y": 0}}},
                       "placements": {"left": {"x": 11, "y": -4}, "right": {"x": 15, "y": -4}}}
        self.check["groups"] = [{"id": "ground", "kind": "surface", "textures": ["left", "right"], "composition": {"reference": "ground.png", "origin": [11, -4]}}]
        self.save(self.manifest, self.assets); self.save(self.art, self.check)
        report = gate.inspect(self.art)
        self.assertTrue(report["passed"]); self.assertIn(str((self.game / "ground.png").resolve()), report["inputs"])
        self.assets["placements"]["another-group"] = {"x": 100, "y": 100}
        self.save(self.manifest, self.assets)
        other_group_report = gate.inspect(self.art)
        self.assertTrue(other_group_report["passed"])
        self.assertNotIn("another-group", other_group_report["surfaces"]["ground"]["placements"])
        self.check["groups"][0]["composition"]["origin"] = [21, 9]
        self.assets["placements"] = {"left": {"x": 21, "y": 9}, "right": {"x": 25, "y": 9}}
        self.save(self.manifest, self.assets); self.save(self.art, self.check)
        self.assertTrue(gate.inspect(self.art)["passed"])
        mask = Image.frombytes("L", reference.size, reference.getchannel("A").tobytes()); mask.putpixel((3, 0), 255); mask.save(self.game / "coverage.png")
        self.check["groups"][0]["coverageMask"] = "coverage.png"; self.save(self.art, self.check)
        self.assertIn("luminance", str(gate.inspect(self.art)["findings"]))
        self.check["groups"][0].pop("coverageMask"); self.save(self.art, self.check)
        self.assets["placements"]["right"]["x"] = 24; self.save(self.manifest, self.assets)
        self.assertIn("overlaps", str(gate.inspect(self.art)["findings"]))
        self.assets["placements"]["right"]["x"] = 25; self.save(self.manifest, self.assets)
        with Image.open(self.game / "right.png") as im: corrupted = im.copy()
        corrupted.putpixel((0, 0), (9, 8, 7, 0)); corrupted.save(self.game / "right.png")
        self.assertIn("RGBA", str(gate.inspect(self.art)["findings"]))
        # Surface edge opacity is intentional; this must not relax a cutout's margin check.
        self.check["groups"] = [{"id": "actor", "kind": "cutout", "textures": ["left"], "margin": 1}]; self.save(self.art, self.check)
        self.assertFalse(gate.inspect(self.art)["passed"])

    def test_surface_inspects_prepare_ground_chunk_manifest(self):
        source = Image.new("RGBA", (5, 3), (20, 40, 60, 255)); source.putpixel((2, 1), (1, 2, 3, 0)); source.save(self.root / "source.png")
        Image.frombytes("L", source.size, source.getchannel("A").tobytes()).save(self.root / "coverage.png")
        recipe = {"version": 1, "source": "source.png", "coverageMask": "coverage.png",
                  "output": {"mode": "chunks", "chunkSize": [3, 2], "gutter": 1, "origin": [-7, 5]}}
        recipe_path = self.root / "recipe.json"; self.save(recipe_path, recipe)
        output = self.root / "prepared"; preparer.run(recipe_path, output)
        report = gate.inspect(output / "packed-art.json")
        self.assertTrue(report["passed"], report["findings"])

    def test_surface_mask_failure_and_evidence_attachment_resets_verdict(self):
        self.receipt()
        mask = Image.new("RGBA", (32, 16), (10, 10, 10, 255)); mask.save(self.root / "mask.png")
        self.assets["textures"]["pose-0"]["anchor"] = {"x": 0, "y": 0}; self.save(self.manifest, self.assets)
        self.check["groups"].append({"id": "surface", "kind": "surface", "textures": ["pose-0"], "coverageMask": "mask.png"})
        self.save(self.art, self.check)
        with self.assertRaisesRegex(ValueError, "coverageMask requires"):
            gate.inspect(self.art)
        self.check["groups"].pop(); self.save(self.art, self.check)
        Image.new("RGBA", (2, 2), (1, 2, 3, 255)).save(self.root / "desktop.png")
        attached = self.root / "review-attached.json"
        result = gate.attach_evidence(self.baseline, self.candidate, self.review, "appearance", "desktop", self.root / "desktop.png", attached)
        self.assertEqual(result["kind"], "image")
        changed = gate.read(attached)
        self.assertEqual(changed["verdicts"][0]["status"], "unverified")
        self.assertEqual(changed["verdicts"][0]["evidence"][-1]["sha256"], gate.digest(self.root / "desktop.png"))
        self.assertEqual(changed["candidateSha256"], self.review_data["candidateSha256"])
        with self.assertRaisesRegex(ValueError, "Unknown protected view"):
            gate.attach_evidence(self.baseline, self.candidate, self.review, "appearance", "missing", self.root / "desktop.png", self.root / "bad.json")

    def test_calibration_subset_does_not_reduce_final_acceptance(self):
        self.check["groups"].append({"id": "future-creature", "kind": "cutout", "clips": ["not-built-yet"]})
        self.save(self.art, self.check)
        self.receipt()
        report = gate.inspect(self.art, ["actor"])
        self.assertTrue(report["passed"])
        self.assertEqual(report["scope"], {"mode": "calibration", "groups": ["actor"], "plannedGroups": ["actor", "future-creature"]})
        for selected in ([], ["missing"], ["actor", "actor"]):
            with self.subTest(selected=selected), self.assertRaisesRegex(ValueError, "calibration group"):
                gate.inspect(self.art, selected)
        with self.assertRaisesRegex(ValueError, "Missing required clip"):
            gate.accept(self.baseline, self.candidate, self.review)
        command = subprocess.run([sys.executable, str(SCRIPT), "inspect", str(self.art), "--groups", "actor", "--out", str(self.root / "calibration")], capture_output=True, text=True)
        self.assertEqual(command.returncode, 0, command.stderr)
        self.assertEqual(json.loads(command.stdout)["scope"]["mode"], "calibration")
        self.assertIn("CALIBRATION SUBSET", (self.root / "calibration/preview.html").read_text())

    def test_neighbor_fragment_and_cut_edge_are_rejected(self):
        with Image.open(self.image) as source:
            image = source.copy()
        image.putpixel((14, 6), (255, 0, 0, 255))
        image.putpixel((14, 7), (255, 0, 0, 255))
        image.putpixel((0, 10), (255, 0, 0, 255))
        image.save(self.image)
        report = gate.inspect(self.art)
        self.assertFalse(report["passed"])
        messages = str(report["findings"])
        self.assertIn("components", messages)
        self.assertIn("crop margin", messages)

    def test_runtime_clip_defaults_and_invalid_anchor(self):
        self.assets["animations"]["walk-ne"].pop("fps")
        self.assets["animations"]["walk-ne"].pop("loop")
        self.save(self.manifest, self.assets)
        clip = gate.inspect(self.art)["clips"]["walk-ne"]
        self.assertEqual(clip["fps"], 8)
        self.assertTrue(clip["loop"])
        self.assets["textures"]["pose-0"]["anchor"] = {"x": "bad", "y": 1}
        self.save(self.manifest, self.assets)
        with self.assertRaisesRegex(ValueError, "Invalid anchor"):
            gate.inspect(self.art)

    def test_declared_disconnected_effect_can_be_reviewed(self):
        with Image.open(self.image) as source:
            image = source.copy()
        image.putpixel((13, 6), (255, 0, 0, 255))
        image.putpixel((13, 7), (255, 0, 0, 255))
        image.save(self.image)
        self.check["groups"][0].update(maxComponents=2, bounds=[5, 8, 10, 10])
        self.save(self.art, self.check)
        self.assertTrue(gate.inspect(self.art)["passed"])

    def test_rectangular_water_rejected_diamond_accepted(self):
        self.check["groups"] = [{"id": "water", "kind": "diamond-overlay", "textures": ["pose-0"]}]
        self.save(self.art, self.check)
        Image.new("RGBA", (32, 16), (0, 100, 200, 255)).save(self.image)
        self.assertFalse(gate.inspect(self.art)["passed"])
        image = Image.new("RGBA", (32, 16))
        for y in range(16):
            for x in range(16):
                if abs((x+.5-8)/8)+abs((y+.5-8)/8) <= 1:
                    image.putpixel((x, y), (0, 100, 200, 255))
        image.save(self.image)
        self.assertTrue(gate.inspect(self.art)["passed"])

    def test_repeated_pixels_are_not_multiple_animation_frames(self):
        with Image.open(self.image) as source:
            image = source.copy()
        image.paste(image.crop((0, 0, 16, 16)), (16, 0))
        image.save(self.image)
        self.assertIn("distinct decoded frames", str(gate.inspect(self.art)["findings"]))
        self.assets["animations"].clear()
        self.save(self.manifest, self.assets)
        with self.assertRaisesRegex(ValueError, "Missing required clip"):
            gate.inspect(self.art)

    def test_stale_sources_and_evidence_do_not_pass(self):
        self.receipt()
        extra = self.game / "new-rule.ts"
        extra.write_text("changed")
        with self.assertRaisesRegex(ValueError, "stale"):
            gate.accept(self.baseline, self.candidate, self.review)
        extra.unlink()
        (self.root / "walk.webm").write_bytes(b"overwritten capture")
        with self.assertRaisesRegex(ValueError, "changed evidence"):
            gate.accept(self.baseline, self.candidate, self.review)

    def test_fail_unverified_omitted_views_and_stills_cannot_accept_motion(self):
        self.receipt()
        original = copy.deepcopy(self.review_data)
        mutations = [lambda r: r["verdicts"][0].update(status="fail"),
                     lambda r: r["verdicts"][1].update(status="unverified"),
                     lambda r: r["verdicts"].pop(),
                     lambda r: r["verdicts"][0]["evidence"].pop(),
                     lambda r: r["verdicts"][1].update(evidence=[self.evidence("desktop.png", "image", "desktop")]),
                     lambda r: r.update(reviewMode="self"),
                     lambda r: r.update(candidateSha256="old")]
        for mutate in mutations:
            review = copy.deepcopy(original)
            mutate(review)
            self.save(self.review, review)
            with self.subTest(review=review), self.assertRaises(ValueError):
                gate.accept(self.baseline, self.candidate, self.review)

    def test_protected_requirements_and_art_thresholds_cannot_be_weakened(self):
        self.receipt()
        self.plan_data["requirements"].pop()
        self.save(self.plan, self.plan_data)
        with self.assertRaisesRegex(ValueError, "Protected plan changed"):
            gate.accept(self.baseline, self.candidate, self.review)
        self.plan_data["requirements"].append({"id": "walk", "description": "Stable NE walking cycle", "domain": "motion", "views": ["desktop"]})
        self.save(self.plan, self.plan_data)
        self.check["groups"][0]["maxComponents"] = 100
        self.save(self.art, self.check)
        with self.assertRaisesRegex(ValueError, "Protected art"):
            gate.snapshot(self.baseline, self.root / "new.json")

    def test_receipts_cannot_be_overwritten_or_written_inside_sources(self):
        self.receipt()
        with self.assertRaises(FileExistsError):
            gate.freeze(self.plan, self.baseline)
        with self.assertRaisesRegex(ValueError, "outside inputRoots"):
            gate.snapshot(self.baseline, self.game / "candidate.json")

    def test_accept_reruns_art_check_instead_of_trusting_a_pass_record(self):
        Image.new("RGBA", (32, 16), (10, 20, 30, 255)).save(self.image)
        self.receipt()
        with self.assertRaisesRegex(ValueError, "Packed art failed"):
            gate.accept(self.baseline, self.candidate, self.review)

    def test_cli_failure_retains_preview_and_positive_acceptance_exits_zero(self):
        self.receipt()
        accepted = subprocess.run([sys.executable, str(SCRIPT), "accept", str(self.baseline), str(self.candidate), str(self.review)], capture_output=True, text=True)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        Image.new("RGBA", (32, 16), (1, 2, 3, 255)).save(self.image)
        rejected = subprocess.run([sys.executable, str(SCRIPT), "inspect", str(self.art), "--out", str(self.root / "failed-art")], capture_output=True, text=True)
        self.assertEqual(rejected.returncode, 1, rejected.stderr)
        self.assertFalse(json.loads(rejected.stdout)["passed"])
        self.assertTrue((self.root / "failed-art/preview.html").exists())


if __name__ == "__main__":
    unittest.main()
