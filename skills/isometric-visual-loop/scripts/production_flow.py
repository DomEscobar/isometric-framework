"""Hash-bound authoring stages. Controls its own transitions, not arbitrary agent tools."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
from datetime import datetime, timezone

STAGES = ("preflight", "layout", "assembly", "static", "motion", "final")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name+".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def local(root, name):
    require(isinstance(name, str) and name and ":" not in name and "\\" not in name
            and not Path(name).is_absolute(), "Use project-relative forward-slash paths")
    path = root / name
    require(not any(p.is_symlink() for p in [path, *path.parents]), "No symlinked inputs")
    path = path.resolve()
    require(path.is_relative_to(root), "Input leaves project root")
    return path


def inputs(root, names):
    result = {}
    for name in names:
        path = local(root, name)
        require(path.exists(), f"Missing production input: {name}")
        files = sorted(path.rglob("*")) if path.is_dir() else [path]
        for file in files:
            require(not file.is_symlink(), "No symlinked inputs")
            if file.is_file():
                result[str(file.relative_to(root)).replace("\\", "/")] = sha(file)
    require(result, "Check has no source files")
    return result


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def records(directory, kind):
    found = []
    for path in sorted(Path(directory).glob("*.json")):
        value = read(path)
        if isinstance(value, dict) and value.get("kind") == kind:
            found.append((value, path))
    return found


def carried(directory, baseline_hash):
    """Receipt hashes an explicit carry-over admits from an earlier baseline."""
    matching = [value for value, _ in records(directory, "production-carryover")
                if value.get("baselineSha256") == baseline_hash]
    require(len(matching) <= 1, "Several carry-over records claim this baseline; keep exactly one")
    if not matching:
        return set()
    entries = matching[0].get("carried")
    require(isinstance(entries, list), "Carry-over record needs a carried array")
    return {entry["receiptSha256"] for entry in entries}


def _inside_input(root, name, declared):
    path = local(root, name)
    return any(path == local(root, item) or path.is_relative_to(local(root, item)) for item in declared)


def _geometry_path(root, geometry, name):
    require(isinstance(name, str) and name and ":" not in name and "\\" not in name and not Path(name).is_absolute(),
            "Geometry references must be project-relative forward-slash paths")
    path = (geometry.parent / name).resolve()
    require(path.is_relative_to(root) and path.is_file() and not path.is_symlink(), "Geometry reference is missing or leaves project root")
    return path


def _v5_landscape(plan, root, checks):
    """Validate the small v5 landscape contract without creating another stage flow."""
    flow = plan["production"]
    land = flow.get("landscape")
    require(isinstance(land, dict), "V5 production needs a landscape contract")
    required = {"geometrySource", "compositionRecipe", "densityMatrix", "decisions", "compositionReport", "pairedCaptures", "wholeMapViews"}
    require(required <= set(land), "V5 landscape needs geometrySource, compositionRecipe, densityMatrix, decisions, compositionReport, pairedCaptures and wholeMapViews")
    geometry_path = local(root, land["geometrySource"])
    geometry = read(geometry_path)
    require(isinstance(geometry, dict) and isinstance(geometry.get("coordinateSpace"), str) and geometry["coordinateSpace"].strip(),
            "Geometry export needs coordinateSpace")
    require((isinstance(geometry.get("projection"), dict) or isinstance(geometry.get("projection"), str) and geometry["projection"].strip()) and isinstance(geometry.get("origin"), list) and len(geometry["origin"]) == 2
            and all(isinstance(x, (int, float)) for x in geometry["origin"]), "Geometry export needs projection and numeric origin")
    require(isinstance(geometry.get("canvas"), list) and len(geometry["canvas"]) == 2 and all(type(x) is int and x > 0 for x in geometry["canvas"]),
            "Geometry export needs positive canvas bounds")
    require(isinstance(geometry.get("layout"), dict) and isinstance(geometry["layout"].get("path"), str), "Geometry export needs layout path")
    nested = [_geometry_path(root, geometry_path, geometry["layout"]["path"])]
    for entry, path in ((geometry["layout"], nested[0]),):
        require(isinstance(entry.get("sha256"), str) and entry["sha256"] == sha(path), "Geometry layout hash is stale")
    masks = geometry.get("masks")
    require(isinstance(masks, dict) and masks and all(isinstance(mid, str) and mid and isinstance(value, dict) and isinstance(value.get("path"), str) for mid, value in masks.items()),
            "Geometry export needs named semantic masks")
    for value in masks.values():
        path = _geometry_path(root, geometry_path, value["path"])
        require(isinstance(value.get("sha256"), str) and value["sha256"] == sha(path), "Geometry mask hash is stale")
        nested.append(path)
    instances = geometry.get("instances")
    require(isinstance(instances, list) and all(isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]
            and isinstance(item.get("anchor"), list) and len(item["anchor"]) == 2 and isinstance(item.get("transform"), dict) for item in instances),
            "Geometry export instances need id, anchor and transform")
    require(len({item["id"] for item in instances}) == len(instances), "Geometry instance IDs must be unique")
    density = read(local(root, land["densityMatrix"]))
    require(isinstance(density, dict) and density.get("version") == 1 and isinstance(density.get("views"), list) and density["views"],
            "V5 densityMatrix version 1 needs named views")
    density_fields = {"id", "sourcePixels", "exportPixels", "worldSize", "cameraZoom", "cssViewport", "dpr", "rendererPixels", "textures", "rendererLimits"}
    require(all(isinstance(view, dict) and density_fields <= set(view) and isinstance(view["id"], str) and view["id"]
            and all(isinstance(view[key], (int, float)) and math.isfinite(view[key]) and view[key] > 0 for key in ("cameraZoom", "dpr"))
            and all(isinstance(view[key], list) and len(view[key]) == 2 and all(type(value) is int and value > 0 for value in view[key])
                    for key in ("sourcePixels", "exportPixels", "worldSize", "cssViewport", "rendererPixels", "textures"))
            and isinstance(view["rendererLimits"], dict) and type(view["rendererLimits"].get("maxTexture")) is int and view["rendererLimits"]["maxTexture"] >= max(view["textures"])
            for view in density["views"]) and len({view["id"] for view in density["views"]}) == len(density["views"]),
            "Each density view needs source/export/world/zoom/viewport/DPR/renderer/textures/limits")
    decisions = read(local(root, land["decisions"]))
    require(isinstance(decisions, dict) and decisions.get("version") == 1 and isinstance(decisions.get("decisions"), list),
            "V5 decisions version 1 required")
    ids = set()
    for decision in decisions["decisions"]:
        require(isinstance(decision, dict) and isinstance(decision.get("id"), str) and decision["id"] not in ids
                and decision.get("status") in ("selected", "rejected", "stopped", "abandoned"), "Decision needs unique id and known status")
        ids.add(decision["id"])
        require(isinstance(decision.get("scope"), str) and decision["scope"].strip() and isinstance(decision.get("variant"), str) and decision["variant"].strip()
                and isinstance(decision.get("evidence"), str) and decision["evidence"].strip(), "Decision needs scope, variant and evidence")
    prior = {}
    for decision in decisions["decisions"]:
        key = (decision["scope"], decision["variant"])
        if decision["status"] == "selected" and prior.get(key) == "stopped":
            require(isinstance(decision.get("authorization"), str) and decision["authorization"].strip(),
                    "Stopped decision cannot become active without later authorization")
        prior[key] = decision["status"]
    pairs = land["pairedCaptures"]
    require(isinstance(pairs, list) and pairs and all(isinstance(p, dict) and set(p) == {"id", "ground", "dressed"}
            and all(isinstance(p[k], str) and p[k] for k in ("id", "ground", "dressed")) for p in pairs),
            "V5 pairedCaptures need id, ground and dressed capture IDs")
    require(isinstance(land["wholeMapViews"], list) and land["wholeMapViews"] and all(isinstance(v, str) and v for v in land["wholeMapViews"]),
            "V5 wholeMapViews required")
    for check in checks.values():
        if check["method"] == "layout":
            require(local(root, check["source"]) == nested[0],
                    "V5 layout checks must consume the geometry export's layout")
        if check["stage"] == "preflight":
            required_inputs = (land["geometrySource"], land["compositionRecipe"], land["densityMatrix"], land["decisions"])
        elif check["stage"] in ("assembly", "static", "final"):
            required_inputs = (land["geometrySource"], land["compositionRecipe"], land["densityMatrix"], land["decisions"], land["compositionReport"])
        else:
            required_inputs = ()
        for item in required_inputs:
            require(_inside_input(root, item, check["inputs"]), "V5 landscape dependency must be a declared check input: " + item)
        if required_inputs:
            for item in nested:
                relative = str(item.relative_to(root)).replace("\\", "/")
                require(_inside_input(root, relative, check["inputs"]), "Transitive geometry dependency must be a declared check input: " + relative)
    return land


def _v5_composition(root, land, snapshot):
    geometry = local(root, land["geometrySource"])
    recipe = local(root, land["compositionRecipe"])
    report_path = local(root, land["compositionReport"])
    report = read(report_path)
    report_source = report.get("geometrySource")
    recipe_data = read(recipe)
    recipe_geometry = _geometry_path(root, recipe, recipe_data.get("geometrySource")) if isinstance(recipe_data, dict) else None
    require(recipe_geometry == geometry and report_source == land["geometrySource"] and report.get("geometrySha256") == sha(geometry)
            and report.get("recipeSha256") == sha(recipe),
            "Composition report geometry source or hash is stale")
    source_hashes = report.get("inputHashes")
    require(isinstance(source_hashes, dict) and source_hashes, "Composition report needs nonempty inputHashes")
    geometry_data = read(geometry)
    consumed = {recipe, geometry, _geometry_path(root, geometry, geometry_data["layout"]["path"])}
    consumed.update(_geometry_path(root, geometry, entry["path"]) for entry in geometry_data["masks"].values())
    surface = recipe_data.get("surface")
    if isinstance(surface, dict):
        packed = _geometry_path(root, recipe, surface.get("packedArt"))
        consumed.update((packed, _geometry_path(root, packed, surface.get("groundPng"))))
    consumed.update(_geometry_path(root, recipe, path) for path in recipe_data.get("regionalMaterials", {}).values())
    for category in ("contacts", "underlays"):
        consumed.update(_geometry_path(root, recipe, item.get("asset")) for item in recipe_data.get(category, []))
    require({path.relative_to(root).as_posix() for path in consumed} <= set(source_hashes),
            "Composition report inputHashes omit consumed inputs")
    for name, expected in source_hashes.items():
        file = local(root, name)
        require(isinstance(expected, str) and sha(file) == expected and snapshot.get(name) == expected,
                "Composition report input is stale or not a declared source input: " + str(name))
    for key in ("protectedPixelReport", "output"):
        entry = report.get(key)
        require(isinstance(entry, dict) and isinstance(entry.get("path"), str) and isinstance(entry.get("sha256"), str),
                "Composition report needs hashed " + key)
        file = _geometry_path(root, report_path, entry["path"])
        require(sha(file) == entry["sha256"], "Composition report " + key + " is stale")
        relative = str(file.relative_to(root)).replace("\\", "/")
        require(relative in snapshot and snapshot[relative] == entry["sha256"], "Composition derivative is not a declared source input")
    require(report.get("passOrder") == ["baseSurface", "regionalContacts", "objectUnderlays"],
            "Composition report needs the ordered base/contact/underlay passes")
    require(report.get("protectedPixelReport", {}).get("unchangedAfterUnderlays") is True, "Composition report must prove protected pixels stayed unchanged after underlays")


def validate(plan, root):
    require(plan.get("version") in (4, 5), "New world production requires acceptance-plan version 4 or 5")
    if plan.get("version") == 5:
        require(plan.get("reviewMode") == "independent", "V5 landscape production requires independent review")
    flow = plan.get("production")
    expected_flow_version = 2 if plan.get("version") == 5 else 1
    require(isinstance(flow, dict) and flow.get("version") == expected_flow_version,
            "Production version %s required" % expected_flow_version)
    checks = flow.get("checks")
    require(isinstance(checks, list) and checks, "Production checks required")
    requirements = {r["id"]: r for r in plan["requirements"]}
    by_id = {}
    coverage = set()
    for check in checks:
        cid = check.get("id")
        require(isinstance(cid, str) and cid and cid not in by_id, "Unique production check IDs required")
        by_id[cid] = check
        require(check.get("stage") in STAGES and check.get("method") in ("review", "layout", "art"), "Unknown stage/method")
        require(isinstance(check.get("requirements"), list) and check["requirements"]
                and set(check["requirements"]) <= set(requirements), "Check must link protected requirements")
        require(isinstance(check.get("views"), list) and check["views"]
                and all(isinstance(v, str) and v for v in check["views"]), "Check needs explicit views")
        require(check.get("evidenceKind") in ("image", "motion", "measurement"), "Declare image/motion/measurement evidenceKind")
        if check["method"] == "review" and check["stage"] in ("assembly", "static", "final"):
            require(check["evidenceKind"] == "image", "Assembly/static/final reviews need actual images")
        if check["stage"] == "motion" and any(requirements[r]["domain"] == "motion" for r in check["requirements"]):
            require(check["evidenceKind"] == "motion", "Motion requirements need motion evidence")
        require(isinstance(check.get("inputs"), list) and check["inputs"], "Check needs explicit source dependencies")
        for name in check["inputs"]:
            path = local(root, name)
            require(any(path == local(root, p) or path.is_relative_to(local(root, p)) for p in plan["inputRoots"]),
                    "Production dependencies must be covered by inputRoots")
        if check["stage"] == "final":
            require(all(any(local(root, p) == local(root, name) or local(root, p).is_relative_to(local(root, name))
                            for name in check["inputs"]) for p in plan["inputRoots"]),
                    "Final review must depend on every source inputRoot")
        if check["method"] in ("layout", "art"):
            source = check.get("source")
            require(isinstance(source, str) and any(local(root, source) == local(root, p)
                    or local(root, source).is_relative_to(local(root, p)) for p in check["inputs"]),
                    "Checker source must be a declared dependency")
        if plan.get("version") >= 4 and STAGES.index(check["stage"]) >= STAGES.index("static"):
            policy = plan["assetPolicy"]
            protected = [policy["coverageLedger"], policy["runtime"]["manifest"], policy["runtime"]["binding"]]
            for target in protected:
                target_path = local(root, target)
                require(any(target_path == local(root, dependency) or target_path.is_relative_to(local(root, dependency))
                            for dependency in check["inputs"]),
                        "V4 static and later checks must hash provenance ledger, manifest and binding dependencies")
        if check["method"] == "layout":
            scope = check.get("requiredScope")
            require(isinstance(scope, dict) and set(scope) == {"regions", "instances", "routes", "bridges"}
                    and all(isinstance(v, list) and len(v) == len(set(v)) and all(isinstance(i, str) and i for i in v) for v in scope.values()),
                    "Protect required layout region/instance/route/bridge IDs")
            require(scope["regions"] and scope["routes"], "Layout needs protected regions and traversal routes")
            contract_name = check.get("artContract")
            if check["stage"] == "static":
                require(isinstance(contract_name, str) and contract_name,
                        "Static placement must measure placed footprints against calibrated art; declare artContract")
            if contract_name is not None:
                require(isinstance(contract_name, str) and any(local(root, contract_name) == local(root, p)
                        or local(root, contract_name).is_relative_to(local(root, p)) for p in check["inputs"]),
                        "artContract must be a declared dependency")
            if plan.get("version") >= 4 and check["stage"] == "layout":
                require(check["evidenceKind"] == "image", "V4 layout requires a blockout image review")
        if plan.get("version") >= 4 and check["stage"] == "layout" and check["method"] == "review":
            require(check["evidenceKind"] == "image", "V4 layout review requires blockout images")
        for rid in check["requirements"]:
            if check["method"] == "review" and check["stage"] == ("static" if requirements[rid]["domain"] == "visual" else "motion"):
                coverage.update((rid, view) for view in check["views"])
    require(set(c["stage"] for c in checks) == set(STAGES), "All six production stages need checks")
    require(any(c["method"] == "layout" and c["stage"] == "layout" for c in checks)
            and any(c["method"] == "layout" and c["stage"] == "static" for c in checks), "Layout and full placement checks required")
    require(any(c["method"] == "review" for c in checks if c["stage"] == "assembly"), "Live assembly review required")
    require(any(c["method"] == "review" for c in checks if c["stage"] == "final"), "Final whole-world review required")
    require(all((r["id"], v) in coverage for r in requirements.values() for v in r["views"]),
            "Production checks omit protected requirement/view coverage")
    rigid = flow.get("rigidAssets")
    require(isinstance(rigid, list) and rigid and len(set(rigid)) == len(rigid),
            "Declare unique nonempty rigidAssets; empty lists cannot skip geometry calibration")
    checked = set()
    for c in checks:
        if c["method"] == "art":
            require(isinstance(c.get("assets"), list) and c["assets"], "Art check needs protected asset IDs")
            require(isinstance(c.get("binding"), str) and any(local(root, c["binding"]) == local(root, p)
                    or local(root, c["binding"]).is_relative_to(local(root, p)) for p in c["inputs"]),
                    "Actual host binding must be a declared dependency")
            checked.update(c["assets"])
    require(set(rigid) <= checked, "Rigid asset geometry coverage missing")
    require(any(c["method"] == "art" and c["stage"] == "assembly" for c in checks), "Rigid assembly calibration required")
    if plan.get("version") == 5:
        _v5_landscape(plan, root, by_id)
    return by_id


def evidence(root, values, views, kind, not_before_ns=None):
    require(isinstance(values, list) and values, "Evidence required")
    covered = set()
    for item in values:
        path = local(root, item["path"])
        require(path.is_file() and path.stat().st_size and sha(path) == item["sha256"], "Missing, empty or changed evidence")
        if not_before_ns is not None:
            require(path.stat().st_mtime_ns >= not_before_ns, "Evidence predates capture ticket; recapture after begin")
        extensions = {"image": (".png", ".jpg", ".jpeg", ".webp"), "motion": (".webm", ".mp4", ".gif"), "measurement": (".json", ".txt")}
        require(path.suffix.lower() in extensions[kind], "Evidence format does not match protected evidenceKind")
        if kind == "image":
            module("visual_compare").image_info(path)
        covered.add(item["view"])
    require(set(views) <= covered, "Missing required view evidence")


def automatic(check, root, snapshot):
    if check["method"] == "layout":
        layout = read(local(root, check["source"]))
        report = module("spatial_checks").inspect(layout)
        require(all(set(ids) <= set(report["scope"][kind]) for kind, ids in check["requiredScope"].items()),
                "Protected layout scope missing from current export")
        if check.get("artContract"):
            placement = module("placement_checks").inspect(layout, read(local(root, check["artContract"])))
            report = {**report, "passed": report["passed"] and placement["passed"],
                      "findings": report["findings"] + placement["findings"]}
        return report
    if check["method"] == "art":
        script = Path(__file__).resolve().parents[2] / "isometric-art-integration/scripts/check-art.mjs"
        contract_path = local(root, check["source"])
        contract = read(contract_path)
        if contract.get("overhangRulings"):
            # A classification decides whether art may leave its footprint, so the file holding it
            # has to be hashed with the rest; otherwise a verdict can be rewritten after acceptance.
            target = (contract_path.parent / contract["overhangRulings"]).resolve()
            require(any(target == local(root, p) or target.is_relative_to(local(root, p)) for p in check["inputs"]),
                    "Classified overhang rulings must be a declared dependency of the art check")
        binding = read(local(root, check["binding"]))
        require(binding["projection"] == contract["projection"], "Host projection differs from measured contract")
        assets = {a["id"]: a for a in contract["assets"]}
        require(set(check["assets"]) <= set(assets), "Required rigid assets missing from measured contract")
        unprotected = sorted(set(binding["assets"]) - set(check["assets"]))
        require(not unprotected,
                "Host binding exports rigid assets that this check does not protect: "+", ".join(unprotected))
        for asset in assets.values():
            path = (contract_path.parent / asset["image"]).resolve()
            require(path.is_relative_to(root) and snapshot.get(path.relative_to(root).as_posix()) == sha(path),
                    "Every inspected rigid image must be in check dependencies")
        for aid in check["assets"]:
            asset, actual = assets[aid], binding["assets"][aid]
            require(all(actual[k] == asset[k] for k in ("frame", "anchor", "render", "footprint")),
                    "Host frame/anchor/scale/footprint differs from measured contract: "+aid)
            require(local(root, actual["image"]) == (contract_path.parent / asset["image"]).resolve(),
                    "Host image differs from measured contract: "+aid)
        result = subprocess.run(["node", str(script), str(contract_path)], capture_output=True, text=True, timeout=60)
        require(result.returncode in (0, 1), "Rigid-art checker could not run")
        report = json.loads(result.stdout)
        measured = {a["id"]: a["bodyHeightPx"] for a in report["assets"] if "bodyHeightPx" in a}
        for aid in check["assets"]:
            if aid not in measured:
                continue
            slack = (contract.get("tolerances") or {}).get("heightErrorPx")
            require(type(slack) in (int, float) and math.isfinite(slack) and slack >= 0,
                    "Contract needs a finite nonnegative heightErrorPx to weigh body height against")
            declared = binding["assets"][aid].get("bodyHeight")
            require(type(declared) in (int, float) and math.isfinite(declared),
                    "Host must declare the bodyHeight it sorts and collides with: "+aid)
            # Only the floor is a defect. A body taller than its art is a deliberate collider,
            # but art rising above the declared body sorts and blocks as a stub while towering.
            low = measured[aid]["low"]
            require(declared >= low - slack,
                    f"Host bodyHeight {declared} for {aid} is below the {low:.1f} px its artwork needs "
                    "even when the highest pixel is read as the farthest cell: the renderer orders depth "
                    "and blocks movement with that number, so the art would sink behind ground it covers")
        return {"passed": report["passed"] and result.returncode == 0, "findings": report["errors"]}
    return None


def collect(plan, root, baseline_hash, directory):
    checks = validate(plan, root)
    admitted = carried(directory, baseline_hash)
    latest = {}
    histories = {}
    ignored = []
    provenance_checked = False
    for value, path in records(directory, "production-receipt"):
        if value.get("baselineSha256") != baseline_hash and sha(path) not in admitted:
            ignored.append(str(path))
            continue
        cid = value.get("check")
        require(cid in checks, "Receipt names unknown check")
        histories.setdefault(cid, []).append((value, path))
        if cid not in latest or value["completedAt"] > latest[cid][0]["completedAt"]:
            latest[cid] = (value, path)
    statuses = {}
    for cid, check in checks.items():
        history = sorted(histories.get(cid, []), key=lambda r: r[0]["completedAt"], reverse=True)
        strategy_required = repeated_failure(history)
        base = {"stage": check["stage"], "views": check["views"],
                "evidenceKind": check["evidenceKind"], "declaredInputs": check["inputs"],
                "strategyRequired": strategy_required}
        try:
            current_inputs = inputs(root, check["inputs"])
        except (ValueError, OSError) as error:
            statuses[cid] = {**base, "status": "unverified", "reason": str(error),
                             "inputIssue": str(error)}
            continue
        if cid not in latest:
            statuses[cid] = {**base, "status": "unverified", "reason": "No receipt"}
            continue
        receipt, path = latest[cid]
        try:
            require(receipt["inputs"] == current_inputs, "Source dependencies changed")
            evidence(root, receipt["evidence"], check["views"], check["evidenceKind"])
            require(receipt["status"] in ("pass", "fail", "unverified"), "Invalid receipt status")
            if plan.get("version") == 5:
                _v5_receipt(root, check, receipt, plan["production"]["landscape"], current_inputs)
            report = automatic(check, root, receipt["inputs"])
            if (plan.get("version") >= 4 and not provenance_checked
                    and STAGES.index(check["stage"]) >= STAGES.index("static")):
                module("asset_provenance").verify(plan, root)
                provenance_checked = True
            status = "fail" if report and not report["passed"] else receipt["status"]
            statuses[cid] = {**base, "status": status, "receipt": str(path), "reason": receipt["observed"]}
        except (ValueError, OSError, KeyError) as error:
            statuses[cid] = {**base, "status": "unverified", "reason": str(error)}
    stages = {s: all(statuses[c["id"]]["status"] == "pass" for c in checks.values() if c["stage"] == s) for s in STAGES}
    next_stage = next((s for s in STAGES if not stages[s]), "complete")
    for cid, check in checks.items():
        previous = STAGES[:STAGES.index(check["stage"])]
        blockers = []
        if not all(stages[stage] for stage in previous):
            blockers.append("Earlier stage not accepted: " + next_stage)
        if statuses[cid]["strategyRequired"]:
            blockers.append("Two failed attempts: supply --strategy with a new hypothesis and discriminating test")
        if statuses[cid].get("inputIssue"):
            blockers.append(statuses[cid]["inputIssue"])
        if statuses[cid]["status"] == "pass":
            blockers.append("Current receipt already passes; preserve it while inputs remain unchanged")
        statuses[cid]["eligible"] = not blockers
        statuses[cid]["blockers"] = blockers
    return {"passed": all(stages.values()), "nextStage": next_stage, "stages": stages, "checks": statuses,
            "ignoredReceipts": sorted(ignored)}


def next_work(status):
    """A non-mutating, actionable view of status; incomplete is never success."""
    candidates = [{"id": cid, "stage": value["stage"], "views": value["views"],
                   "evidenceKind": value["evidenceKind"], "inputs": value["declaredInputs"],
                   "expectedEvidence": {"kind": value["evidenceKind"], "views": value["views"]}}
                  for cid, value in status["checks"].items() if value["eligible"]]
    blockers = {cid: value["blockers"] for cid, value in status["checks"].items()
                if value["stage"] == status["nextStage"] and value["blockers"]}
    if status["passed"]:
        return {**status, "state": "complete", "readyToWork": False, "eligibleChecks": [],
                "missingInputs": [], "blockers": []}
    missing = [value.get("inputIssue") for value in status["checks"].values() if value.get("inputIssue")]
    return {**status, "state": "ready-to-work" if candidates else "incomplete", "readyToWork": bool(candidates),
            "eligibleChecks": candidates, "missingInputs": missing, "blockers": blockers}


def prerequisites(plan, root, baseline_hash, directory, check):
    result = collect(plan, root, baseline_hash, directory)
    needed = STAGES[:STAGES.index(check["stage"])]
    require(all(result["stages"][s] for s in needed), "Earlier stage not accepted: "+result["nextStage"])


def attempts(baseline_hash, directory, cid):
    # Carried receipts stay in the history, or patching the plan would clear the
    # two-failure counter and buy an escape from the strategy requirement.
    admitted = carried(directory, baseline_hash)
    history = []
    for record, path in records(directory, "production-receipt"):
        if record.get("check") != cid:
            continue
        if record.get("baselineSha256") == baseline_hash or sha(path) in admitted:
            history.append((record, path))
    return sorted(history, key=lambda r: r[0]["completedAt"], reverse=True)


def repeated_failure(history):
    return len(history) >= 2 and all(record[0]["status"] == "fail" for record in history[:2])


def _v5_review_submission(root, check, ticket, submission, land):
    author = ticket.get("authorId")
    require(isinstance(author, str) and author.strip(), "V5 ticket authorId required")
    require(submission.get("authorId") == author, "V5 submission authorId must match ticket")
    reviewer = submission.get("reviewer")
    require(isinstance(reviewer, str) and reviewer.strip() and reviewer != author,
            "V5 reviewer must be an identity different from authorId")
    if check["method"] != "review" and check["evidenceKind"] != "image":
        return submission["status"]
    judgments = submission.get("judgments")
    expected = {(rid, view) for rid in check["requirements"] for view in check["views"]}
    require(isinstance(judgments, list), "V5 review needs per-requirement/view judgments")
    found = {(item.get("requirement"), item.get("view")) for item in judgments if isinstance(item, dict)}
    require(found == expected and len(judgments) == len(expected), "V5 review must judge every requirement and view exactly once")
    for item in judgments:
        require(item.get("status") in ("pass", "fail", "unverified") and item.get("reviewer") == reviewer
                and isinstance(item.get("observed"), str) and item["observed"].strip(),
                "V5 judgments need reviewer, status and observation")
    derived = "fail" if any(item["status"] == "fail" for item in judgments) else (
        "unverified" if any(item["status"] == "unverified" for item in judgments) else "pass")
    require(submission["status"] == derived, "V5 review status must be derived from its judgments")
    if check["evidenceKind"] != "image":
        return derived
    metadata = submission.get("captureMetadata")
    require(isinstance(metadata, list) and metadata, "V5 image review needs captureMetadata")
    by_id = {item.get("id"): item for item in metadata if isinstance(item, dict) and isinstance(item.get("id"), str)}
    require(len(by_id) == len(metadata), "V5 captureMetadata IDs must be unique")
    evidence_by_path = {(item["path"], item["sha256"], item["view"]) for item in submission.get("evidence", [])}
    geometry = read(local(root, land["geometrySource"]))
    pairs = {pair["id"]: pair for pair in land["pairedCaptures"]}
    for capture in by_id.values():
        required = {"id", "path", "sha256", "view", "mode", "pairId", "camera", "viewport", "renderer", "worldState", "timeState", "geometrySource", "geometrySha256", "scope", "worldBounds"}
        require(required <= set(capture) and capture["mode"] in ("ground-only", "dressed") and capture["scope"] in ("whole-map", "detail"),
                "V5 capture metadata is incomplete")
        require(capture["geometrySource"] == land["geometrySource"], "Capture geometry source differs from landscape contract")
        require(capture["geometrySha256"] == sha(local(root, land["geometrySource"])), "Capture geometry hash is stale")
        require((capture["path"], capture["sha256"], capture["view"]) in evidence_by_path, "Capture metadata must bind actual evidence path, hash and view")
        require(isinstance(capture["worldBounds"], list) and len(capture["worldBounds"]) == 2
                and all(type(value) is int and value > 0 for value in capture["worldBounds"]),
                "Capture worldBounds need positive width and height")
        if capture["scope"] == "whole-map":
            require(capture["worldBounds"] == geometry["canvas"], "Whole-map capture bounds must match geometry canvas")
    if check["stage"] in ("assembly", "static", "final"):
        for pair_id, pair in pairs.items():
            ground, dressed = by_id.get(pair["ground"]), by_id.get(pair["dressed"])
            require(ground and dressed and ground["mode"] == "ground-only" and dressed["mode"] == "dressed" and ground["pairId"] == dressed["pairId"] == pair_id,
                    "V5 ground/dressed pair is missing")
            for key in ("camera", "viewport", "renderer", "worldState", "timeState", "geometrySource", "geometrySha256", "worldBounds", "scope"):
                require(ground[key] == dressed[key], "Ground/dressed pair differs in " + key)
    required_whole = set(land["wholeMapViews"])
    whole = {capture["view"] for capture in by_id.values() if capture["scope"] == "whole-map"}
    if check["stage"] == "final":
        require(required_whole <= whole, "V5 final scope needs declared whole-map views")
    detail = {capture["view"] for capture in by_id.values() if capture["scope"] == "detail"}
    if check["stage"] in ("static", "final"):
        require(detail, "V5 image review needs a representative detail capture")
    return derived


def _v5_receipt(root, check, receipt, land, snapshot):
    author = receipt.get("authorId")
    require(isinstance(author, str) and author.strip() and receipt.get("reviewer") != author,
            "V5 receipt authorId/reviewer chain is invalid")
    if check["method"] == "review" or check["evidenceKind"] == "image":
        _v5_review_submission(root, check, {"authorId": author}, receipt, land)
    if check["stage"] in ("assembly", "static", "final"):
        _v5_composition(root, land, snapshot)


def carryover(gate, baseline, previous_baseline, directory, reason, output):
    """Admit earlier receipts under a patched plan.

    Admission is visibility only. collect still re-verifies inputs, evidence and the
    automatic checkers, so carrying a receipt cannot turn a stale stage green.
    """
    _, plan, root = gate.protected(baseline)
    checks = validate(plan, root)
    current_hash, previous_hash = sha(baseline), sha(previous_baseline)
    require(current_hash != previous_hash, "Carry-over needs an earlier baseline, not the current one")
    require(isinstance(reason, str) and reason.strip(), "Record why the plan was patched")
    earlier = read(previous_baseline)
    require(earlier.get("plan") == read(baseline).get("plan"),
            "Carry-over reconciles a patched plan, not receipts from a different plan file")
    require(isinstance(earlier.get("requirements"), list) and isinstance(earlier.get("productionChecks"), dict),
            "Earlier baseline predates carry-over and cannot prove the plan only grew; re-run its stages")
    require(earlier.get("reviewMode") == plan["reviewMode"],
            "Review mode changed; reconcile that before carrying receipts")
    kept = {requirement["id"]: requirement for requirement in plan["requirements"]}
    for requirement in earlier["requirements"]:
        require(kept.get(requirement["id"]) == requirement,
                "Protected requirement dropped or narrowed: " + str(requirement.get("id")))
    require(not carried(directory, current_hash), "A carry-over already names this baseline")
    # Receipts keep the hash of the baseline that produced them, so a second patch has to
    # reconsider whatever the previous patch already admitted, not just fresh receipts.
    inherited = carried(directory, previous_hash)
    admitted, declined = [], []
    for receipt, path in records(directory, "production-receipt"):
        if receipt.get("baselineSha256") != previous_hash and sha(path) not in inherited:
            continue
        cid = receipt.get("check")
        entry = {"check": cid, "receiptSha256": sha(path), "receipt": str(path)}
        if cid not in checks:
            declined.append({**entry, "reason": "Check no longer exists in the patched plan"})
        elif earlier["productionChecks"].get(cid) != fingerprint(checks[cid]):
            declined.append({**entry, "reason": "Check definition changed; run it again under the patched plan"})
        else:
            try:
                fresh = inputs(root, checks[cid]["inputs"]) == receipt.get("inputs")
            except (ValueError, OSError):
                fresh = False
            admitted.append({**entry, "inputsUnchanged": fresh})
    require(admitted or declined, "No receipts belong to that baseline; check the earlier baseline path")
    target = Path(output).resolve()
    require(target.parent == Path(directory).resolve(), "Carry-over must live directly in its receipt directory")
    require(all(not target.is_relative_to(local(root, p)) for p in plan["inputRoots"]),
            "Carry-over must be outside source inputRoots")
    value = {"kind": "production-carryover", "baselineSha256": current_hash,
             "previousBaselineSha256": previous_hash, "reason": reason.strip(),
             "carried": admitted, "declined": declined,
             "createdAt": datetime.now(timezone.utc).isoformat()}
    gate.write_new(output, value)
    return value


def begin(gate, baseline, cid, directory, output, strategy=None, author_id=None):
    _, plan, root = gate.protected(baseline)
    checks = validate(plan, root)
    require(cid in checks, "Unknown production check")
    check = checks[cid]
    prerequisites(plan, root, sha(baseline), directory, check)
    history = attempts(sha(baseline), directory, cid)
    strategy_record = None
    if repeated_failure(history):
        require(strategy, "Two failed attempts: supply --strategy with a new hypothesis and discriminating test")
        change = read(strategy)
        require(change.get("check") == cid and change.get("previousReceiptSha256") == sha(history[0][1])
                and all(isinstance(change.get(k), str) and change[k].strip() for k in ("hypothesis", "test")),
                "Strategy must name latest receipt, check, hypothesis and test")
        strategy_record = {"sha256": sha(strategy), "change": change}
    target = Path(output).resolve()
    require(all(not target.is_relative_to(local(root, p)) for p in plan["inputRoots"]), "Tickets must be outside source inputRoots")
    if plan.get("version") == 5:
        require(isinstance(author_id, str) and author_id.strip(), "V5 begin needs --author-id")
    gate.write_new(output, {"kind": "production-ticket", "baselineSha256": sha(baseline), "check": cid,
                           "previousReceiptSha256": sha(history[0][1]) if history else None,
                           "inputs": inputs(root, check["inputs"]), "strategy": strategy_record,
                           "authorId": author_id.strip() if isinstance(author_id, str) else None,
                           "startedAt": datetime.now(timezone.utc).isoformat()})


def draft(gate, baseline, ticket_path, mapping_path, output):
    """Write a review template only after validating the proposed evidence."""
    _, plan, root = gate.protected(baseline)
    ticket, mapping = read(ticket_path), read(mapping_path)
    require(ticket.get("kind") == "production-ticket" and ticket.get("baselineSha256") == sha(baseline),
            "Ticket baseline mismatch")
    check = validate(plan, root).get(ticket.get("check"))
    require(check is not None, "Ticket names unknown production check")
    require(ticket.get("inputs") == inputs(root, check["inputs"]),
            "Inputs changed since begin; make a new ticket before recapturing")
    values = mapping.get("evidence") if isinstance(mapping, dict) else None
    require(isinstance(values, list), "Evidence mapping needs an evidence array")
    prepared = []
    for item in values:
        require(isinstance(item, dict) and set(item) == {"path", "view"},
                "Evidence mapping entries need only path and view")
        path = local(root, item["path"])
        prepared.append({"path": item["path"], "sha256": sha(path), "view": item["view"]})
    evidence(root, prepared, check["views"], check["evidenceKind"], Path(ticket_path).stat().st_mtime_ns)
    target = Path(output).resolve()
    require(all(not target.is_relative_to(local(root, p)) for p in plan["inputRoots"]),
            "Drafts must be outside source inputRoots")
    value = {"ticketSha256": sha(ticket_path), "status": "unverified", "reviewer": "", "observed": "", "evidence": prepared}
    if plan.get("version") == 5:
        require(isinstance(ticket.get("authorId"), str) and ticket["authorId"].strip(), "V5 ticket authorId required")
        value["authorId"] = ticket["authorId"]
        if check["method"] == "review" or check["evidenceKind"] == "image":
            value["judgments"] = [{"requirement": requirement, "view": view, "status": "unverified", "reviewer": "", "observed": ""}
                                  for requirement in check["requirements"] for view in check["views"]]
        if check["evidenceKind"] == "image":
            supplied = mapping.get("captureMetadata", [])
            require(isinstance(supplied, list), "V5 captureMetadata must be a list")
            value["captureMetadata"] = supplied
    gate.write_new(output, value)


def finish(gate, baseline, ticket_path, submission_path, directory, output):
    _, plan, root = gate.protected(baseline)
    ticket, submission = read(ticket_path), read(submission_path)
    require(ticket.get("kind") == "production-ticket" and ticket["baselineSha256"] == sha(baseline), "Ticket baseline mismatch")
    check = validate(plan, root)[ticket["check"]]
    history = attempts(sha(baseline), directory, check["id"])
    require(not any(r[0].get("ticketSha256") == sha(ticket_path) for r in history), "Ticket already consumed")
    require(ticket.get("previousReceiptSha256") == (sha(history[0][1]) if history else None),
            "Ticket superseded by another attempt; begin again")
    if repeated_failure(history):
        change = (ticket.get("strategy") or {}).get("change", {})
        require(change.get("previousReceiptSha256") == sha(history[0][1]) and change.get("check") == check["id"]
                and all(isinstance(change.get(k), str) and change[k].strip() for k in ("hypothesis", "test")),
                "Strategy change required for repeated failure")
    prerequisites(plan, root, sha(baseline), directory, check)
    require(ticket["inputs"] == inputs(root, check["inputs"]), "Inputs changed since begin; make a new ticket before recapturing")
    require(submission.get("ticketSha256") == sha(ticket_path), "Submission must name the capture ticket hash")
    require(submission.get("status") in ("pass", "fail", "unverified"), "Submission status required")
    require(all(isinstance(submission.get(k), str) and submission[k].strip() for k in ("reviewer", "observed")), "Reviewer and observations required")
    evidence(root, submission.get("evidence"), check["views"], check["evidenceKind"], Path(ticket_path).stat().st_mtime_ns)
    if plan.get("version") == 5:
        _v5_review_submission(root, check, ticket, submission, plan["production"]["landscape"])
    report = automatic(check, root, ticket["inputs"])
    automatic_passed = report is None or report["passed"]
    if plan.get("version") >= 4 and STAGES.index(check["stage"]) >= STAGES.index("static"):
        try:
            provenance = module("asset_provenance").verify(plan, root)
            report = {"provenance": provenance, **({"automatic": report} if report else {})}
        except (ValueError, OSError, KeyError) as error:
            automatic_passed = False
            report = {"provenance": {"passed": False, "error": str(error)},
                      **({"automatic": report} if report else {})}
    if plan.get("version") == 5 and check["stage"] in ("assembly", "static", "final"):
        try:
            _v5_composition(root, plan["production"]["landscape"], ticket["inputs"])
        except (ValueError, OSError, KeyError) as error:
            automatic_passed = False
            report = {"landscape": {"passed": False, "error": str(error)}, **({"automatic": report} if report else {})}
    status = "fail" if not automatic_passed else submission["status"]
    target = Path(output).resolve()
    require(target.parent == Path(directory).resolve(), "Receipt output must be directly in its receipt directory")
    require(all(not target.is_relative_to(local(root, p)) for p in plan["inputRoots"]), "Receipts must be outside source inputRoots")
    gate.protected(baseline)
    require(ticket["inputs"] == inputs(root, check["inputs"]), "Inputs changed during check")
    value = {"kind": "production-receipt", "baselineSha256": sha(baseline), "check": check["id"],
             "inputs": ticket["inputs"], "ticketSha256": sha(ticket_path), "startedAt": ticket["startedAt"],
             "strategy": ticket.get("strategy"), "previousReceiptSha256": ticket.get("previousReceiptSha256"),
             "completedAt": datetime.now(timezone.utc).isoformat(), "status": status,
             "reviewer": submission["reviewer"], "observed": submission["observed"],
             "authorId": ticket.get("authorId"), "judgments": submission.get("judgments"),
             "captureMetadata": submission.get("captureMetadata"), "evidence": submission["evidence"], "automatic": report}
    gate.write_new(output, value)
    return value
