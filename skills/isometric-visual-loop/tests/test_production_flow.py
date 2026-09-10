"""Deliberately broken spatial/production cases; fixtures are not game-quality evidence."""
import copy
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from types import SimpleNamespace
from PIL import Image
import test_verify_world as fixtures

gate = fixtures.gate
flow = gate.production_tools()
spatial = flow.module("spatial_checks")


def layout():
    land = [[c, r, "ground"] for c in range(8) for r in range(6) if c != 5 and (c, r) != (1, 4)]
    return {"version": 1, "spawn": [0, 2, "ground"], "regions": [
        {"id": "land", "kind": "paving", "cells": land},
        {"id": "garden", "kind": "planting", "cells": [[1, 4, "ground"]]},
        {"id": "water", "kind": "water", "cells": [[5, r, "ground"] for r in range(6)]}],
        "instances": [
            {"id": "tree", "kind": "tree", "footprint": [[1, 4, "ground"]], "support": "garden", "solid": True, "approaches": []},
            {"id": "house", "kind": "building", "footprint": [[3, 3, "ground"]], "support": "land", "solid": True, "approaches": [[3, 2, "ground"]]}],
        "routes": [{"id": "main", "cells": [[c, 2, "ground"] for c in range(8)], "start": [0, 2, "ground"], "goals": [[7, 2, "ground"]], "clearanceCells": 0}],
        "bridges": [{"id": "bridge", "deck": [[c, 2, "ground"] for c in (4, 5, 6)], "landings": [[4, 2, "ground"], [6, 2, "ground"]], "waterOverlayCells": [[5, r, "ground"] for r in range(6) if r != 2]}]}


class SpatialTests(unittest.TestCase):
    def test_connected_scene_and_independent_floors(self):
        data = layout()
        self.assertTrue(spatial.inspect(data)["passed"])
        data["regions"].append({"id": "roof", "kind": "planting", "cells": [[0, 2, "roof"]]})
        data["instances"][0].update(footprint=[[0, 2, "roof"]], support="roof")
        self.assertTrue(spatial.inspect(data)["passed"])

    def test_tree_on_path_and_blocked_doorway(self):
        data = layout()
        data["instances"][0].update(footprint=[[3, 2, "ground"]], support="land")
        ids = {f["id"].split(":")[0] for f in spatial.inspect(data)["findings"]}
        self.assertTrue({"root-support", "root-route", "route-clearance", "entrance-access"} <= ids)

    def test_broken_deck_and_water_over_support(self):
        for broken, expected in (("deck", "deck-continuity"), ("waterOverlayCells", "water-over-deck")):
            data = layout()
            if broken == "deck": data["bridges"][0][broken].pop(1)
            else: data["bridges"][0][broken].append([5, 2, "ground"])
            with self.subTest(broken=broken):
                self.assertIn(expected+":bridge", [f["id"] for f in spatial.inspect(data)["findings"]])

    def test_clearance_and_missing_entrance_are_not_just_path_existence(self):
        data = layout()
        data["routes"][0]["clearanceCells"] = 1
        self.assertIn("route-clearance:main", [f["id"] for f in spatial.inspect(data)["findings"]])
        data = layout()
        data["instances"][1]["approaches"] = []
        self.assertIn("entrance-missing:house", [f["id"] for f in spatial.inspect(data)["findings"]])

    def test_locally_valid_island_route_still_requires_spawn_connection(self):
        data = layout()
        data["regions"][0]["cells"] += [[20, 20, "ground"], [20, 21, "ground"]]
        data["routes"].append({"id": "island", "cells": [[20, 21, "ground"]], "start": [20, 21, "ground"], "goals": [[20, 21, "ground"]], "clearanceCells": 0})
        self.assertIn("route-connectivity:island", [f["id"] for f in spatial.inspect(data)["findings"]])


class ProductionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.game = self.root / "game"
        self.game.mkdir()
        self.receipts = self.root / "receipts"
        self.receipts.mkdir()
        self.save("game/layout.json", layout())
        self.save("game/boot.json", {"ready": True})
        self.save("game/actor.json", {"clip": "walk"})
        Image.new("RGB", (80, 80), "green").save(self.game / "asset.png")
        starter = gate.read(Path(__file__).resolve().parents[2] / "isometric-art-integration/references/starter-contract.json")
        asset = copy.deepcopy(starter["assets"][2])
        asset.update(image="asset.png", sha256=gate.digest(self.game / "asset.png"), frame={"x": 0, "y": 0, "width": 80, "height": 80})
        starter["assets"] = [asset]
        self.save("game/rigid.json", starter)
        actual = {k: asset[k] for k in ("frame", "anchor", "render", "footprint")}
        actual["image"] = "game/asset.png"
        self.save("game/binding.json", {"projection": starter["projection"], "assets": {"chair": actual}})
        self.plan = {"version": 3, "root": "..", "inputRoots": ["game"], "artChecks": [], "reviewMode": "independent",
                     "requirements": [{"id": "look", "description": "Whole composed scene", "domain": "visual", "views": ["desktop", "mobile"]},
                                      {"id": "play", "description": "Observed traversal", "domain": "gameplay", "views": ["desktop"]}],
                     "comparisons": [{"id": v, "requirements": ["look"], "view": v, "role": "style", "focus": "Complete composition", "reference": "game/asset.png"} for v in ["desktop", "mobile"]],
                     "production": {"version": 1, "rigidAssets": ["chair"], "checks": []}}
        def check(cid, stage, method="review", files=None, views=None):
            return {"id": cid, "stage": stage, "method": method, "evidenceKind": "image" if method == "review" and stage in ("assembly", "static", "final") else "measurement", "requirements": ["play" if stage == "motion" else "look"], "views": views or ["desktop"], "inputs": files or ["game/layout.json", "game/actor.json"]}
        self.plan["production"]["checks"] = [
            check("boot", "preflight", files=["game/boot.json"]),
            dict(check("layout", "layout", "layout", ["game/layout.json"]), source="game/layout.json"),
            dict(check("rigid", "assembly", "art", ["game/rigid.json", "game/binding.json", "game/asset.png"]), source="game/rigid.json", assets=["chair"], binding="game/binding.json"),
            check("assembly", "assembly"),
            dict(check("placement", "static", "layout", ["game/layout.json"]), source="game/layout.json"),
            check("composition", "static", views=["desktop", "mobile"]),
            check("motion", "motion"), check("final", "final", files=["game"], views=["desktop", "mobile"])]
        self.plan_path = self.save("game/plan.json", self.plan)
        for check in self.plan["production"]["checks"]:
            if check["method"] == "layout":
                check["requiredScope"] = spatial.inspect(layout())["scope"]
        self.save("game/plan.json", self.plan)
        self.baseline = self.root / "baseline.json"
        gate.freeze(self.plan_path, self.baseline)
        self.adapter = SimpleNamespace(protected=gate.protected, write_new=gate.write_new)
        self.counter = 0

    def save(self, path, value):
        target = self.root / path
        target.write_text(json.dumps(value), encoding="utf8")
        return target

    def start(self, cid):
        self.counter += 1
        ticket = self.root / f"ticket-{self.counter}.json"
        flow.begin(self.adapter, self.baseline, cid, self.receipts, ticket)
        return ticket

    def complete(self, cid, status="pass", omit_mobile=False):
        ticket = self.start(cid)
        check = next(c for c in self.plan["production"]["checks"] if c["id"] == cid)
        proof = self.save(f"proof-{self.counter}.json", {"testFixture": True})
        if check["evidenceKind"] == "image":
            proof = self.root / f"proof-{self.counter}.png"
            Image.new("RGB", (8, 8), "green").save(proof)
        submission = self.save(f"submission-{self.counter}.json", {"ticketSha256": gate.digest(ticket), "status": status, "reviewer": "test-reviewer", "observed": "Synthetic gate plumbing, not visual approval", "evidence": [{"path": proof.name, "sha256": gate.digest(proof), "view": v} for v in check["views"] if not(omit_mobile and v == "mobile")]})
        output = self.receipts / f"receipt-{self.counter}.json"
        return flow.finish(self.adapter, self.baseline, ticket, submission, self.receipts, output)

    def through_assembly(self):
        for cid in ["boot", "layout", "rigid", "assembly"]:
            self.assertEqual(self.complete(cid)["status"], "pass", cid)

    def test_prerequisites_block_expansion_and_v3_acceptance_bypass(self):
        with self.assertRaisesRegex(ValueError, "Earlier stage"):
            self.start("assembly")
        with self.assertRaisesRegex(ValueError, "receipts required"):
            gate.snapshot(self.baseline, self.root / "candidate.json")
        with self.assertRaisesRegex(ValueError, "Production receipts"):
            gate.accept(self.baseline, self.root / "missing.json", self.root / "review.json")
        self.complete("boot", "unverified")
        with self.assertRaisesRegex(ValueError, "Earlier stage"):
            self.start("layout")

    def test_full_progression_and_local_invalidation(self):
        self.through_assembly()
        for cid in ["placement", "composition", "motion", "final"]:
            self.assertEqual(self.complete(cid)["status"], "pass")
        self.assertTrue(flow.collect(self.plan, self.root, gate.digest(self.baseline), self.receipts)["passed"])
        gate.snapshot(self.baseline, self.root / "candidate.json", self.receipts)
        self.save("game/actor.json", {"clip": "changed"})
        result = flow.collect(self.plan, self.root, gate.digest(self.baseline), self.receipts)
        self.assertEqual(result["checks"]["boot"]["status"], "pass")
        self.assertEqual(result["checks"]["layout"]["status"], "pass")
        self.assertEqual(result["checks"]["rigid"]["status"], "pass")
        self.assertEqual(result["checks"]["assembly"]["status"], "unverified")
        self.assertEqual(result["nextStage"], "assembly")

    def test_ticket_requires_unchanged_sources_before_capture(self):
        ticket = self.start("boot")
        self.save("game/boot.json", {"ready": False})
        submission = self.save("submission.json", {})
        with self.assertRaisesRegex(ValueError, "Inputs changed since begin"):
            flow.finish(self.adapter, self.baseline, ticket, submission, self.receipts, self.receipts / "x.json")

    def test_missing_mobile_and_changed_evidence_rejected(self):
        self.through_assembly()
        self.complete("placement")
        with self.assertRaisesRegex(ValueError, "Missing required view"):
            self.complete("composition", omit_mobile=True)
        receipt = self.complete("composition")
        (self.root / receipt["evidence"][0]["path"]).write_text("changed")
        self.assertEqual(flow.collect(self.plan, self.root, gate.digest(self.baseline), self.receipts)["checks"]["composition"]["status"], "unverified")

    def test_layout_failure_overrides_claimed_pass_and_later_failure_supersedes_pass(self):
        self.complete("boot")
        data = layout()
        data["instances"][0].update(footprint=[[2, 2, "ground"]], support="land")
        self.save("game/layout.json", data)
        self.assertEqual(self.complete("layout")["status"], "fail")
        with self.assertRaisesRegex(ValueError, "Earlier stage"):
            self.start("rigid")
        self.save("game/layout.json", layout())
        self.complete("layout")
        self.complete("layout", "fail")
        self.assertEqual(flow.collect(self.plan, self.root, gate.digest(self.baseline), self.receipts)["checks"]["layout"]["status"], "fail")

    def test_incompatible_rigid_geometry_and_host_binding(self):
        self.complete("boot")
        self.complete("layout")
        data = gate.read(self.game / "rigid.json")
        data["assets"][0]["groundPoints"][0]["source"]["x"] += 9
        self.save("game/rigid.json", data)
        result = self.complete("rigid")
        self.assertEqual(result["status"], "fail")
        self.assertTrue(result["automatic"]["findings"])
        binding = gate.read(self.game / "binding.json")
        binding["assets"]["chair"]["anchor"]["x"] = .2
        self.save("game/binding.json", binding)
        with self.assertRaisesRegex(ValueError, "Host frame/anchor"):
            self.complete("rigid")

    def test_plan_cannot_omit_geometry_or_visual_coverage(self):
        for defect in ("rigid", "mobile"):
            plan = copy.deepcopy(self.plan)
            if defect == "rigid":
                plan["production"]["checks"] = [c for c in plan["production"]["checks"] if c["id"] != "rigid"]
            else:
                next(c for c in plan["production"]["checks"] if c["id"] == "composition")["views"] = ["desktop"]
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                flow.validate(plan, self.root)

    def test_two_failed_attempts_require_strategy_change(self):
        self.complete("boot", "fail")
        self.complete("boot", "fail")
        with self.assertRaisesRegex(ValueError, "Two failed attempts"):
            self.start("boot")
        latest = sorted(self.receipts.glob("*.json"))[-1]
        strategy = self.save("strategy.json", {"check": "boot", "previousReceiptSha256": gate.digest(latest),
                                               "hypothesis": "Asset URL omitted from build", "test": "Load the production asset URL directly"})
        flow.begin(self.adapter, self.baseline, "boot", self.receipts, self.root / "strategy-ticket.json", strategy)
        self.assertTrue(gate.read(self.root / "strategy-ticket.json")["strategy"])

    def test_scope_removal_and_old_capture_reuse_rejected(self):
        old = self.complete("boot")
        self.save("game/boot.json", {"ready": "changed"})
        ticket = self.start("boot")
        submission = self.save("old-evidence.json", {"ticketSha256": gate.digest(ticket), "status": "pass", "reviewer": "test", "observed": "Trying to reuse stale evidence", "evidence": old["evidence"]})
        with self.assertRaisesRegex(ValueError, "predates capture ticket"):
            flow.finish(self.adapter, self.baseline, ticket, submission, self.receipts, self.receipts / "stale.json")
        self.complete("boot")
        data = layout()
        data["instances"] = []
        self.save("game/layout.json", data)
        with self.assertRaisesRegex(ValueError, "Protected layout scope"):
            self.complete("layout")

    def test_ticket_cannot_be_reused_or_finish_after_another_attempt(self):
        pending = self.start("boot")
        self.complete("boot", "fail")
        submission = self.save("unused.json", {})
        with self.assertRaisesRegex(ValueError, "superseded"):
            flow.finish(self.adapter, self.baseline, pending, submission, self.receipts, self.receipts / "x.json")
        consumed = self.root / "ticket-2.json"
        with self.assertRaisesRegex(ValueError, "already consumed"):
            flow.finish(self.adapter, self.baseline, consumed, submission, self.receipts, self.receipts / "y.json")

    def test_v3_cli_and_existing_comparison_acceptance_work_together(self):
        command = [sys.executable, str(fixtures.SCRIPT)]
        blocked = subprocess.run(command + ["production", "begin", str(self.baseline), "--check", "final", "--receipts", str(self.receipts), "--out", str(self.root / "blocked.json")], capture_output=True, text=True)
        self.assertEqual(blocked.returncode, 1)
        self.assertIn("Earlier stage", blocked.stderr)
        self.through_assembly()
        for cid in ["placement", "composition", "motion"]: self.complete(cid)
        candidate = self.root / "candidate.json"
        gate.snapshot(self.baseline, candidate, self.receipts)
        captures = self.save("captures.json", {v: {"path": "game/asset.png", "captureNotes": "Synthetic comparison plumbing"} for v in ["desktop", "mobile"]})
        adapter = SimpleNamespace(protected=gate.protected, source_hashes=gate.source_hashes, local=gate.local)
        result = gate.comparison_tools().build(adapter, self.baseline, candidate, captures, self.root / "comparison")
        review_path = Path(result["review"])
        review = gate.read(review_path)
        review["comparison"]["reviewer"] = "test-reviewer"
        for assessment in review["comparison"]["assessments"]:
            assessment.update(status="pass", observations=[{"id": assessment["id"]+"-observed", "status": "pass", "currentRegion": [0, 0, 8, 8], "referenceRegion": [0, 0, 8, 8], "difference": "Synthetic fixture agrees", "repair": ""}])
        for verdict in review["verdicts"]:
            req = next(r for r in self.plan["requirements"] if r["id"] == verdict["id"])
            verdict.update(status="pass", reviewer="test-reviewer", notes="Synthetic gate plumbing", evidence=[{"path": "../game/asset.png", "sha256": gate.digest(self.game / "asset.png"), "kind": "image", "view": v} for v in req["views"]])
        review_path.write_text(json.dumps(review), encoding="utf8")
        with self.assertRaisesRegex(ValueError, "blocks acceptance: final"):
            gate.accept(self.baseline, candidate, review_path, self.receipts)
        self.complete("final")
        accepted = subprocess.run(command + ["accept", str(self.baseline), str(candidate), str(review_path), "--production-receipts", str(self.receipts)], capture_output=True, text=True)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertTrue(json.loads(accepted.stdout)["passed"])


if __name__ == "__main__":
    unittest.main()
