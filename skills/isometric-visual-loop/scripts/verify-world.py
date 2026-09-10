"""Authoring gates: inspect decoded packed art; freeze, snapshot and accept a world.

Pillow is required only for inspect/accept with art checks. No runtime dependency.
Evidence receipts establish coverage and freshness, not truthfulness or beauty.
"""
import argparse
import base64
import hashlib
import io
import json
import math
from pathlib import Path
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def local(base, name):
    require(isinstance(name, str) and name and ":" not in name and "\\" not in name,
            "Use local relative forward-slash paths, not URLs or drive paths")
    require(not Path(name).is_absolute(), "Paths must be relative")
    return (base / name).resolve()


def components(mask, width, minimum):
    remaining = {i for i, visible in enumerate(mask) if visible}
    sizes = []
    while remaining:
        seed = remaining.pop()
        pending, size = [seed], 0
        while pending:
            pixel = pending.pop()
            size += 1
            x, y = pixel % width, pixel // width
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    nx, ny = x + dx, y + dy
                    neighbor = ny * width + nx
                    if 0 <= nx < width and ny >= 0 and neighbor in remaining:
                        remaining.remove(neighbor)
                        pending.append(neighbor)
        if size >= minimum:
            sizes.append(size)
    return sorted(sizes, reverse=True)


def inspect(spec_path):
    from PIL import Image
    spec_path = Path(spec_path).resolve()
    spec = read(spec_path)
    require(spec.get("version") == 1, "Art spec version must be 1")
    manifest_path = local(spec_path.parent, spec["manifest"])
    data = read(manifest_path)
    assets = data.get("assets", data)
    groups = spec.get("groups")
    require(isinstance(groups, list) and groups, "Art checks need nonempty groups")
    textures, animations = assets["textures"], assets.get("animations", {})
    inputs = {str(spec_path): digest(spec_path), str(manifest_path): digest(manifest_path)}
    images, decoded, findings, previews, clips = {}, {}, [], {}, {}
    group_ids = set()
    for group in groups:
        gid = group["id"]
        require(isinstance(gid, str) and gid and gid not in group_ids, "Unique nonempty group IDs required")
        group_ids.add(gid)
        kind = group["kind"]
        require(kind in ("cutout", "diamond-overlay"), "Unknown art check kind")
        threshold = group.get("alphaThreshold", 16)
        require(integer(threshold, 1, 255), "alphaThreshold must be 1..255")
        selected = list(group.get("textures", []))
        group_clips = group.get("clips", [])
        minimum = group.get("minDistinctFrames", 1)
        require(integer(minimum, 1, 256), "minDistinctFrames must be 1..256")
        for clip_id in group_clips:
            require(clip_id in animations, f"Missing required clip: {clip_id}")
            clip = animations[clip_id]
            require(isinstance(clip.get("frames"), list) and 1 <= len(clip["frames"]) <= 256,
                    f"Invalid frame list: {clip_id}")
            fps = clip.get("fps", 8)
            require(type(fps) in (int, float) and math.isfinite(fps) and 0 < fps <= 120,
                    f"Invalid fps: {clip_id}")
            require(type(clip.get("loop", True)) is bool, f"Invalid loop flag: {clip_id}")
            clips[clip_id] = {**clip, "fps": fps, "loop": clip.get("loop", True)}
            selected.extend(clip["frames"])
        require(selected and len(selected) <= 4096, f"Group {gid} needs bounded texture/clip coverage")
        pixel_hashes = {}
        for tid in dict.fromkeys(selected):
            require(tid in textures, f"Missing required texture: {tid}")
            texture = textures[tid]
            image_id = texture["image"]
            if image_id not in decoded:
                source = local(manifest_path.parent, assets["images"][image_id]["url"])
                require(source.stat().st_size <= 64 * 1024 * 1024, "PNG exceeds 64 MiB")
                raw = source.read_bytes()
                with Image.open(io.BytesIO(raw)) as original:
                    require(original.format == "PNG" and original.width * original.height <= 32_000_000,
                            "Expected PNG no larger than 32 million pixels")
                    require(getattr(original, "n_frames", 1) == 1, "Use a static PNG atlas")
                    decoded[image_id] = original.convert("RGBA")
                inputs[str(source)] = hashlib.sha256(raw).hexdigest()
                images[image_id] = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
            atlas = decoded[image_id]
            frame = texture.get("frame", {"x": 0, "y": 0, "width": atlas.width, "height": atlas.height})
            x, y, w, h = (frame[k] for k in ("x", "y", "width", "height"))
            require(integer(x, 0, atlas.width) and integer(y, 0, atlas.height)
                    and integer(w, 1, 1024) and integer(h, 1, 1024)
                    and x + w <= atlas.width and y + h <= atlas.height, f"Invalid frame rectangle: {tid}")
            rgba = atlas.crop((x, y, x + w, y + h))
            alpha = rgba.getchannel("A").tobytes()
            mask = [a >= threshold for a in alpha]
            pixels = [(i % w, i // w) for i, visible in enumerate(mask) if visible]
            errors = []
            if not pixels:
                errors.append("empty frame")
            elif kind == "cutout":
                margin = group.get("margin", 1)
                maximum = group.get("maxComponents", 1)
                component_min = group.get("minComponentPixels", 2)
                require(integer(margin, 1, min(w, h) // 2), "Cutout margin must leave transparent padding")
                require(integer(maximum, 1, 1024) and integer(component_min, 1, w*h), "Invalid component limits")
                left, top = min(p[0] for p in pixels), min(p[1] for p in pixels)
                right, bottom = max(p[0] for p in pixels), max(p[1] for p in pixels)
                if left < margin or top < margin or right >= w-margin or bottom >= h-margin:
                    errors.append("visible pixels touch protected crop margin; inspect for truncation")
                sizes = components(mask, w, component_min)
                if len(sizes) > maximum:
                    errors.append(f"{len(sizes)} significant alpha components exceed {maximum}; inspect neighbor fragments")
                bounds = group.get("bounds")
                if bounds is not None:
                    require(isinstance(bounds, list) and len(bounds) == 4
                            and all(integer(n, 1, 1024) for n in bounds)
                            and bounds[0] <= bounds[2] and bounds[1] <= bounds[3], "bounds: minWidth,minHeight,maxWidth,maxHeight")
                    if not (bounds[0] <= right-left+1 <= bounds[2] and bounds[1] <= bottom-top+1 <= bounds[3]):
                        errors.append("visible bounds outside declared size range")
            elif any(abs((px+.5-w/2)/(w/2)) + abs((py+.5-h/2)/(h/2)) > 1.000001 for px, py in pixels):
                errors.append("opaque pixels outside tile diamond; entity sprites are not terrain-clipped")
            pixel_hashes[tid] = hashlib.sha256(rgba.tobytes()).hexdigest()
            anchor = texture.get("anchor", {"x": .5, "y": 1})
            require(isinstance(anchor, dict) and all(type(anchor.get(axis)) in (int, float)
                    and math.isfinite(anchor[axis]) for axis in ("x", "y")), f"Invalid anchor: {tid}")
            previews[tid] = {"image": image_id, "frame": frame, "anchor": anchor}
            findings.append({"group": gid, "texture": tid, "errors": errors})
        for clip_id in group_clips:
            count = len({pixel_hashes[tid] for tid in animations[clip_id]["frames"]})
            if count < minimum:
                findings.append({"group": gid, "clip": clip_id, "errors": [f"{count} distinct decoded frames; requires {minimum}"]})
    return {"version": 1, "passed": not any(f["errors"] for f in findings), "inputs": inputs,
            "findings": findings, "textures": previews, "clips": clips, "images": images}


def preview(report, target):
    # Embed original files once; CSS/canvas only presents the exact manifest crops.
    payload = json.dumps(report).replace("<", "\\u003c")
    document = """<!doctype html><meta charset="utf-8"><title>Packed art inspection</title>
<style>body{font:15px system-ui;background:#e8ebdf;color:#172b22;margin:24px}button,input{margin:8px}section{display:flex;flex-wrap:wrap;gap:12px}article{padding:12px;background:#fff;max-width:500px}canvas{image-rendering:pixelated;background:repeating-conic-gradient(#ddd 0 25%,#fff 0 50%) 0/16px 16px}.bad{color:#a00}.status{font-weight:bold}p{max-width:1000px}</style>
<h1>Packed art inspection</h1><p id="status" class="status"></p>
<p>Structural checks do not approve anatomy, facing, contacts or animation quality. Inspect every used clip and the real game. Red cross = declared anchor; blue outline = frame.</p>
<label>Shared zoom <input id="zoom" type="range" min="1" max="6" value="3"></label>
<button id="play">Pause clips</button><button id="replay">Replay clips</button><button id="background">Dark background</button><section id="frames"></section>
<script>const data=PAYLOAD;const loaded={};const views=[];let playing=true,dark=false,t=0,last=performance.now();
document.querySelector('#status').textContent=data.passed?'STRUCTURAL PASS - visual review still required':'STRUCTURAL FAIL - repair before acceptance';
document.querySelector('#status').classList.toggle('bad',!data.passed);
function add(label,ids,fps=0,loop=true){const article=document.createElement('article'),title=document.createElement('h3'),canvas=document.createElement('canvas'),notes=document.createElement('p');title.textContent=label+(fps?' ('+fps+' fps, '+(loop?'loop':'once')+')':'');notes.textContent=data.findings.filter(f=>ids.includes(f.texture)||f.clip===label).flatMap(f=>f.errors).join('; ');notes.className='bad';article.append(title,canvas,notes);document.querySelector('#frames').append(article);views.push({canvas,ids,fps,loop});}
for(const id of Object.keys(data.textures))add(id,[id]);for(const [id,c] of Object.entries(data.clips))add(id,c.frames,c.fps,c.loop);
Promise.all(Object.entries(data.images).map(([id,url])=>new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>{loaded[id]=im;resolve()};im.onerror=reject;im.src=url}))).then(()=>{document.body.dataset.decoded='true';requestAnimationFrame(draw)}).catch(()=>{document.querySelector('#status').textContent='IMAGE DECODE FAILED'});
function draw(now){if(playing)t+=(now-last)/1000;last=now;const zoom=Number(document.querySelector('#zoom').value);for(const v of views){const index=Math.floor(t*v.fps),tex=data.textures[v.ids[v.loop?index%v.ids.length:Math.min(index,v.ids.length-1)]],f=tex.frame,c=v.canvas;c.width=f.width;c.height=f.height;c.style.width=f.width*zoom+'px';c.style.height=f.height*zoom+'px';c.style.background=dark?'#17232d':'';const ctx=c.getContext('2d');ctx.drawImage(loaded[tex.image],f.x,f.y,f.width,f.height,0,0,f.width,f.height);ctx.strokeStyle='#3584e4';ctx.lineWidth=.5;ctx.strokeRect(.25,.25,f.width-.5,f.height-.5);ctx.strokeStyle='#f44';const x=tex.anchor.x*f.width,y=tex.anchor.y*f.height;ctx.beginPath();ctx.moveTo(x-3,y);ctx.lineTo(x+3,y);ctx.moveTo(x,y-3);ctx.lineTo(x,y+3);ctx.stroke();}requestAnimationFrame(draw)}
document.querySelector('#play').onclick=e=>{playing=!playing;e.target.textContent=playing?'Pause clips':'Play clips'};document.querySelector('#background').onclick=e=>{dark=!dark;e.target.textContent=dark?'Checker background':'Dark background'};
document.querySelector('#replay').onclick=()=>{t=0;last=performance.now()};
</script>""".replace("PAYLOAD", payload)
    with Path(target).open("x", encoding="utf-8") as stream:
        stream.write(document)


def plan_state(plan_path):
    plan_path = Path(plan_path).resolve()
    plan = read(plan_path)
    require(plan.get("version") == 1, "Plan version must be 1")
    root = local(plan_path.parent, plan["root"])
    require(plan.get("reviewMode") in ("independent", "self"), "Declare independent or self review")
    requirements = plan.get("requirements")
    require(isinstance(requirements, list) and requirements, "Plan needs requirements")
    ids = set()
    for req in requirements:
        require(isinstance(req.get("id"), str) and req["id"] and req["id"] not in ids, "Unique requirement IDs required")
        ids.add(req["id"])
        require(isinstance(req.get("description"), str) and req["description"].strip(), "Requirement description required")
        require(req.get("domain") in ("visual", "motion", "gameplay", "performance"), "Invalid requirement domain")
        require(isinstance(req.get("views"), list) and req["views"] and all(isinstance(v, str) and v for v in req["views"]), "Requirement views required")
    require(isinstance(plan.get("inputRoots"), list) and plan["inputRoots"], "Explicit source inputRoots required")
    require(isinstance(plan.get("artChecks"), list), "Declare artChecks (empty only for work without packed art)")
    return plan_path, plan, root


def freeze(plan_path, output):
    plan_path, plan, root = plan_state(plan_path)
    specs = {str(local(root, p)): digest(local(root, p)) for p in plan["artChecks"]}
    write_new(output, {"version": 1, "plan": str(plan_path), "planSha256": digest(plan_path), "artSpecs": specs})


def protected(baseline_path):
    baseline = read(baseline_path)
    plan_path, plan, root = plan_state(baseline["plan"])
    require(digest(plan_path) == baseline["planSha256"], "Protected plan changed; do not silently narrow requirements")
    for file, sha in baseline["artSpecs"].items():
        require(digest(file) == sha, f"Protected art thresholds/coverage changed: {file}")
    return baseline, plan, root


def source_hashes(plan, root):
    result = {}
    for name in plan["inputRoots"]:
        source = local(root, name)
        require(source.exists() and source.is_relative_to(root), "Input roots must exist inside project root")
        for file in sorted(source.rglob("*") if source.is_dir() else [source]):
            require(not file.is_symlink(), "Use ordinary source files, not symlinked input trees")
            if file.is_file():
                result[str(file.resolve())] = digest(file)
    require(result, "No source inputs found")
    return result


def snapshot(baseline_path, output):
    baseline, plan, root = protected(baseline_path)
    target = Path(output).resolve()
    require(all(not target.is_relative_to(local(root, p)) for p in plan["inputRoots"]), "Evidence outputs must be outside inputRoots")
    write_new(output, {"version": 1, "baselineSha256": digest(baseline_path), "inputs": source_hashes(plan, root)})


def accept(baseline_path, candidate_path, review_path):
    baseline, plan, root = protected(baseline_path)
    candidate, review = read(candidate_path), read(review_path)
    require(candidate["baselineSha256"] == digest(baseline_path), "Candidate belongs to a different baseline")
    require(candidate["inputs"] == source_hashes(plan, root), "Candidate is stale: source files added, removed or changed")
    require(review.get("candidateSha256") == digest(candidate_path), "Review belongs to a different candidate")
    require(review.get("reviewMode") == plan["reviewMode"], "Review mode does not match protected plan")
    for spec in baseline["artSpecs"]:
        report = inspect(spec)
        require(report["passed"], f"Packed art failed: {spec}; run inspect for findings")
        require(all(candidate["inputs"].get(file) == sha for file, sha in report["inputs"].items()),
                "Art spec, manifest and all inspected images must be inside inputRoots")
    verdicts = review.get("verdicts")
    require(isinstance(verdicts, list), "Review verdicts required")
    by_id = {v["id"]: v for v in verdicts}
    require(len(by_id) == len(verdicts) and set(by_id) == {r["id"] for r in plan["requirements"]}, "Review must cover exactly every protected requirement")
    extensions = {"image": {".png", ".jpg", ".jpeg", ".webp"}, "motion": {".webm", ".mp4", ".gif"}, "measurement": {".json", ".txt"}}
    for req in plan["requirements"]:
        verdict = by_id[req["id"]]
        require(verdict.get("status") == "pass", f"Requirement not accepted: {req['id']}")
        require(all(isinstance(verdict.get(k), str) and verdict[k].strip() for k in ("reviewer", "notes")), "Reviewer identity and observations required")
        evidence = verdict.get("evidence")
        require(isinstance(evidence, list) and evidence, "Evidence required")
        covered = set()
        for item in evidence:
            file = local(Path(review_path).resolve().parent, item["path"])
            kind = item["kind"]
            require(kind in extensions and file.suffix.lower() in extensions[kind], "Evidence kind/extension mismatch")
            require(file.stat().st_size > 0 and digest(file) == item["sha256"], "Missing, empty or changed evidence")
            permitted = {"visual": {"image", "motion"}, "motion": {"motion"}, "gameplay": {"image", "motion", "measurement"}, "performance": {"measurement"}}[req["domain"]]
            if kind in permitted:
                covered.add(item["view"])
        require(set(req["views"]) <= covered, f"Missing {req['domain']} evidence/views: {req['id']}")
    # Detect mutations occurring during inspection rather than accepting the old snapshot.
    require(candidate["inputs"] == source_hashes(plan, root), "Inputs changed during acceptance")
    return {"passed": True, "reviewMode": review["reviewMode"], "requirements": len(by_id),
            "limit": "Coverage and freshness verified; reviewer judgments are not authenticated or machine-proven."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("inspect"); p.add_argument("spec"); p.add_argument("--out", required=True)
    p = sub.add_parser("freeze"); p.add_argument("plan"); p.add_argument("output")
    p = sub.add_parser("snapshot"); p.add_argument("baseline"); p.add_argument("output")
    p = sub.add_parser("accept"); p.add_argument("baseline"); p.add_argument("candidate"); p.add_argument("review")
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            report = inspect(args.spec)
            output = Path(args.out)
            output.mkdir(parents=True, exist_ok=False)
            preview(report, output / "preview.html")
            write_new(output / "report.json", {k: v for k, v in report.items() if k != "images"})
            print(json.dumps({"passed": report["passed"], "preview": str(output / "preview.html"), "findings": [f for f in report["findings"] if f["errors"]]}, indent=2))
            return 0 if report["passed"] else 1
        if args.command == "freeze": freeze(args.plan, args.output)
        elif args.command == "snapshot": snapshot(args.baseline, args.output)
        else: print(json.dumps(accept(args.baseline, args.candidate, args.review), indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError, ImportError) as error:
        print(f"verify-world: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
