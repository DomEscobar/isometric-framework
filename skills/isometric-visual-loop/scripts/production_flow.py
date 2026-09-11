"""Hash-bound authoring stages. Controls its own transitions, not arbitrary agent tools."""
import hashlib
import importlib.util
import json
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


def validate(plan, root):
    flow = plan.get("production")
    require(isinstance(flow, dict) and flow.get("version") == 1, "Production version 1 required")
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
        if check["method"] == "layout":
            scope = check.get("requiredScope")
            require(isinstance(scope, dict) and set(scope) == {"regions", "instances", "routes", "bridges"}
                    and all(isinstance(v, list) and len(v) == len(set(v)) and all(isinstance(i, str) and i for i in v) for v in scope.values()),
                    "Protect required layout region/instance/route/bridge IDs")
            require(scope["regions"] and scope["routes"], "Layout needs protected regions and traversal routes")
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
    require(isinstance(rigid, list) and len(set(rigid)) == len(rigid), "Declare unique rigidAssets, empty only when absent")
    checked = set()
    for c in checks:
        if c["method"] == "art":
            require(isinstance(c.get("assets"), list) and c["assets"], "Art check needs protected asset IDs")
            require(isinstance(c.get("binding"), str) and any(local(root, c["binding"]) == local(root, p)
                    or local(root, c["binding"]).is_relative_to(local(root, p)) for p in c["inputs"]),
                    "Actual host binding must be a declared dependency")
            checked.update(c["assets"])
    require(set(rigid) <= checked, "Rigid asset geometry coverage missing")
    if rigid:
        require(any(c["method"] == "art" and c["stage"] == "assembly" for c in checks), "Rigid assembly calibration required")
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
        report = module("spatial_checks").inspect(read(local(root, check["source"])))
        require(all(set(ids) <= set(report["scope"][kind]) for kind, ids in check["requiredScope"].items()),
                "Protected layout scope missing from current export")
        return report
    if check["method"] == "art":
        script = Path(__file__).resolve().parents[2] / "isometric-art-integration/scripts/check-art.mjs"
        contract_path = local(root, check["source"])
        contract = read(contract_path)
        binding = read(local(root, check["binding"]))
        require(binding["projection"] == contract["projection"], "Host projection differs from measured contract")
        assets = {a["id"]: a for a in contract["assets"]}
        require(set(check["assets"]) <= set(assets), "Required rigid assets missing from measured contract")
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
        return {"passed": report["passed"] and result.returncode == 0, "findings": report["errors"]}
    return None


def collect(plan, root, baseline_hash, directory):
    checks = validate(plan, root)
    latest = {}
    histories = {}
    for path in sorted(Path(directory).glob("*.json")):
        value = read(path)
        if value.get("kind") != "production-receipt" or value.get("baselineSha256") != baseline_hash:
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
            report = automatic(check, root, receipt["inputs"])
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
    return {"passed": all(stages.values()), "nextStage": next_stage, "stages": stages, "checks": statuses}


def prerequisites(plan, root, baseline_hash, directory, check):
    result = collect(plan, root, baseline_hash, directory)
    needed = STAGES[:STAGES.index(check["stage"])]
    require(all(result["stages"][s] for s in needed), "Earlier stage not accepted: "+result["nextStage"])


def attempts(baseline_hash, directory, cid):
    history = []
    for path in Path(directory).glob("*.json"):
        record = read(path)
        if record.get("kind") == "production-receipt" and record.get("baselineSha256") == baseline_hash and record.get("check") == cid:
            history.append((record, path))
    return sorted(history, key=lambda r: r[0]["completedAt"], reverse=True)


def repeated_failure(history):
    return len(history) >= 2 and all(record[0]["status"] == "fail" for record in history[:2])


def begin(gate, baseline, cid, directory, output, strategy=None):
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
    gate.write_new(output, {"kind": "production-ticket", "baselineSha256": sha(baseline), "check": cid,
                           "previousReceiptSha256": sha(history[0][1]) if history else None,
                           "inputs": inputs(root, check["inputs"]), "strategy": strategy_record,
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
    gate.write_new(output, {"ticketSha256": sha(ticket_path), "status": "unverified",
                            "reviewer": "", "observed": "", "evidence": prepared})


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
    report = automatic(check, root, ticket["inputs"])
    status = "fail" if report and not report["passed"] else submission["status"]
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
             "evidence": submission["evidence"], "automatic": report}
    gate.write_new(output, value)
    return value
