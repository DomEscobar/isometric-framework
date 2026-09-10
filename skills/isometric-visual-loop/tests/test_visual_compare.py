"""Comparison bundle, target protection and reviewer coverage regressions."""
import copy
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
import test_verify_world as fixtures

gate = fixtures.gate


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.WorkflowTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        f = self.f
        f.plan_data["version"] = 2
        f.plan_data["requirements"] = f.plan_data["requirements"][:1]
        f.plan_data["comparisons"] = [{"id": view, "requirements": ["appearance"], "view": view,
                                      "role": "style", "reference": "reference.png", "focus": "Whole shape and consistent pixel treatment"}
                                     for view in ("desktop", "mobile")]
        (f.root / "reference.png").write_bytes(f.image.read_bytes())
        f.save(f.plan, f.plan_data)
        self.captures = f.root / "captures.json"
        (f.root / "capture.png").write_bytes(f.image.read_bytes())
        f.save(self.captures, {v: {"path": "capture.png", "captureNotes": "Fixed camera, neutral test state"} for v in ("desktop", "mobile")})
        self.tool = gate.comparison_tools()
        self.adapter = SimpleNamespace(protected=gate.protected, source_hashes=gate.source_hashes, local=gate.local)

    def build(self, name="round-1", previous=None):
        f = self.f
        if not f.baseline.exists():
            gate.freeze(f.plan, f.baseline)
            gate.snapshot(f.baseline, f.candidate)
        result = self.tool.build(self.adapter, f.baseline, f.candidate, self.captures, f.root / name, previous)
        return Path(result["review"])

    def reviewed(self, template, failed=False):
        value = gate.read(template)
        for verdict in value["verdicts"]:
            verdict.update(status="pass", reviewer="test-reviewer", notes="Inspected both images")
        value["comparison"]["reviewer"] = "test-reviewer"
        for a in value["comparison"]["assessments"]:
            status = "fail" if failed else "pass"
            a.update(status=status, observations=[{"id": a["id"] + "-shape", "status": status,
                "currentRegion": [1, 1, 8, 8], "referenceRegion": [1, 1, 8, 8],
                "difference": "Shape differs" if failed else "Whole shape agrees", "repair": "Restore the missing silhouette" if failed else ""}])
        for resolution in value["comparison"]["resolutions"]:
            resolution.update(status="open" if failed else "resolved", reason="Reinspected this area")
        path = template.with_name("review.json")
        self.f.save(path, value)
        return path

    def test_complete_visual_review_and_cli_bundle(self):
        f = self.f
        template = self.build()
        self.assertIn("Visual comparison", template.with_name("board.html").read_text())
        review = self.reviewed(template)
        result = gate.accept(f.baseline, f.candidate, review)
        self.assertEqual(result["visualComparisons"], 2)
        command = subprocess.run([sys.executable, str(fixtures.SCRIPT), "compare", str(f.baseline), str(f.candidate), str(self.captures), "--out", str(f.root / "cli-round")], capture_output=True, text=True)
        self.assertEqual(command.returncode, 0, command.stderr)
        self.assertTrue(Path(json.loads(command.stdout)["board"]).exists())

    def test_v2_cannot_omit_target_coverage(self):
        self.f.plan_data["comparisons"].pop()
        self.f.save(self.f.plan, self.f.plan_data)
        with self.assertRaisesRegex(ValueError, "Every visual"):
            gate.freeze(self.f.plan, self.f.baseline)

    def test_review_packet_cannot_weaken_protected_criteria(self):
        template = self.build()
        review = self.reviewed(template)
        packet_path = template.with_name("packet.json")
        packet = gate.read(packet_path)
        self.assertEqual(packet["requirements"], self.f.plan_data["requirements"])
        packet["requirements"][0]["description"] = "Only check that an image exists"
        self.f.save(packet_path, packet)
        value = gate.read(review)
        value["comparison"]["packetSha256"] = self.tool.sha(packet_path)
        self.f.save(review, value)
        with self.assertRaisesRegex(ValueError, "Protected review requirements"):
            gate.accept(self.f.baseline, self.f.candidate, review)

    def test_changed_target_and_stale_source_rejected(self):
        template = self.build()
        review = self.reviewed(template)
        (self.f.game / "new.ts").write_text("changed")
        with self.assertRaisesRegex(ValueError, "stale"):
            gate.accept(self.f.baseline, self.f.candidate, review)
        (self.f.game / "new.ts").unlink()
        (self.f.root / "reference.png").write_bytes(b"changed reference")
        with self.assertRaisesRegex(ValueError, "Protected visual reference"):
            gate.snapshot(self.f.baseline, self.f.root / "candidate-2.json")

    def test_failed_omitted_unlocated_and_tampered_reviews_rejected(self):
        template = self.build()
        review = self.reviewed(template)
        original = gate.read(review)
        mutations = [lambda r: r.pop("comparison"),
                     lambda r: r["comparison"]["assessments"].pop(),
                     lambda r: r["comparison"]["assessments"][0]["observations"][0].update(currentRegion=[30, 0, 10, 5]),
                     lambda r: r["comparison"].update(packetSha256="wrong")]
        for mutate in mutations:
            value = copy.deepcopy(original)
            mutate(value)
            self.f.save(review, value)
            with self.subTest(value=value), self.assertRaises((ValueError, KeyError)):
                gate.accept(self.f.baseline, self.f.candidate, review)
        review = self.reviewed(template, failed=True)
        with self.assertRaisesRegex(ValueError, "Visual differences"):
            gate.accept(self.f.baseline, self.f.candidate, review)
        self.reviewed(template)
        template.with_name("0-current.png").write_bytes(b"changed capture")
        with self.assertRaises((ValueError, OSError)):
            gate.accept(self.f.baseline, self.f.candidate, review)

    def test_prior_findings_require_fresh_resolution_and_same_id(self):
        first = self.reviewed(self.build(), failed=True)
        # Reviewer array order must not affect the next round's preserved findings.
        reordered = gate.read(first)
        reordered["comparison"]["assessments"].reverse()
        self.f.save(first, reordered)
        template = self.build("round-2", first)
        review = self.reviewed(template)
        self.assertTrue(gate.accept(self.f.baseline, self.f.candidate, review)["passed"])
        value = gate.read(review)
        value["comparison"]["resolutions"].pop()
        self.f.save(review, value)
        with self.assertRaisesRegex(ValueError, "every previous"):
            gate.accept(self.f.baseline, self.f.candidate, review)
        self.reviewed(template)
        template.with_name("previous-review.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "Previous review snapshot"):
            gate.accept(self.f.baseline, self.f.candidate, review)

    def test_explicit_art_rebaseline_preserves_findings_and_scope(self):
        f = self.f
        first = self.reviewed(self.build(), failed=True)
        f.check["groups"][0]["margin"] = 2
        f.save(f.art, f.check)
        f.baseline, f.candidate = f.root / "baseline-2.json", f.root / "candidate-2.json"
        gate.freeze(f.plan, f.baseline)
        gate.snapshot(f.baseline, f.candidate)
        with self.assertRaisesRegex(ValueError, "rebaseline-note"):
            self.build("needs-note", first)
        result = self.tool.build(self.adapter, f.baseline, f.candidate, self.captures,
                                 f.root / "round-2", first, "Require two padding pixels after repacking")
        template = Path(result["review"])
        packet = gate.read(template.with_name("packet.json"))
        self.assertEqual(len(packet["priorFindings"]), 2)
        self.assertEqual(packet["baselineChange"]["reason"], "Require two padding pixels after repacking")
        review = self.reviewed(template)
        self.assertTrue(gate.accept(f.baseline, f.candidate, review)["passed"])
        template.with_name("previous-packet.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "Previous packet snapshot"):
            gate.accept(f.baseline, f.candidate, review)

    def test_rebaseline_cannot_change_requirements_or_target(self):
        f = self.f
        first = self.reviewed(self.build(), failed=True)
        original = copy.deepcopy(f.plan_data)
        for change in ("requirements", "target"):
            f.plan_data = copy.deepcopy(original)
            if change == "requirements":
                f.plan_data["requirements"][0]["description"] = "Weaker criterion"
            else:
                fixtures.Image.new("RGBA", (32, 16), (1, 2, 3, 255)).save(f.root / "reference.png")
            f.save(f.plan, f.plan_data)
            baseline, candidate = f.root / (change+"-baseline.json"), f.root / (change+"-candidate.json")
            gate.freeze(f.plan, baseline)
            gate.snapshot(baseline, candidate)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "requirements|target"):
                self.tool.build(self.adapter, baseline, candidate, self.captures,
                                f.root / change, first, "An explanation cannot waive protected criteria")

    def test_layout_dimensions_and_immutable_output(self):
        self.f.plan_data["comparisons"][0]["role"] = "layout"
        self.f.save(self.f.plan, self.f.plan_data)
        fixtures.Image.new("RGB", (40, 20)).save(self.f.root / "capture.png")
        with self.assertRaisesRegex(ValueError, "matching capture dimensions"):
            self.build()
        (self.f.root / "capture.png").write_bytes(self.f.image.read_bytes())
        self.build()
        with self.assertRaises(FileExistsError):
            self.build()

    def test_added_view_preserves_history_and_can_locate_missing_coverage(self):
        f = self.f
        first = self.reviewed(self.build(), failed=True)
        extra = copy.deepcopy(f.plan_data["comparisons"][1])
        extra.update(id="mobile-detail", focus="Previously missing habitat")
        f.plan_data["comparisons"].append(extra)
        f.save(f.plan, f.plan_data)
        captures = gate.read(self.captures)
        captures["mobile-detail"] = captures["mobile"]
        f.save(self.captures, captures)
        baseline, candidate = f.root / "expanded-baseline.json", f.root / "expanded-candidate.json"
        gate.freeze(f.plan, baseline)
        gate.snapshot(baseline, candidate)
        result = self.tool.build(self.adapter, baseline, candidate, self.captures,
                                 f.root / "expanded", first, "Add missing mobile habitat coverage")
        template = Path(result["review"])
        packet = gate.read(template.with_name("packet.json"))
        self.assertEqual([bool(i.get("previous")) for i in packet["items"]], [True, True, False])
        self.assertEqual(len(packet["priorFindings"]), 2)
        review = self.reviewed(template)
        value = gate.read(review)
        mobile, detail = value["comparison"]["assessments"][1:]
        detail["observations"] = mobile["observations"]
        mobile["observations"] = [dict(detail["observations"][0], id="mobile-overview")]
        resolution = next(r for r in value["comparison"]["resolutions"] if r["id"] == "mobile-shape")
        resolution.update(comparison="mobile-detail", reason="The added habitat view now shows the missing area")
        f.save(review, value)
        self.assertTrue(gate.accept(baseline, candidate, review)["passed"])
        resolution["comparison"] = "desktop"
        f.save(review, value)
        with self.assertRaisesRegex(ValueError, "retain its view"):
            gate.accept(baseline, candidate, review)

    def test_added_coverage_cannot_replace_an_existing_comparison(self):
        f = self.f
        first = self.reviewed(self.build(), failed=True)
        f.plan_data["comparisons"][1]["focus"] = "Changed existing comparison"
        f.save(f.plan, f.plan_data)
        baseline, candidate = f.root / "changed-baseline.json", f.root / "changed-candidate.json"
        gate.freeze(f.plan, baseline)
        gate.snapshot(baseline, candidate)
        with self.assertRaisesRegex(ValueError, "scope cannot be removed or changed"):
            self.tool.build(self.adapter, baseline, candidate, self.captures,
                            f.root / "changed", first, "Cannot disguise replacement as addition")


if __name__ == "__main__":
    unittest.main()
