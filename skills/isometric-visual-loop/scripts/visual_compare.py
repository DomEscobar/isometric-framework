"""Build inspectable image comparisons; validate recorded visual judgments.

No model calls or aesthetic scores. The agent must actually inspect the images.
"""
import base64
import hashlib
import io
import json
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def local(base, name):
    require(isinstance(name, str) and name and ":" not in name and "\\" not in name
            and not Path(name).is_absolute(), "Comparison paths must be local and relative")
    return (base / name).resolve()


def image_info(path):
    from PIL import Image
    require(path.stat().st_size <= 32 * 1024 * 1024, "Comparison image exceeds 32 MiB")
    raw = path.read_bytes()
    with Image.open(io.BytesIO(raw)) as im:
        require(im.format in ("PNG", "JPEG", "WEBP") and im.width * im.height <= 16_000_000
                and getattr(im, "n_frames", 1) == 1, "Use static PNG/JPEG/WebP comparisons up to 16 million pixels")
        im.load()
        return {"width": im.width, "height": im.height,
                "mime": Image.MIME[im.format], "sha256": hashlib.sha256(raw).hexdigest()}


def definitions(plan, root):
    specs = plan.get("comparisons", [])
    require(isinstance(specs, list), "comparisons must be a list")
    requirements = {r["id"]: r for r in plan["requirements"]}
    ids, covered, references = set(), set(), {}
    for spec in specs:
        cid = spec.get("id")
        require(isinstance(cid, str) and cid and cid not in ids, "Unique comparison IDs required")
        ids.add(cid)
        require(spec.get("role") in ("style", "layout", "both"), "Declare reference role: style/layout/both")
        require(isinstance(spec.get("focus"), str) and spec["focus"].strip(), "Comparison focus required")
        reqs = spec.get("requirements")
        require(isinstance(reqs, list) and reqs and len(reqs) == len(set(reqs)), "Comparison requirements required")
        for rid in reqs:
            require(rid in requirements and requirements[rid]["domain"] == "visual"
                    and spec.get("view") in requirements[rid]["views"], "Comparison must match a visual requirement/view")
            covered.add((rid, spec["view"]))
        reference = local(root, spec["reference"])
        references[str(reference)] = image_info(reference)["sha256"]
    if plan["version"] >= 2:
        expected = {(r["id"], v) for r in requirements.values() if r["domain"] == "visual" for v in r["views"]}
        require(expected <= covered, "Every visual requirement/view needs a protected comparison")
    return specs, references


def save(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def region(value, image):
    return (isinstance(value, list) and len(value) == 4
            and all(type(n) is int for n in value)
            and value[0] >= 0 and value[1] >= 0 and value[2] > 0 and value[3] > 0
            and value[0] + value[2] <= image["width"] and value[1] + value[3] <= image["height"])


def packet_media(packet_path, packet):
    require(packet.get("version") == 1 and isinstance(packet.get("items"), list) and packet["items"], "Invalid comparison packet")
    for item in packet["items"]:
        for kind in ("reference", "current", "previous"):
            media = item.get(kind)
            if media is None:
                require(kind == "previous", "Reference and current images required")
                continue
            file = local(packet_path.parent, media["path"])
            require(file.is_relative_to(packet_path.parent), "Packet media must stay inside its bundle")
            require(image_info(file) == {k: media[k] for k in ("width", "height", "mime", "sha256")}, "Comparison media changed")
    if packet.get("previousReviewSha256"):
        previous = packet_path.parent / "previous-review.json"
        require(sha(previous) == packet["previousReviewSha256"], "Previous review snapshot changed")
        prior = read(previous)
        if packet.get("baselineChange"):
            change = packet["baselineChange"]
            old_path = packet_path.parent / "previous-packet.json"
            require(sha(old_path) == prior["comparison"]["packetSha256"], "Previous packet snapshot changed")
            old = read(old_path)
            require(change.get("previousBaselineSha256") == old["baselineSha256"]
                    and old["baselineSha256"] != packet["baselineSha256"]
                    and old["requirements"] == packet["requirements"]
                    and old["reviewMode"] == packet["reviewMode"]
                    and isinstance(change.get("reason"), str) and change["reason"].strip(),
                    "Invalid baseline transition or changed protected requirements")
            current_items = {i["definition"]["id"]: i for i in packet["items"]}
            require(all(i["definition"]["id"] in current_items
                        and (i["definition"], i["reference"]["sha256"], i["current"]["sha256"])
                        == (current_items[i["definition"]["id"]]["definition"],
                            current_items[i["definition"]["id"]]["reference"]["sha256"],
                            current_items[i["definition"]["id"]]["previous"]["sha256"])
                        for i in old["items"]),
                    "Baseline transition changed targets, scope or previous images")
        findings = [{"id": o["id"], "comparison": a["id"], "status": o["status"],
                     "difference": o["difference"], "repair": o.get("repair", "")}
                    for a in prior["comparison"]["assessments"] for o in a["observations"] if o["status"] != "pass"]
        require(sorted(findings, key=lambda f: f["id"]) == sorted(packet["priorFindings"], key=lambda f: f["id"]),
                "Previous findings were omitted or changed")
    else:
        require(not packet.get("priorFindings"), "First round cannot invent prior findings")


def inspect_review(review_path):
    review_path = Path(review_path).resolve()
    review = read(review_path)
    comparison = review.get("comparison", {})
    packet_path = local(review_path.parent, comparison["packet"])
    require(sha(packet_path) == comparison.get("packetSha256"), "Comparison packet changed")
    packet = read(packet_path)
    packet_media(packet_path, packet)
    require(review.get("candidateSha256") == packet["candidateSha256"], "Comparison candidate mismatch")
    require(review.get("reviewMode") == packet["reviewMode"], "Comparison review mode mismatch")
    require(isinstance(comparison.get("reviewer"), str) and comparison["reviewer"].strip(), "Comparison reviewer required")
    assessments = comparison.get("assessments")
    require(isinstance(assessments, list), "Comparison assessments required")
    by_id = {a["id"]: a for a in assessments}
    expected = {i["definition"]["id"] for i in packet["items"]}
    require(len(expected) == len(packet["items"]) and len(by_id) == len(assessments)
            and set(by_id) == expected, "Review every comparison exactly once")
    finding_ids, open_findings = set(), []
    for item in packet["items"]:
        cid = item["definition"]["id"]
        assessment = by_id[cid]
        observations = assessment.get("observations")
        require(assessment.get("status") in ("pass", "fail", "unverified")
                and isinstance(observations, list) and observations, "Explicit visual observations required")
        statuses = []
        for obs in observations:
            oid, status = obs.get("id"), obs.get("status")
            require(isinstance(oid, str) and oid and oid not in finding_ids, "Unique stable observation IDs required")
            finding_ids.add(oid)
            require(status in ("pass", "fail", "unverified"), "Observation status required")
            require(isinstance(obs.get("difference"), str) and obs["difference"].strip(), "Describe the observed agreement/difference")
            if status != "unverified":
                require(region(obs.get("currentRegion"), item["current"])
                        and region(obs.get("referenceRegion"), item["reference"]), "Locate observations in both source images")
            if status == "fail":
                require(isinstance(obs.get("repair"), str) and obs["repair"].strip(), "Failed observations need concrete repairs")
            if status != "pass":
                open_findings.append({"id": oid, "comparison": cid, "status": status,
                                      "difference": obs["difference"], "repair": obs.get("repair", "")})
            statuses.append(status)
        derived = "fail" if "fail" in statuses else "unverified" if "unverified" in statuses else "pass"
        require(assessment["status"] == derived, "Comparison status contradicts its observations")
    prior = packet.get("priorFindings", [])
    resolutions = comparison.get("resolutions", [])
    resolved = {r["id"]: r for r in resolutions}
    require(len(resolved) == len(resolutions) and set(resolved) == {f["id"] for f in prior}, "Account for every previous open finding")
    for finding in prior:
        answer = resolved[finding["id"]]
        require(answer.get("status") in ("resolved", "open", "regressed")
                and isinstance(answer.get("reason"), str) and answer["reason"].strip(), "Explain each previous finding's current state")
        destination = answer.get("comparison", finding["comparison"])
        items = {i["definition"]["id"]: i for i in packet["items"]}
        require(destination in items, "Finding resolution names an unknown comparison")
        source, target = items[finding["comparison"]], items[destination]
        require(source["definition"]["view"] == target["definition"]["view"]
                and set(source["definition"]["requirements"]) & set(target["definition"]["requirements"])
                and source["reference"]["sha256"] == target["reference"]["sha256"],
                "Finding relocation must retain its view, requirement and target")
        observations = by_id[destination]["observations"]
        current = next((o for o in observations if o["id"] == finding["id"]), None)
        require(current is not None, "Reinspect each prior finding with the same ID")
        require((answer["status"] == "resolved") == (current["status"] == "pass"), "Resolution contradicts current observation")
    return review, packet_path, packet, open_findings


def build(gate, baseline_path, candidate_path, captures_path, output, previous=None, rebaseline_note=None):
    baseline, plan, root = gate.protected(baseline_path)
    candidate_path, captures_path, output = Path(candidate_path).resolve(), Path(captures_path).resolve(), Path(output).resolve()
    candidate = read(candidate_path)
    require(candidate["baselineSha256"] == sha(baseline_path)
            and candidate["inputs"] == gate.source_hashes(plan, root), "Candidate is stale or belongs to another baseline")
    specs, _ = definitions(plan, root)
    require(specs, "Plan has no protected visual comparisons")
    require(all(not output.is_relative_to(gate.local(root, p)) for p in plan["inputRoots"]), "Comparison output must be outside inputRoots")
    captures = read(captures_path)
    require(set(captures) == {s["id"] for s in specs}, "Supply exactly one current capture per comparison")
    previous_packet, previous_path, prior_findings, baseline_change = None, None, [], None
    previous_items = {}
    if previous:
        _, previous_path, previous_packet, prior_findings = inspect_review(previous)
        require(previous_packet["requirements"] == plan["requirements"]
                and previous_packet["reviewMode"] == plan["reviewMode"], "Previous protected requirements or review mode differ")
        if previous_packet["baselineSha256"] != sha(baseline_path):
            require(isinstance(rebaseline_note, str) and rebaseline_note.strip(),
                    "Previous baseline changed; use --rebaseline-note for an art-check correction or added comparisons, retaining requirements and targets")
            baseline_change = {"previousBaselineSha256": previous_packet["baselineSha256"], "reason": rebaseline_note}
        previous_items = {i["definition"]["id"]: i for i in previous_packet["items"]}
        current_specs = {s["id"]: s for s in specs}
        require(all(cid in current_specs and item["definition"] == current_specs[cid]
                    for cid, item in previous_items.items()), "Previous comparison scope cannot be removed or changed")
    require(rebaseline_note is None or baseline_change is not None, "A rebaseline note needs a previous review from another baseline")
    # Decode all inputs before creating a new immutable bundle.
    sources = []
    for index, spec in enumerate(specs):
        current = captures[spec["id"]]
        require(isinstance(current.get("captureNotes"), str) and current["captureNotes"].strip(), "Describe the live camera, viewport and captured state")
        files = {"reference": local(root, spec["reference"]), "current": local(captures_path.parent, current["path"])}
        prior_item = previous_items.get(spec["id"])
        if prior_item:
            files["previous"] = local(previous_path.parent, prior_item["current"]["path"])
        infos = {kind: image_info(file) for kind, file in files.items()}
        if prior_item:
            require(infos["reference"]["sha256"] == prior_item["reference"]["sha256"],
                    "Previous comparison target differs")
        if spec["role"] in ("layout", "both"):
            dimensions = {(info["width"], info["height"]) for info in infos.values()}
            require(len(dimensions) == 1, "Layout comparisons require matching capture dimensions; do not stretch images")
        sources.append((spec, current["captureNotes"], files, infos))
    output.mkdir(parents=True, exist_ok=False)
    packet = {"version": 1, "baselineSha256": sha(baseline_path), "candidateSha256": sha(candidate_path),
              "reviewMode": plan["reviewMode"], "previousReviewSha256": sha(previous) if previous else None,
              "requirements": plan["requirements"], "baselineChange": baseline_change, "priorFindings": prior_findings, "items": []}
    display = []
    for index, (spec, notes, files, infos) in enumerate(sources):
        item = {"definition": spec, "captureNotes": notes}
        shown = {"definition": spec, "captureNotes": notes}
        for kind, file in files.items():
            raw = file.read_bytes()
            require(hashlib.sha256(raw).hexdigest() == infos[kind]["sha256"], "Capture changed during comparison assembly")
            suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[infos[kind]["mime"]]
            name = f"{index}-{kind}{suffix}"
            with (output / name).open("xb") as stream:
                stream.write(raw)
            item[kind] = {**infos[kind], "path": name}
            shown[kind] = {**item[kind], "url": f"data:{infos[kind]['mime']};base64," + base64.b64encode(raw).decode("ascii")}
        packet["items"].append(item)
        display.append(shown)
    if previous:
        (output / "previous-review.json").write_bytes(Path(previous).read_bytes())
        require(sha(previous) == packet["previousReviewSha256"], "Previous review changed during assembly")
        if baseline_change:
            (output / "previous-packet.json").write_bytes(previous_path.read_bytes())
    require(candidate["inputs"] == gate.source_hashes(plan, root), "Source changed during comparison assembly")
    gate.protected(baseline_path)
    save(output / "packet.json", packet)
    template = {"candidateSha256": sha(candidate_path), "reviewMode": plan["reviewMode"], "verdicts": [],
                "comparison": {"packet": "packet.json", "packetSha256": sha(output / "packet.json"),
                               "reviewer": "", "assessments": [], "resolutions": []}}
    for req in plan["requirements"]:
        evidence = [{"path": item["current"]["path"], "sha256": item["current"]["sha256"], "kind": "image", "view": item["definition"]["view"]}
                    for item in packet["items"] if req["id"] in item["definition"]["requirements"]]
        template["verdicts"].append({"id": req["id"], "status": "unverified", "reviewer": "", "notes": "", "evidence": evidence})
    for spec in specs:
        observations = [{"id": f["id"], "status": "unverified", "currentRegion": None, "referenceRegion": None, "difference": "", "repair": ""}
                        for f in prior_findings if f["comparison"] == spec["id"]]
        template["comparison"]["assessments"].append({"id": spec["id"], "status": "unverified", "observations": observations})
    template["comparison"]["resolutions"] = [{"id": f["id"], "status": "open", "reason": ""} for f in prior_findings]
    save(output / "review-template.json", template)
    payload = json.dumps({"items": display, "priorFindings": prior_findings, "requirements": plan["requirements"], "baselineChange": baseline_change}, allow_nan=False).replace("<", "\\u003c")
    html = Path(__file__).with_name("comparison-board.html").read_text(encoding="utf-8").replace("__PACKET_DATA__", payload)
    (output / "board.html").write_text(html, encoding="utf-8")
    (output / "review-request.md").write_text(
        "# Review the actual images\n\nOpen board.html in a browser or inspect its bundled source images directly. "
        "Read the protected focus and reference role for every comparison. Inspect reference, current, and previous images. "
        "For style references compare pixel treatment, materials, density and readability, not exact object positions. "
        "For layout/both compare camera and composition too. Locate each observation in both original images using "
        "[x,y,width,height] pixels. Name the actual agreement or difference and a concrete repair for every failure. "
        "Inspect the worst transition and strongest repeated motif when terrain is in scope. "
        "Reinspect all prior open findings with their same IDs; keep the complete scope open, including regressions. "
        "Use pass/fail/unverified honestly. Missing images or unobserved motion remain unverified. "
        "Static comparisons cannot approve motion, gameplay or performance; complete their separate evidence. "
        "Fill review-template.json and save as review.json. Do not change packet.json or its images. "
        "Do not infer an intended verdict from this request.\n\n"
        "Set comparison.reviewer to your identity. Each assessment needs observations in this format "
        "(illustrative schema, not a suggested finding):\n\n"
        '```json\n{"id":"stable-observation-id","status":"fail","currentRegion":[10,20,30,40],'
        '"referenceRegion":[12,22,30,40],"difference":"Describe what you actually see",'
        '"repair":"Describe a concrete repair for this failure"}\n```\n\n'
        "Use source-pixel rectangles inside each image. Pass observations describe the observed agreement; "
        "unverified observations explain what could not be inspected and may use null regions. "
        "Assessment status is fail if any observation fails, otherwise unverified if any is unverified, "
        "otherwise pass. The packet contains the protected requirement descriptions; assess those criteria, "
        "not merely the existence of image files. If baselineChange is present, inspect its stated art-check "
        "correction/additional views and retained previous packet; a new baseline does not close visual findings. "
        "Preserve prior observation IDs and fill every resolution with "
        "resolved/open/regressed plus a reason. When an added comparison supplies previously missing evidence, "
        "you may move that finding's observation to it and set the resolution's comparison field to its ID. "
        "The destination must share the protected view, requirement and target; explain the relocation and "
        "continue assessing the original comparison too. Complete the separate requirement verdicts too.\n", encoding="utf-8")
    return {"board": str(output / "board.html"), "packet": str(output / "packet.json"), "review": str(output / "review-template.json")}


def validate_acceptance(plan, root, baseline_path, candidate_path, review_path):
    review, packet_path, packet, findings = inspect_review(review_path)
    require(packet["baselineSha256"] == sha(baseline_path) and packet["candidateSha256"] == sha(candidate_path), "Visual comparison is stale or belongs to another candidate")
    specs, references = definitions(plan, root)
    require(packet.get("requirements") == plan["requirements"], "Protected review requirements changed or missing")
    require([i["definition"] for i in packet["items"]] == specs, "Protected comparison scope changed")
    for item in packet["items"]:
        reference = str(local(root, item["definition"]["reference"]))
        require(item["reference"]["sha256"] == references[reference], "Comparison reference does not match protected target")
        if item["definition"]["role"] in ("layout", "both"):
            require((item["reference"]["width"], item["reference"]["height"]) == (item["current"]["width"], item["current"]["height"]), "Layout image dimensions differ")
    require(not findings, "Visual differences remain failed or unverified")
    return len(specs)
