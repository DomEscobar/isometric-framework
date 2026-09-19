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
            {"id": "tree", "kind": "tree", "footprint": [[1, 4, "ground"]], "support": "garden", "solid": True, "approaches": [], "asset": "chair"},
            {"id": "house", "kind": "building", "footprint": [[3, 3, "ground"]], "support": "land", "solid": True, "approaches": [[3, 2, "ground"]], "asset": "chair"}],
        "routes": [{"id": "main", "cells": [[c, 2, "ground"] for c in range(8)], "start": [0, 2, "ground"], "goals": [[7, 2, "ground"]], "clearanceCells": 0}],
        "bridges": [{"id": "bridge", "deck": [[c, 2, "ground"] for c in (4, 5, 6)], "landings": [[4, 2, "ground"], [6, 2, "ground"]], "waterOverlayCells": [[5, r, "ground"] for r in range(6) if r != 2]}]}


class SpatialTests(unittest.TestCase):
    def test_water_requires_axis_connected_cells(self):
        data = layout()
        water = next(region for region in data["regions"] if region["id"] == "water")
        water["cells"] = [[5, 0, "ground"], [6, 1, "ground"]]
        land = next(region for region in data["regions"] if region["id"] == "land")
        land["cells"].remove([6, 1, "ground"])
        land["cells"].append([5, 2, "ground"])
        self.assertIn("water-connectivity:water", [f["id"] for f in spatial.inspect(data)["findings"]])

    def test_water_axis_bend_and_separate_pond_ids_pass(self):
        data = layout()
        water = next(region for region in data["regions"] if region["id"] == "water")
        water["cells"] = [[5, 0, "ground"], [5, 1, "ground"], [6, 1, "ground"]]
        land = next(region for region in data["regions"] if region["id"] == "land")
        land["cells"].remove([6, 1, "ground"])
        land["cells"].append([5, 2, "ground"])
        self.assertTrue(spatial.inspect(data)["passed"])
        data["regions"].append({"id": "pond", "kind": "water", "cells": [[20, 20, "ground"]]})
        self.assertTrue(spatial.inspect(data)["passed"])

    def test_water_topology_regression_rejects_diagonal_bends_across_bridge(self):
        data = layout()
        water = next(region for region in data["regions"] if region["id"] == "water")
        water["cells"] = ([[7, row, "ground"] for row in range(4)]
                          + [[8, row, "ground"] for row in range(4, 6)]
                          + [[8, row, "ground"] for row in range(7, 9)]
                          + [[7, row, "ground"] for row in range(9, 13)])
        land = next(region for region in data["regions"] if region["id"] == "land")
        land["cells"] = [point for point in land["cells"] if point not in water["cells"]]
        land["cells"] += [[7, 6, "ground"], [8, 6, "ground"], [9, 6, "ground"]]
        data["bridges"].append({"id": "wide", "deck": [[7, 6, "ground"], [8, 6, "ground"], [9, 6, "ground"]],
                                "landings": [[7, 6, "ground"], [9, 6, "ground"]], "waterOverlayCells": []})
        water["underBridgeCells"] = [[8, 6, "ground"]]
        self.assertIn("water-connectivity:water", [f["id"] for f in spatial.inspect(data)["findings"]])

    def test_water_can_connect_under_a_declared_bridge_deck(self):
        data = layout()
        water = next(region for region in data["regions"] if region["id"] == "water")
        water["cells"] = [[5, 1, "ground"], [5, 3, "ground"]]
        water["underBridgeCells"] = [[5, 2, "ground"]]
        land = next(region for region in data["regions"] if region["id"] == "land")
        land["cells"].append([5, 2, "ground"])
        self.assertTrue(spatial.inspect(data)["passed"])

    def test_water_under_bridge_cells_must_be_valid_declared_decks(self):
        for value, expected in (([[4, 2, "ground"], [4, 2, "ground"]], "Duplicate cells"),
                                ([[5, 1, "ground"]], "declared bridge deck"),
                                ("not-a-list", "underBridgeCells must be a list")):
            data = layout()
            water = next(region for region in data["regions"] if region["id"] == "water")
            water["underBridgeCells"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, expected):
                spatial.inspect(data)
        data = layout()
        land = next(region for region in data["regions"] if region["id"] == "land")
        land["underBridgeCells"] = []
        with self.assertRaisesRegex(ValueError, "only applies to water"):
            spatial.inspect(data)

    def test_water_on_different_floors_is_not_connected(self):
        data = layout()
        water = next(region for region in data["regions"] if region["id"] == "water")
        water["cells"] = [[5, 1, "ground"], [5, 2, "roof"]]
        self.assertIn("water-connectivity:water", [f["id"] for f in spatial.inspect(data)["findings"]])

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


class PlacementTests(unittest.TestCase):
    placement = flow.module("placement_checks")

    def contract(self, **footprints):
        return {"assets": [{"id": name, "footprint": {"columns": c, "rows": r}}
                           for name, (c, r) in footprints.items()]}

    def test_reserved_cells_must_match_the_calibrated_art(self):
        data = layout()
        for instance in data["instances"]:
            instance["asset"] = "oak" if instance["kind"] == "tree" else "cottage"
        contract = self.contract(oak=(1, 1), cottage=(1, 1))
        self.assertTrue(self.placement.inspect(data, contract)["passed"])
        # The art checker forces a wide wall to declare 6x1; reserving one cell hides five.
        wide = self.contract(oak=(1, 1), cottage=(6, 1))
        report = self.placement.inspect(data, wide)
        self.assertFalse(report["passed"])
        self.assertEqual([f["id"] for f in report["findings"]], ["footprint-disagreement:house"])
        self.assertIn("reserves 1x1 cells but calibrated art cottage measures 6x1", report["findings"][0]["difference"])

    def test_multi_cell_placement_agreeing_with_its_art_passes(self):
        data = layout()
        for instance in data["instances"]:
            instance["asset"] = "oak" if instance["kind"] == "tree" else "cottage"
        house = next(i for i in data["instances"] if i["id"] == "house")
        house["footprint"] = [[3, 3, "ground"], [4, 3, "ground"]]
        self.assertTrue(spatial.inspect(data)["passed"])
        self.assertTrue(self.placement.inspect(data, self.contract(oak=(1, 1), cottage=(2, 1)))["passed"])

    def test_unnamed_and_unknown_assets_are_findings_not_silent_passes(self):
        data = layout()
        data["instances"][0]["asset"] = "ghost"
        del data["instances"][1]["asset"]
        report = self.placement.inspect(data, self.contract(oak=(1, 1)))
        self.assertEqual({f["id"] for f in report["findings"]},
                         {"asset-unknown:tree", "asset-unnamed:house"})


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
        starter["overhangRulings"] = "./rulings.json"
        self.save("game/rulings.json", {"version": 1, "rulings": []})
        self.save("game/rigid.json", starter)
        actual = {k: asset[k] for k in ("frame", "anchor", "render", "footprint")}
        actual["image"] = "game/asset.png"
        # The opaque 80x80 frame reaches 60px above the anchor row, and a 1x1 footprint leaves
        # no doubt which cell owns that top row, so the measured body height is exactly 60.
        actual["bodyHeight"] = 60
        self.save("game/binding.json", {"projection": starter["projection"], "assets": {"chair": actual}})
        self.write_provenance()
        self.plan = {"version": 4, "root": "..", "inputRoots": ["game"], "artChecks": [], "reviewMode": "independent",
                     "assetPolicy": {"version": 1, "sources": {"world": "generated", "character": "generated", "environment": "generated"},
                                     "characterAnimation": {"animated": "image-to-video-extract-pack", "staticIdle": "generated-facing"},
                                     "coverageLedger": "game/ledger.json", "runtime": {"manifest": "game/runtime.json", "binding": "game/used.json"}},
                     "requirements": [{"id": "look", "description": "Whole composed scene", "domain": "visual", "views": ["desktop", "mobile"]},
                                      {"id": "play", "description": "Observed traversal", "domain": "gameplay", "views": ["desktop"]}],
                     "comparisons": [{"id": v, "requirements": ["look"], "view": v, "role": "style", "focus": "Complete composition", "reference": "game/asset.png"} for v in ["desktop", "mobile"]],
                     "production": {"version": 1, "rigidAssets": ["chair"], "checks": []}}
        provenance = ["game/ledger.json", "game/runtime.json", "game/used.json"]
        def check(cid, stage, method="review", files=None, views=None):
            image = (method == "review" and stage in ("assembly", "static", "final")) or (method == "layout" and stage == "layout")
            listed = list(files or ["game/layout.json", "game/actor.json"])
            if flow.STAGES.index(stage) >= flow.STAGES.index("static"):
                listed += [path for path in provenance if path not in listed]
            return {"id": cid, "stage": stage, "method": method, "evidenceKind": "image" if image else "measurement", "requirements": ["play" if stage == "motion" else "look"], "views": views or ["desktop"], "inputs": listed}
        self.plan["production"]["checks"] = [
            check("boot", "preflight", files=["game/boot.json"]),
            dict(check("layout", "layout", "layout", ["game/layout.json"]), source="game/layout.json"),
            dict(check("rigid", "assembly", "art", ["game/rigid.json", "game/binding.json", "game/asset.png", "game/rulings.json"]), source="game/rigid.json", assets=["chair"], binding="game/binding.json"),
            check("assembly", "assembly"),
            dict(check("placement", "static", "layout", ["game/layout.json", "game/rigid.json"]),
                 source="game/layout.json", artContract="game/rigid.json"),
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

    def write_provenance(self):
        self.save("game/generation.json", {"localJobId": "synthetic-test-not-generated-art", "outputSha256": gate.digest(self.game / "asset.png")})
        def proof(name):
            return {"path": "game/" + name, "sha256": gate.digest(self.game / name)}
        ledger = {"version": 1, "clips": {}, "images": {
            "ground": {"origin": {"kind": "generated", "record": proof("generation.json"), "output": proof("asset.png")},
                       "transforms": [proof("asset.png")]}}}
        self.save("game/ledger.json", ledger)
        self.save("game/runtime.json", {"assets": {"images": {"ground": {"url": "asset.png"}}, "textures": {}, "animations": {}}})
        self.save("game/used.json", {"version": 1, "used": {
            category: {"images": ["ground"] if category == "world" else [], "textures": [], "animations": []}
            for category in ("world", "character", "environment", "ui", "debug")}})

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

    def test_world_expansion_retains_scoped_calibration_but_stales_full_review(self):
        self.through_assembly()
        for cid in ["placement", "composition", "motion", "final"]:
            self.complete(cid)
        # New unrelated family is outside the patch's inputs, inside final scope.
        self.save("game/new-building.json", {"texture": "new-family"})
        result = flow.collect(self.plan, self.root, gate.digest(self.baseline), self.receipts)
        for cid in ["boot", "layout", "rigid", "assembly"]:
            self.assertEqual(result["checks"][cid]["status"], "pass", cid)
        self.assertEqual(result["checks"]["final"]["status"], "unverified")
        # Shared actor behavior really affects the patch; it must invalidate it.
        self.save("game/actor.json", {"clip": "changed-shared-behavior"})
        result = flow.collect(self.plan, self.root, gate.digest(self.baseline), self.receipts)
        self.assertEqual(result["checks"]["assembly"]["status"], "unverified")
        self.assertFalse(result["checks"]["final"]["eligible"])

    def test_missing_mobile_and_changed_evidence_rejected(self):
        self.through_assembly()
        self.complete("placement")
        with self.assertRaisesRegex(ValueError, "Missing required view"):
            self.complete("composition", omit_mobile=True)
        receipt = self.complete("composition")
        (self.root / receipt["evidence"][0]["path"]).write_text("changed")
        self.assertEqual(flow.collect(self.plan, self.root, gate.digest(self.baseline), self.receipts)["checks"]["composition"]["status"], "unverified")

    def test_status_explains_check_eligibility_and_declared_evidence_contract(self):
        result = flow.collect(self.plan, self.root, gate.digest(self.baseline), self.receipts)
        boot = result["checks"]["boot"]
        self.assertTrue(boot["eligible"])
        self.assertEqual(boot["views"], ["desktop"])
        self.assertEqual(boot["evidenceKind"], "measurement")
        self.assertEqual(boot["declaredInputs"], ["game/boot.json"])
        self.assertFalse(boot["strategyRequired"])
        self.assertTrue(result["checks"]["assembly"]["blockers"])
        self.complete("boot")
        completed = flow.collect(self.plan, self.root, gate.digest(self.baseline), self.receipts)["checks"]["boot"]
        self.assertFalse(completed["eligible"])
        self.assertIn("Current receipt already passes", completed["blockers"][0])

    def test_status_does_not_offer_a_check_with_missing_inputs(self):
        (self.game / "boot.json").unlink()
        boot = flow.collect(self.plan, self.root, gate.digest(self.baseline), self.receipts)["checks"]["boot"]
        self.assertFalse(boot["eligible"])
        self.assertTrue(any("Missing production input" in item for item in boot["blockers"]))

    def test_next_is_read_only_and_distinguishes_ready_from_incomplete(self):
        status = flow.collect(self.plan, self.root, gate.digest(self.baseline), self.receipts)
        next_item = flow.next_work(status)
        self.assertEqual(next_item["state"], "ready-to-work")
        self.assertTrue(next_item["readyToWork"])
        self.assertEqual(next_item["eligibleChecks"][0]["id"], "boot")
        self.assertEqual(next_item["eligibleChecks"][0]["expectedEvidence"], {"kind": "measurement", "views": ["desktop"]})
        (self.game / "boot.json").unlink()
        broken = flow.next_work(flow.collect(self.plan, self.root, gate.digest(self.baseline), self.receipts))
        self.assertEqual(broken["state"], "incomplete")
        self.assertFalse(broken["readyToWork"])
        self.assertTrue(broken["missingInputs"])

    def test_v4_cannot_skip_stages_and_records_static_provenance_failure(self):
        with self.assertRaisesRegex(ValueError, "Earlier stage"):
            self.start("placement")
        self.through_assembly()
        self.save("game/ledger.json", {})
        self.save("game/runtime.json", {})
        self.save("game/used.json", {})
        value = self.complete("placement")
        self.assertEqual(value["status"], "fail")
        self.assertFalse(value["automatic"]["provenance"]["passed"])
        self.assertIn("Runtime manifest", value["automatic"]["provenance"]["error"])

    def test_draft_hashes_only_valid_fresh_complete_evidence_and_leaves_review_fields_blank(self):
        self.through_assembly()
        self.complete("placement")
        check = next(c for c in self.plan["production"]["checks"] if c["id"] == "composition")
        stale = self.root / "stale.png"
        Image.new("RGB", (8, 8), "green").save(stale)
        stale_ticket = self.start("composition")
        stale_mapping = self.save("stale-mapping.json", {"evidence": [{"path": stale.name, "view": view} for view in check["views"]]})
        with self.assertRaisesRegex(ValueError, "predates capture ticket"):
            flow.draft(self.adapter, self.baseline, stale_ticket, stale_mapping, self.root / "stale-draft.json")
        ticket = self.start("composition")
        proof = self.root / "fresh.png"
        Image.new("RGB", (8, 8), "green").save(proof)
        incomplete = self.save("incomplete-mapping.json", {"evidence": [{"path": proof.name, "view": "desktop"}]})
        with self.assertRaisesRegex(ValueError, "Missing required view"):
            flow.draft(self.adapter, self.baseline, ticket, incomplete, self.root / "incomplete-draft.json")
        wrong = self.save("wrong-kind.json", {"evidence": [{"path": "wrong-kind.json", "view": view} for view in check["views"]]})
        with self.assertRaisesRegex(ValueError, "format does not match"):
            flow.draft(self.adapter, self.baseline, ticket, wrong, self.root / "wrong-draft.json")
        mapping = self.save("mapping.json", {"evidence": [{"path": proof.name, "view": view} for view in check["views"]]})
        with self.assertRaisesRegex(ValueError, "Drafts must be outside"):
            flow.draft(self.adapter, self.baseline, ticket, mapping, self.game / "unsafe-draft.json")
        output = self.root / "composition-draft.json"
        command = [sys.executable, str(fixtures.SCRIPT), "production", "draft", str(self.baseline),
                   "--ticket", str(ticket), "--evidence-mapping", str(mapping), "--receipts", str(self.receipts),
                   "--out", str(output)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        draft = gate.read(output)
        self.assertEqual(draft["status"], "unverified")
        self.assertEqual(draft["reviewer"], "")
        self.assertEqual(draft["observed"], "")
        self.assertEqual(draft["ticketSha256"], gate.digest(ticket))
        self.assertTrue(all(item["sha256"] == gate.digest(proof) for item in draft["evidence"]))

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

    def test_host_body_height_must_match_the_height_the_artwork_measures(self):
        """The renderer orders depth and blocks movement with this number, so art has to bound it."""
        self.complete("boot")
        self.complete("layout")
        binding = gate.read(self.game / "binding.json")
        # 32 is the engine's own fallback for a sprite of any height.
        for short in (32, 57):
            binding["assets"]["chair"]["bodyHeight"] = short
            self.save("game/binding.json", binding)
            with self.assertRaisesRegex(ValueError, "below the 60.0 px its artwork needs"):
                self.complete("rigid")
        # heightErrorPx absorbs measurement error; a taller body is a deliberate collider.
        for allowed in (58, 200):
            binding["assets"]["chair"]["bodyHeight"] = allowed
            self.save("game/binding.json", binding)
            self.assertEqual(self.complete("rigid")["status"], "pass")
        del binding["assets"]["chair"]["bodyHeight"]
        self.save("game/binding.json", binding)
        with self.assertRaisesRegex(ValueError, "must declare the bodyHeight"):
            self.complete("rigid")

    def test_placement_rejects_art_covering_cells_the_layout_never_reserved(self):
        data = gate.read(self.game / "layout.json")
        house = next(i for i in data["instances"] if i["id"] == "house")
        house["footprint"] = [[3, 3, "ground"], [4, 3, "ground"]]
        self.save("game/layout.json", data)
        self.through_assembly()
        result = self.complete("placement")
        self.assertEqual(result["status"], "fail")
        findings = result["automatic"]["automatic"]["findings"]
        self.assertEqual([f["id"] for f in findings], ["footprint-disagreement:house"])

    def test_static_placement_cannot_skip_the_art_contract(self):
        plan = copy.deepcopy(self.plan)
        del next(c for c in plan["production"]["checks"] if c["id"] == "placement")["artContract"]
        with self.assertRaisesRegex(ValueError, "declare artContract"):
            flow.validate(plan, self.root)
        undeclared = copy.deepcopy(self.plan)
        check = next(c for c in undeclared["production"]["checks"] if c["id"] == "placement")
        check["inputs"] = [p for p in check["inputs"] if p != "game/rigid.json"]
        with self.assertRaisesRegex(ValueError, "artContract must be a declared dependency"):
            flow.validate(undeclared, self.root)

    def test_calibrating_one_asset_cannot_hide_another_exported_rigid_asset(self):
        self.complete("boot")
        self.complete("layout")
        binding = gate.read(self.game / "binding.json")
        binding["assets"]["stadtmauer"] = copy.deepcopy(binding["assets"]["chair"])
        self.save("game/binding.json", binding)
        with self.assertRaisesRegex(ValueError, "does not protect: stadtmauer"):
            self.complete("rigid")

    def test_overhang_rulings_must_be_hashed_with_the_contract(self):
        plan = copy.deepcopy(self.plan)
        check = next(c for c in plan["production"]["checks"] if c["id"] == "rigid")
        check["inputs"] = [p for p in check["inputs"] if p != "game/rulings.json"]
        self.save("game/plan.json", plan)
        self.baseline = self.root / "baseline-unpinned-rulings.json"
        gate.freeze(self.plan_path, self.baseline)
        self.complete("boot")
        self.complete("layout")
        with self.assertRaisesRegex(ValueError, "rulings must be a declared dependency"):
            self.complete("rigid")

    def test_plan_cannot_omit_geometry_or_visual_coverage(self):
        for defect in ("rigid", "empty-rigid", "mobile"):
            plan = copy.deepcopy(self.plan)
            if defect == "rigid":
                plan["production"]["checks"] = [c for c in plan["production"]["checks"] if c["id"] != "rigid"]
            elif defect == "empty-rigid":
                plan["production"]["rigidAssets"] = []
                plan["production"]["checks"] = [c for c in plan["production"]["checks"] if c["method"] != "art"]
            else:
                next(c for c in plan["production"]["checks"] if c["id"] == "composition")["views"] = ["desktop"]
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                flow.validate(plan, self.root)

    def test_shipped_example_cannot_drop_rigid_calibration(self):
        example_path = Path(__file__).resolve().parents[1] / "references" / "acceptance-plan.example.json"
        example = gate.read(example_path)
        gutted = copy.deepcopy(example)
        gutted["production"]["rigidAssets"] = []
        gutted["production"]["checks"] = [c for c in gutted["production"]["checks"] if c["method"] != "art"]
        with self.assertRaisesRegex(ValueError, "nonempty rigidAssets"):
            flow.validate(gutted, example_path.parent.parent)

    def test_shipped_example_covers_each_environment_dimension_with_static_evidence(self):
        example_path = Path(__file__).resolve().parents[1] / "references" / "acceptance-plan.example.json"
        example = gate.read(example_path)
        flow.validate(example, example_path.parent.parent)
        expected_views = {
            "style": {"desktop", "mobile"},
            "composition": {"desktop", "mobile", "ground-only"},
            "relationships": {"desktop", "mobile"},
            "connections": {"desktop", "mobile", "contact-detail"},
        }
        visual = {r["id"]: set(r["views"]) for r in example["requirements"] if r["domain"] == "visual"}
        self.assertEqual({rid: visual[rid] for rid in expected_views}, expected_views)
        comparison_coverage = {(rid, spec["view"])
                               for spec in example["comparisons"] for rid in spec["requirements"]}
        self.assertTrue(all((rid, view) in comparison_coverage
                            for rid, views in expected_views.items() for view in views))
        static_checks = [check for check in example["production"]["checks"]
                         if check["stage"] == "static" and check["method"] == "review"]
        static_coverage = {(rid, view) for check in static_checks
                           for rid in check["requirements"] for view in check["views"]}
        self.assertTrue(all((rid, view) in static_coverage
                            for rid, views in expected_views.items() for view in views))
        self.assertTrue(all(len(check["requirements"]) == 1 for check in static_checks))
        for stage in ("assembly", "final"):
            covered = {rid for check in example["production"]["checks"]
                       if check["stage"] == stage and check["method"] == "review"
                       for rid in check["requirements"]}
            self.assertTrue(set(expected_views) <= covered, stage)

    def test_two_failed_attempts_require_strategy_change(self):
        self.complete("boot", "fail")
        self.complete("boot", "fail")
        self.assertTrue(flow.collect(self.plan, self.root, gate.digest(self.baseline), self.receipts)["checks"]["boot"]["strategyRequired"])
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

    def test_new_world_production_rejects_version_3(self):
        plan = copy.deepcopy(self.plan)
        plan["version"] = 3
        plan.pop("assetPolicy", None)
        with self.assertRaisesRegex(ValueError, "acceptance-plan version 4"):
            flow.validate(plan, self.root)
        v3_path = self.save("game/plan-v3.json", plan)
        with self.assertRaisesRegex(ValueError, "acceptance-plan version 4"):
            gate.freeze(v3_path, self.root / "v3-baseline.json")

    def test_v4_cli_acceptance_and_valid_rechain_stales_previous_reviews(self):
        self.assertTrue(self.assert_cli_acceptance()["provenance"]["enforced"])
        command = [sys.executable, str(fixtures.SCRIPT), "production", "next", str(self.baseline), "--receipts", str(self.receipts)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["state"], "complete")
        # Valid replacement evidence is still a new candidate, not reusable review.
        self.save("game/generation.json", {"localJobId": "replacement-synthetic-record", "outputSha256": gate.digest(self.game / "asset.png")})
        ledger = gate.read(self.game / "ledger.json")
        ledger["images"]["ground"]["origin"]["record"] = {"path": "game/generation.json", "sha256": gate.digest(self.game / "generation.json")}
        self.save("game/ledger.json", ledger)
        self.assertTrue(gate.asset_provenance_tools().verify(self.plan, self.root)["enforced"])
        status = flow.collect(self.plan, self.root, gate.digest(self.baseline), self.receipts)
        self.assertEqual(status["nextStage"], "static")
        self.assertEqual(status["checks"]["composition"]["status"], "unverified")

    def patch_plan(self, mutate):
        self.patches = getattr(self, "patches", 0) + 1
        previous = self.baseline
        mutate(self.plan)
        self.save("game/plan.json", self.plan)
        self.baseline = self.root / f"patched-baseline-{self.patches}.json"
        gate.freeze(self.plan_path, self.baseline)
        return previous

    def grow(self, plan):
        plan["requirements"].append({"id": "extra", "description": "Added wing", "domain": "visual", "views": ["desktop"]})
        plan["comparisons"].append({"id": "extra-desktop", "requirements": ["extra"], "view": "desktop",
                                    "role": "style", "focus": "Added wing", "reference": "game/asset.png"})
        plan["production"]["checks"].append(
            {"id": "extra", "stage": "static", "method": "review", "evidenceKind": "image",
             "requirements": ["extra"], "views": ["desktop"],
             "inputs": ["game/layout.json", "game/actor.json", "game/ledger.json", "game/runtime.json", "game/used.json"]})

    def carry(self, previous, reason="Added a wing to the approved scope", name="carry.json"):
        return flow.carryover(self.adapter, self.baseline, previous, self.receipts, reason, self.receipts / name)

    def test_patching_the_plan_reports_orphaned_receipts_instead_of_dropping_them(self):
        self.through_assembly()
        self.patch_plan(self.grow)
        status = flow.collect(self.plan, self.root, gate.digest(self.baseline), self.receipts)
        self.assertEqual(len(status["ignoredReceipts"]), 4)
        self.assertEqual(status["nextStage"], "preflight")
        self.assertEqual(status["checks"]["boot"]["reason"], "No receipt")

    def test_carryover_keeps_unchanged_stages_and_leaves_only_the_new_work_open(self):
        self.through_assembly()
        for cid in ["placement", "composition", "motion", "final"]:
            self.complete(cid)
        record = self.carry(self.patch_plan(self.grow))
        self.assertEqual(len(record["carried"]), 8)
        self.assertEqual(record["declined"], [])
        moved = {item["check"]: item["inputsUnchanged"] for item in record["carried"]}
        # The patched plan file lives inside the final check's own input tree.
        self.assertFalse(moved["final"])
        self.assertTrue(moved["boot"])
        status = flow.collect(self.plan, self.root, gate.digest(self.baseline), self.receipts)
        self.assertEqual(status["ignoredReceipts"], [])
        for cid in ["boot", "layout", "rigid", "assembly", "placement", "composition", "motion"]:
            self.assertEqual(status["checks"][cid]["status"], "pass", cid)
        self.assertEqual(status["checks"]["extra"]["status"], "unverified")
        self.assertEqual(status["nextStage"], "static")

    def test_a_second_patch_reconsiders_what_the_first_one_admitted(self):
        self.through_assembly()
        first = self.carry(self.patch_plan(self.grow), name="carry-1.json")
        self.assertEqual(len(first["carried"]), 4)

        def widen(plan):
            next(c for c in plan["production"]["checks"] if c["id"] == "layout")["views"] = ["desktop", "mobile"]
        second = self.carry(self.patch_plan(widen), reason="Layout now reviewed on mobile too", name="carry-2.json")
        self.assertEqual({item["check"] for item in second["carried"]}, {"boot", "rigid", "assembly"})
        self.assertEqual([item["check"] for item in second["declined"]], ["layout"])
        status = flow.collect(self.plan, self.root, gate.digest(self.baseline), self.receipts)
        self.assertEqual(status["ignoredReceipts"], [second["declined"][0]["receipt"]])
        self.assertEqual(status["checks"]["boot"]["status"], "pass")
        self.assertEqual(status["checks"]["layout"]["status"], "unverified")
        self.assertEqual(status["nextStage"], "layout")

    def test_carryover_refuses_a_plan_that_narrows_protected_requirements(self):
        self.through_assembly()

        def narrow(plan):
            plan["requirements"] = [r for r in plan["requirements"] if r["id"] != "play"]
            next(c for c in plan["production"]["checks"] if c["id"] == "motion")["requirements"] = ["look"]
        previous = self.patch_plan(narrow)
        with self.assertRaisesRegex(ValueError, "dropped or narrowed: play"):
            self.carry(previous)

    def test_a_changed_check_definition_declines_only_its_own_receipt(self):
        self.through_assembly()

        def widen(plan):
            next(c for c in plan["production"]["checks"] if c["id"] == "boot")["views"] = ["desktop", "mobile"]
        record = self.carry(self.patch_plan(widen))
        self.assertEqual([item["check"] for item in record["declined"]], ["boot"])
        self.assertIn("Check definition changed", record["declined"][0]["reason"])
        self.assertEqual({item["check"] for item in record["carried"]}, {"layout", "rigid", "assembly"})
        status = flow.collect(self.plan, self.root, gate.digest(self.baseline), self.receipts)
        self.assertEqual(status["checks"]["boot"]["status"], "unverified")
        self.assertEqual(status["nextStage"], "preflight")

    def test_a_carried_receipt_whose_inputs_moved_is_not_green(self):
        self.through_assembly()
        previous = self.patch_plan(self.grow)
        self.save("game/boot.json", {"ready": "changed after the patch"})
        record = self.carry(previous)
        self.assertFalse(next(item for item in record["carried"] if item["check"] == "boot")["inputsUnchanged"])
        status = flow.collect(self.plan, self.root, gate.digest(self.baseline), self.receipts)
        self.assertEqual(status["checks"]["boot"]["status"], "unverified")

    def test_patching_the_plan_does_not_clear_the_two_failure_counter(self):
        self.complete("boot", "fail")
        self.complete("boot", "fail")
        self.carry(self.patch_plan(self.grow))
        self.assertTrue(flow.collect(self.plan, self.root, gate.digest(self.baseline), self.receipts)["checks"]["boot"]["strategyRequired"])
        with self.assertRaisesRegex(ValueError, "Two failed attempts"):
            self.start("boot")

    def test_one_carryover_per_baseline_and_no_reconciliation_without_the_protected_surface(self):
        self.through_assembly()
        previous = self.patch_plan(self.grow)
        self.carry(previous)
        with self.assertRaisesRegex(ValueError, "already names this baseline"):
            self.carry(previous, name="carry-again.json")
        stale = gate.read(previous)
        del stale["productionChecks"]
        previous.write_text(json.dumps(stale), encoding="utf8")
        with self.assertRaisesRegex(ValueError, "predates carry-over"):
            self.carry(previous, name="carry-stale.json")

    def test_carryover_needs_a_reason_and_the_same_patched_plan(self):
        self.through_assembly()
        previous = self.patch_plan(self.grow)
        with self.assertRaisesRegex(ValueError, "why the plan was patched"):
            self.carry(previous, reason="   ", name="carry-blank.json")
        with self.assertRaisesRegex(ValueError, "not the current one"):
            self.carry(self.baseline, name="carry-self.json")
        other = gate.read(previous)
        other["plan"] = str(self.root / "game/other-plan.json")
        previous.write_text(json.dumps(other), encoding="utf8")
        with self.assertRaisesRegex(ValueError, "different plan file"):
            self.carry(previous, name="carry-other.json")

    def assert_cli_acceptance(self):
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
        return json.loads(accepted.stdout)


if __name__ == "__main__":
    unittest.main()
