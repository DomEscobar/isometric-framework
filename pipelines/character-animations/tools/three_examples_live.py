#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, json, os, re, sqlite3, time, urllib.request, zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "review/three-examples-01"
BASE = "https://isoani.huecki.com/animation"
REFERENCE = ROOT / "artifacts/minimax-ne-source-01/reference.png"
TASK_CAP = 3.0
PRIOR_ACCOUNTED = 4.41887525
SOURCE_QUOTES = {("3", "480p"): 0.06, ("5", "768p"): 0.20}
REMOVAL_UNIT = 0.004
CASES = [
    {"id":"walk-ne-3s-480p-8f-80","action":"walk","loop":True,"duration":3,"resolution":"480p","frame_policy":"8","cell":80,
     "prompt":"Fixed camera. Animate the exact full-body character in an orthographic isometric northeast rear-three-quarter walk IN PLACE. Maintain unwavering northeast facing and the same torso angle throughout. Keep both feet fully visible with alternating full strides and a complete gait cycle. Keep the body root stable. No turn, yaw, orbit, camera movement, zoom, scale change, crop, or background scene change. Preserve crisp consistent identity, clothing, anatomy, pixel-art features, and lantern. The ending must flow into the beginning."},
    {"id":"punch-ne-3s-480p-8f-160","action":"punch","loop":False,"duration":3,"resolution":"480p","frame_policy":"8","cell":160,
     "prompt":"Fixed camera. Animate the exact full-body character performing one decisive northeast-facing punch IN PLACE: clear anticipation, fast extension to a readable impact pose, recovery, then settled finish. Maintain unwavering northeast rear-three-quarter facing and the same torso angle. Keep the complete figure, both feet, fist and lantern visible. Stable root. No turn, yaw, orbit, camera movement, zoom, scale change, crop, extra limbs, repeated punches, or background scene change. Preserve crisp consistent identity, clothing, anatomy and pixel-art features."},
    {"id":"walk-ne-5s-768p-12f-160","action":"walk","loop":True,"duration":5,"resolution":"768p","frame_policy":"12","cell":160,
     "prompt":"Fixed camera. Animate the exact full-body character in an orthographic isometric northeast rear-three-quarter walk IN PLACE. Maintain unwavering northeast facing and the same torso angle throughout. Keep both feet fully visible with alternating full strides and multiple complete steady gait cycles. Keep the body root stable. No turn, yaw, orbit, camera movement, zoom, scale change, crop, or background scene change. Preserve crisp consistent identity, clothing, anatomy, pixel-art features, and lantern. The ending must flow into the beginning."},
]

def utc(): return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def sha_bytes(data: bytes): return hashlib.sha256(data).hexdigest()
def sha(path: Path): return sha_bytes(path.read_bytes())
def write(path: Path, value: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_name("."+path.name+".tmp")
    tmp.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
    os.replace(tmp,path)
def load_env():
    values={}
    for raw in Path("/etc/animation-pipeline.env").read_text(encoding="utf-8").splitlines():
        s=raw.strip()
        if s and not s.startswith("#") and "=" in s:
            k,v=s.split("=",1); values[k]=v.strip().strip("'").strip('"')
    token=values.get("ANIMATION_API_TOKEN")
    if not token: raise RuntimeError("ANIMATION_API_TOKEN missing from service environment")
    return values,token

def public_get(client, path, headers):
    r=client.get(path,headers=headers); r.raise_for_status(); return r.json()
def poll_job(client, headers, job_id, expected_stage, timeout=1200):
    started=time.monotonic(); seen=[]
    while time.monotonic()-started<timeout:
        job=public_get(client,f"/v1/jobs/{job_id}",headers)
        seen.append({"elapsed":round(time.monotonic()-started,3),"state":job["state"],"latest_stage":job.get("latest_stage"),"updated_at":job.get("updated_at")})
        if job.get("latest_stage") != expected_stage:
            raise RuntimeError(f"stale/unexpected stage while waiting for {expected_stage}: {job.get('latest_stage')}")
        if job["state"] not in {"queued","running"}: return job,seen
        time.sleep(1)
    raise RuntimeError(f"timeout waiting for {expected_stage}")
def artifact(job,name):
    return next((x for x in job.get("artifacts",[]) if x["name"]==name),None)
def approve(client,headers,job_id,a):
    r=client.post(f"/v1/jobs/{job_id}/reviews",headers=headers,json={"artifact":a["name"],"sha256":a["sha256"],"decision":"approve"}); r.raise_for_status(); return r.json()
def reconcile_ledgers():
    paths=sorted(set(ROOT.glob("review/**/cost-ledger.json"))|set(ROOT.glob("artifacts/**/cost-ledger.json")))
    refs={}; no_ref=[]
    for p in paths:
        try:d=json.loads(p.read_text())
        except Exception:continue
        entries=d.get("entries") if isinstance(d,dict) else None
        if not isinstance(entries,list):continue
        for e in entries:
            if not isinstance(e,dict):continue
            ids=[]
            for k in ("provider_reference","prediction_id","response_id"):
                if isinstance(e.get(k),str):ids.append(e[k])
            for k in ("provider_references","deduplicated_provider_references"):
                if isinstance(e.get(k),list):ids += [x for x in e[k] if isinstance(x,str)]
            rec={"path":str(p.relative_to(ROOT)),"entry_id":e.get("id"),"known":float(e.get("known_billed_usd") or 0),"open":float(e.get("open_liability_usd") or 0)}
            if ids:
                share_open=rec["open"]/len(set(ids)); share_known=rec["known"]/len(set(ids))
                for ident in set(ids):
                    old=refs.get(ident,{"known":0.0,"open":0.0,"sources":[]})
                    old["known"]=max(old["known"],share_known);old["open"]=max(old["open"],share_open);old["sources"].append(rec["path"]);refs[ident]=old
            elif rec["known"] or rec["open"]: no_ref.append(rec)
    dedup=sum(x["known"]+x["open"] for x in refs.values())
    return {"scanned_ledgers":len(paths),"unique_provider_ids":len(refs),"provider_bound_deduplicated_usd":round(dedup,9),"unbound_entries":no_ref,"authoritative_latest_cumulative_usd":PRIOR_ACCOUNTED,"basis":"latest retained cumulative ledger plus programmatic provider-ID inventory; nested prior rollups excluded","paths":[str(p.relative_to(ROOT)) for p in paths]}
def preflight():
    OUT.mkdir(parents=True,exist_ok=True);OUT.chmod(0o700)
    env,token=load_env();headers={"Authorization":f"Bearer {token}"}
    with httpx.Client(base_url=BASE,timeout=30,follow_redirects=False) as c:
        health=c.get("/health");health.raise_for_status();caps=public_get(c,"/v1/capabilities",headers)
    if caps["paid_policy"]!={"enabled":True,"max_stage_usd":0.5}:raise RuntimeError(f"unexpected paid policy: {caps['paid_policy']}")
    reviewer=caps["automatic_review"]["reviewer"]
    if not reviewer.get("available") or float(reviewer.get("max_review_usd",0))!=0.05:raise RuntimeError(f"review policy unavailable/unexpected: {reviewer}")
    rec=reconcile_ledgers()
    fx_xml=urllib.request.urlopen("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml",timeout=30).read().decode()
    fx=float(re.search(r"currency=['\"]USD['\"] rate=['\"]([0-9.]+)",fx_xml).group(1)); fx_date=re.search(r"time=['\"]([0-9-]+)",fx_xml).group(1)
    worst_sources=sum(SOURCE_QUOTES[(str(x["duration"]),x["resolution"])] for x in CASES)
    worst_reviews=0.05*len(CASES); worst_removals=sum(int(x["frame_policy"])*REMOVAL_UNIT for x in CASES)
    reserved=round(worst_sources+worst_reviews+worst_removals,9)
    if reserved>TASK_CAP:raise RuntimeError("three-case worst-case exceeds USD3 task cap")
    if PRIOR_ACCOUNTED+reserved>20*fx:raise RuntimeError("existing development cap cannot cover reservations")
    ledger={"schema":"three-examples-shared-ledger-v1","task_cap_usd":TASK_CAP,"prior_reconciliation":rec,"development_ceiling":{"eur":20,"usd":20*fx,"fx_date":fx_date,"usd_per_eur":fx},"entries":[],"known_billed_usd":0.0,"open_liability_usd":reserved,"maximum_accounted_usd":reserved,"cumulative_maximum_accounted_usd":PRIOR_ACCOUNTED+reserved,"updated_at_utc":utc()}
    for x in CASES:
        ledger["entries"] += [
          {"id":x["id"]+":source","reserved_usd":SOURCE_QUOTES[(str(x["duration"]),x["resolution"])],"known_billed_usd":None,"open_liability_usd":SOURCE_QUOTES[(str(x["duration"]),x["resolution"])],"status":"reserved_not_sent"},
          {"id":x["id"]+":review","reserved_usd":0.05,"known_billed_usd":None,"open_liability_usd":0.05,"status":"reserved_not_sent"},
          {"id":x["id"]+":removal","reserved_usd":int(x["frame_policy"])*REMOVAL_UNIT,"known_billed_usd":None,"open_liability_usd":int(x["frame_policy"])*REMOVAL_UNIT,"status":"reserved_not_sent"}]
    write(OUT/"cost-ledger.json",ledger)
    results={"schema":"three-live-examples-v1","created_at_utc":utc(),"planned_count":3,"records":[{**x,"status":"planned","job_id":None,"stages":[]} for x in CASES]}
    write(OUT/"results.json",results)
    snap={"health":health.json(),"capabilities":caps,"reference":{"path":str(REFERENCE),"sha256":sha(REFERENCE)},"quotes":{"source_3s_480p_discounted_usd":0.06,"source_5s_768p_discounted_usd":0.20,"removal_unit_usd":0.004,"wavespeed_balance_usd":6.99,"fetched_via":"live WaveSpeed MCP immediately before preflight"},"facing_generation_tested":False,"reference_flow":"existing accepted NE reference uploaded separately into each fresh live API job","removal_max_inflight_configured":int(env.get("ANIMATION_REMOVAL_MAX_INFLIGHT","5")),"preflight_at_utc":utc()}
    write(OUT/"preflight.json",snap)
    print(json.dumps({"status":"preflight_complete","reserved_usd":reserved,"cumulative_maximum_usd":PRIOR_ACCOUNTED+reserved,"capabilities":{"paid":caps["paid_policy"],"reviewer":reviewer},"ledger_inventory":{"ledgers":rec["scanned_ledgers"],"ids":rec["unique_provider_ids"]}},indent=2))

def update_totals(ledger):
    ledger["known_billed_usd"]=round(sum(float(e.get("known_billed_usd") or 0) for e in ledger["entries"]),9)
    ledger["open_liability_usd"]=round(sum(float(e.get("open_liability_usd") or 0) for e in ledger["entries"]),9)
    ledger["maximum_accounted_usd"]=round(ledger["known_billed_usd"]+ledger["open_liability_usd"],9)
    ledger["cumulative_maximum_accounted_usd"]=round(PRIOR_ACCOUNTED+ledger["maximum_accounted_usd"],9);ledger["updated_at_utc"]=utc();write(OUT/"cost-ledger.json",ledger)
def entry(ledger,id):return next(x for x in ledger["entries"] if x["id"]==id)
def persisted_review_for_stage(stage_id):
    with sqlite3.connect(ROOT/"var/jobs.sqlite3") as connection:
        row=connection.execute("SELECT record_json FROM automatic_reviews WHERE stage_job_id=?",(stage_id,)).fetchone()
    if row is None:return None
    return {**json.loads(row[0]),"stage_job_id":stage_id}
def stage_event(rec,name,stage_id,start,started_mono,polls,**extra):rec["stages"].append({"name":name,"stage_id":stage_id,"started_at_utc":start,"ended_at_utc":utc(),"duration_seconds":round(time.monotonic()-started_mono,3),"polls":polls,**extra})
def run():
    preflight_path=OUT/"preflight.json"
    if not preflight_path.exists():preflight()
    results=json.loads((OUT/"results.json").read_text());ledger=json.loads((OUT/"cost-ledger.json").read_text())
    env,token=load_env();headers={"Authorization":f"Bearer {token}"}
    with httpx.Client(base_url=BASE,timeout=60,follow_redirects=False) as c:
      for i,case in enumerate(CASES):
        rec=results["records"][i]
        if rec["status"]=="terminal_failed_or_blocked" and rec.get("failure")=="stage_event() got multiple values for argument 'state'":
          rec.update(status="planned",failure=None,actual_stage_achieved=None,ended_at_utc=None)
          for suffix in ("review","removal"):
            e=entry(ledger,case["id"]+":"+suffix);e.update(open_liability_usd=e["reserved_usd"],status="reserved_not_sent")
          update_totals(ledger);write(OUT/"results.json",results)
        if rec["status"] not in {"planned"}:continue
        rec.update(status="running",started_at_utc=utc());write(OUT/"results.json",results)
        folder=OUT/case["id"];folder.mkdir(exist_ok=True)
        try:
          t=time.monotonic();start=utc()
          if rec.get("job_id"):
            job_id=rec["job_id"];job=public_get(c,f"/v1/jobs/{job_id}",headers)
            if job.get("latest_stage")!="inspect_reference" or job["state"] not in {"completed","needs_review"}:raise RuntimeError("free recovery job no longer at inspected reference state")
            polls=[{"elapsed":0.0,"state":job["state"],"latest_stage":job.get("latest_stage"),"updated_at":job.get("updated_at"),"reused_free_job":True}]
          else:
            r=c.post("/v1/jobs",headers=headers,files={"reference":("reference.png",REFERENCE.read_bytes(),"image/png")},data={"options":json.dumps({"auto_start":True})});r.raise_for_status();job=r.json();job_id=job["id"];rec["job_id"]=job_id
            job,polls=poll_job(c,headers,job_id,"inspect_reference",120)
          stage_event(rec,"inspect_reference",None,start,t,polls,state=job["state"])
          ref=artifact(job,"reference.png");approve(c,headers,job_id,ref);rec["reference_approval"]={"sha256":ref["sha256"],"revision":ref["revision"],"basis":"pre-existing accepted NE reference exact upload hash"}
          source_e=entry(ledger,case["id"]+":source");source_e["status"]="submission_started";update_totals(ledger)
          payload={"stage":"generate_video","params":{"input":"reference.png","preset":"minimax-h3-action-3s-480p-v1","prompt":case["prompt"],"duration":case["duration"],"resolution":case["resolution"],"seed":-1},"authorize_paid":True,"budget_cap_usd":SOURCE_QUOTES[(str(case["duration"]),case["resolution"])]}
          t=time.monotonic();start=utc();source_stage_ids=[];source_polls=[]
          for resume_attempt in range(120):
            q=c.post(f"/v1/jobs/{job_id}/stages",headers=headers,json=payload);q.raise_for_status();sid=q.json()["id"];source_stage_ids.append(sid);source_e.update(stage_ids=source_stage_ids,status="submitted_open_liability");update_totals(ledger)
            job,polls=poll_job(c,headers,job_id,"generate_video",120);source_polls.extend(polls)
            if job["state"]=="needs_review":break
            state_art=artifact(job,"generate-video-state.json")
            if job["state"]!="needs_attention" or state_art is None:raise RuntimeError("source stage terminal state: "+job["state"]+" "+str(job.get("message")))
            raw=c.get(f"/v1/jobs/{job_id}/artifacts/{state_art['name']}",headers=headers);raw.raise_for_status();known=json.loads(raw.content)
            if not isinstance(known.get("prediction_id"),str) or known.get("submission_status")=="submission_unknown":raise RuntimeError("source submission ambiguous or missing prediction ID; no resubmit")
            time.sleep(2)
          else: raise RuntimeError("known source prediction did not complete within bounded polling")
          stage_event(rec,"generate_video",source_stage_ids,start,t,source_polls,state=job["state"],resume_stage_count=len(source_stage_ids))
          video=artifact(job,"video-output.mp4");approve(c,headers,job_id,video);rec["source"]={"artifact":video,"provider_prediction_id":None}
          # Download provider state receipt when registered, without exposing hosted URLs.
          if artifact(job,"generate-video-state.json"):
            raw=c.get(f"/v1/jobs/{job_id}/artifacts/generate-video-state.json",headers=headers);raw.raise_for_status();state=json.loads(raw.content);pid=state.get("prediction_id");rec["source"]["provider_prediction_id"]=pid;source_e.update(provider_references=[pid] if pid else [],status="completed_charge_not_authoritatively_reported")
          update_totals(ledger)
          review_e=entry(ledger,case["id"]+":review");review_e["status"]="submission_started";update_totals(ledger)
          t=time.monotonic();start=utc();q=c.post(f"/v1/jobs/{job_id}/automatic-review",headers=headers,json={"artifact":"video-output.mp4","sha256":video["sha256"],"revision":video["revision"],"frame_policy":case["frame_policy"],"action":case["action"],"authorize_paid_review":True,"budget_cap_usd":0.05});q.raise_for_status();rsid=q.json()["id"];review_e.update(stage_id=rsid,status="submitted_open_liability");update_totals(ledger)
          job,polls=poll_job(c,headers,job_id,"automatic_review",900);stage_event(rec,"automatic_review_and_extraction",rsid,start,t,polls,state=job["state"])
          ar=next((x for x in job.get("automatic_reviews",[]) if x.get("stage_job_id")==rsid),None)
          if ar is None:raise RuntimeError("exact automatic review record missing")
          rec["automatic_review"]=ar
          rr=artifact(job,"automatic-review-result.json")
          if rr:
            raw=c.get(f"/v1/jobs/{job_id}/artifacts/{rr['name']}",headers=headers);raw.raise_for_status();review_result=json.loads(raw.content);cost=(review_result.get("budget") or {}).get("actual_cost_usd");rid=review_result.get("response_id");review_e.update(known_billed_usd=cost,open_liability_usd=0.0 if cost is not None else review_e["reserved_usd"],provider_reference=rid,status="known_billed" if cost is not None else "response_received_cost_unknown");write(folder/"automatic-review-result.json",review_result)
          update_totals(ledger)
          if ar["status"]!="approved":
            rem=entry(ledger,case["id"]+":removal");rem.update(open_liability_usd=0.0,status="not_sent_after_review_outcome");update_totals(ledger);raise RuntimeError("automatic reviewer did not approve: "+str(ar.get("reason") or ar.get("rejection_reason") or ar["status"]))
          selected=sorted([x for x in job["artifacts"] if x["name"].startswith("selected-frame-")],key=lambda x:x["name"])
          expected=int(case["frame_policy"])
          if len(selected)!=expected:raise RuntimeError(f"selected frame count {len(selected)} != {expected}")
          for a in selected:approve(c,headers,job_id,a)
          rem=entry(ledger,case["id"]+":removal");rem["reserved_usd"]=len(selected)*REMOVAL_UNIT;rem["open_liability_usd"]=rem["reserved_usd"];rem["status"]="submission_started";update_totals(ledger)
          removal_payload={"stage":"remove_background","params":{"inputs":[x["name"] for x in selected],"preset":"waldlicht-removal-v1"},"authorize_paid":True,"budget_cap_usd":len(selected)*REMOVAL_UNIT}
          t=time.monotonic();start=utc();removal_stage_ids=[];removal_polls=[]
          for resume_attempt in range(120):
            q=c.post(f"/v1/jobs/{job_id}/stages",headers=headers,json=removal_payload);q.raise_for_status();msid=q.json()["id"];removal_stage_ids.append(msid);rem.update(stage_ids=removal_stage_ids,status="submitted_open_liability");update_totals(ledger)
            job,polls=poll_job(c,headers,job_id,"remove_background",180);removal_polls.extend(polls)
            if job["state"]=="needs_review":break
            state_art=artifact(job,"remove-background-state.json")
            if job["state"]!="needs_attention" or state_art is None:raise RuntimeError("removal terminal state: "+job["state"]+" "+str(job.get("message")))
            raw=c.get(f"/v1/jobs/{job_id}/artifacts/{state_art['name']}",headers=headers);raw.raise_for_status();known=json.loads(raw.content)
            items=known.get("items",[])
            if any(x.get("status")=="submission_unknown" for x in items if isinstance(x,dict)):raise RuntimeError("removal submission ambiguous; no resubmit")
            known_ids=[x.get("prediction_id") for x in items if isinstance(x,dict) and isinstance(x.get("prediction_id"),str)]
            if not known_ids:raise RuntimeError("removal needs attention without known prediction IDs; no resubmit")
            time.sleep(1)
          else: raise RuntimeError("known removal predictions did not complete within bounded polling")
          stage_event(rec,"remove_background",removal_stage_ids,start,t,removal_polls,state=job["state"],resume_stage_count=len(removal_stage_ids))
          state_art=artifact(job,"remove-background-state.json");raw=c.get(f"/v1/jobs/{job_id}/artifacts/{state_art['name']}",headers=headers);raw.raise_for_status();rem_state=json.loads(raw.content);pids=sorted({x.get("prediction_id") for x in rem_state.get("items",[]) if isinstance(x.get("prediction_id"),str)});rem.update(provider_references=pids,status="completed_charge_not_authoritatively_reported");rec["removal"]={"prediction_ids":pids,"configured_maximum_inflight":rem_state.get("maximum_inflight"),"observed_maximum_inflight":rem_state.get("observed_maximum_inflight")};write(folder/"remove-background-state.json",rem_state);update_totals(ledger)
          cutouts=sorted([x for x in job["artifacts"] if x["name"].startswith("cutout-frame-")],key=lambda x:x["name"])
          for a in cutouts:approve(c,headers,job_id,a)
          export_preset="derived-native-80-v1" if case["cell"]==80 else "derived-native-160-v1"
          t=time.monotonic();start=utc();q=c.post(f"/v1/jobs/{job_id}/stages",headers=headers,json={"stage":"spatial_export","params":{"source":"video-output.mp4","selection_receipt":"automatic-review-result.json","selection_mode":"automatic_model_validated","export_preset":export_preset,"removal_preset":"waldlicht-removal-v1","removal_recipe":"wavespeed-image-background-remover-output-v1"}});q.raise_for_status();esid=q.json()["id"]
          job,polls=poll_job(c,headers,job_id,"spatial_export",900);stage_event(rec,"spatial_export",esid,start,t,polls,state=job["state"])
          if job["state"]!="completed":raise RuntimeError("spatial export terminal state: "+job["state"]+" "+str(job.get("message")))
          dl=c.get(f"/v1/jobs/{job_id}/download",headers=headers);dl.raise_for_status();zpath=folder/"api-job-download.zip";zpath.write_bytes(dl.content)
          with zipfile.ZipFile(zpath) as z:
            bad=z.testzip();names=z.namelist()
          if bad:raise RuntimeError("ZIP CRC failure: "+bad)
          wanted=[x["name"] for x in job["artifacts"] if x["name"] in {f"atlas-{case['cell']}.png",f"atlas-{case['cell']}-manifest.json",f"all-frames-{case['cell']}-light.png",f"all-frames-{case['cell']}-dark.png",f"all-frames-{case['cell']}-petrol.png","spatial-export.zip","spatial-verification.json","spatial-export-result.json","preview.html"} or (x["name"].startswith(f"preview-{case['cell']}-") and x["name"].endswith(".mp4"))]
          outputs={}
          for name in wanted:
            rr=c.get(f"/v1/jobs/{job_id}/artifacts/{name}",headers=headers);rr.raise_for_status();(folder/name).write_bytes(rr.content);outputs[name]={"sha256":sha_bytes(rr.content),"bytes":len(rr.content)}
          manifest=json.loads((folder/f"atlas-{case['cell']}-manifest.json").read_text())
          rec.update(status="completed",ended_at_utc=utc(),actual_stage_achieved="actual authenticated HTTP ZIP download",output={"zip":{"path":str(zpath),"sha256":sha(zpath),"crc_ok":True,"entry_count":len(names)},"artifacts":outputs,"manifest":{"frame_count":len(manifest["frames"]),"action":manifest.get("action"),"loop":manifest.get("loop"),"cell":case["cell"],"frame_durations_seconds":manifest.get("frame_durations_seconds")}})
        except Exception as exc:
          rec.update(status="terminal_failed_or_blocked",ended_at_utc=utc(),failure=str(exc),actual_stage_achieved=rec["stages"][-1]["name"] if rec["stages"] else "job_creation")
          # Release only stages definitely never submitted.
          for suffix in ("review","removal"):
            e=entry(ledger,case["id"]+":"+suffix)
            if e["status"]=="reserved_not_sent":e.update(open_liability_usd=0.0,status="not_sent_after_failure")
          update_totals(ledger)
        write(OUT/"results.json",results)
    print(json.dumps({"records":[{"id":x["id"],"status":x["status"],"job_id":x.get("job_id"),"achieved":x.get("actual_stage_achieved"),"failure":x.get("failure")} for x in results["records"]],"ledger":json.loads((OUT/"cost-ledger.json").read_text())},indent=2))

def resume_after_review_lookup_fix():
    """Continue the three existing paid runs without repeating source or review calls."""
    results=json.loads((OUT/"results.json").read_text());ledger=json.loads((OUT/"cost-ledger.json").read_text())
    env,token=load_env();headers={"Authorization":f"Bearer {token}"}
    with httpx.Client(base_url=BASE,timeout=60,follow_redirects=False) as c:
      for i,case in enumerate(CASES):
        rec=results["records"][i]
        if rec.get("failure") not in {
            "exact automatic review record missing",
            "exact review request binding still missing",
        }:continue
        rec.update(status="running",failure=None,ended_at_utc=None);write(OUT/"results.json",results)
        folder=OUT/case["id"];job_id=rec["job_id"]
        try:
          job=public_get(c,f"/v1/jobs/{job_id}",headers)
          if job.get("latest_stage")!="automatic_review":raise RuntimeError("recovery job moved beyond exact automatic review")
          review_e=entry(ledger,case["id"]+":review");rsid=review_e.get("stage_id")
          persisted=persisted_review_for_stage(rsid)
          if persisted is None:raise RuntimeError("exact persisted stage-bound automatic review record missing")
          ar=next((x for x in job.get("automatic_reviews",[]) if x.get("id")==persisted.get("id")),None)
          if ar is None:raise RuntimeError("HTTP API omitted the exact persisted automatic review record")
          ar={**ar,"stage_job_id":rsid}
          rec["automatic_review"]=ar
          rr=artifact(job,"automatic-review-result.json")
          if rr is None:raise RuntimeError("automatic review result artifact missing")
          raw=c.get(f"/v1/jobs/{job_id}/artifacts/{rr['name']}",headers=headers);raw.raise_for_status();review_result=json.loads(raw.content);write(folder/"automatic-review-result.json",review_result)
          binding=review_result.get("server_request_binding") or {}
          if binding.get("request_id") != ar.get("id"):
            raise RuntimeError("legacy review request ID is not bound to the exact persisted review record")
          if binding.get("source_sha256") != ar.get("source_sha256") or binding.get("source_revision") != ar.get("source_revision"):
            raise RuntimeError("review request source binding does not match the exact persisted review record")
          cost=(review_result.get("budget") or {}).get("actual_cost_usd");rid=review_result.get("response_id")
          review_e.update(known_billed_usd=cost,open_liability_usd=0.0 if cost is not None else review_e["reserved_usd"],provider_reference=rid,status="known_billed" if cost is not None else "response_received_cost_unknown");update_totals(ledger)
          rem=entry(ledger,case["id"]+":removal")
          if ar["status"]!="approved":
            rem.update(open_liability_usd=0.0,status="not_sent_after_review_outcome");update_totals(ledger)
            rec.update(status="terminal_failed_or_blocked",ended_at_utc=utc(),failure="automatic reviewer did not approve: "+str(ar.get("rejection_reason") or ar.get("reason") or ar["status"]),actual_stage_achieved="automatic_review_and_extraction")
            write(OUT/"results.json",results);continue
          selected=sorted([x for x in job["artifacts"] if x["name"].startswith("selected-frame-")],key=lambda x:x["name"])
          expected=int(case["frame_policy"])
          if len(selected)!=expected:raise RuntimeError(f"selected frame count {len(selected)} != {expected}")
          for a in selected:approve(c,headers,job_id,a)
          rem.update(reserved_usd=len(selected)*REMOVAL_UNIT,open_liability_usd=len(selected)*REMOVAL_UNIT,status="submission_started");update_totals(ledger)
          removal_payload={"stage":"remove_background","params":{"inputs":[x["name"] for x in selected],"preset":"waldlicht-removal-v1"},"authorize_paid":True,"budget_cap_usd":len(selected)*REMOVAL_UNIT}
          t=time.monotonic();start=utc();stage_ids=[];all_polls=[]
          for resume_attempt in range(120):
            q=c.post(f"/v1/jobs/{job_id}/stages",headers=headers,json=removal_payload);q.raise_for_status();sid=q.json()["id"];stage_ids.append(sid);rem.update(stage_ids=stage_ids,status="submitted_open_liability");update_totals(ledger)
            job,polls=poll_job(c,headers,job_id,"remove_background",180);all_polls.extend(polls)
            if job["state"]=="needs_review":break
            state_art=artifact(job,"remove-background-state.json")
            if job["state"]!="needs_attention" or state_art is None:raise RuntimeError("removal terminal state: "+job["state"]+" "+str(job.get("message")))
            raw=c.get(f"/v1/jobs/{job_id}/artifacts/{state_art['name']}",headers=headers);raw.raise_for_status();known=json.loads(raw.content);items=known.get("items",[])
            if any(x.get("status")=="submission_unknown" for x in items if isinstance(x,dict)):raise RuntimeError("removal submission ambiguous; no resubmit")
            if not any(isinstance(x.get("prediction_id"),str) for x in items if isinstance(x,dict)):raise RuntimeError("removal needs attention without known prediction IDs; no resubmit")
            time.sleep(1)
          else:raise RuntimeError("known removal predictions did not complete within bounded polling")
          stage_event(rec,"remove_background",stage_ids,start,t,all_polls,state=job["state"],resume_stage_count=len(stage_ids))
          state_art=artifact(job,"remove-background-state.json");raw=c.get(f"/v1/jobs/{job_id}/artifacts/{state_art['name']}",headers=headers);raw.raise_for_status();rem_state=json.loads(raw.content);write(folder/"remove-background-state.json",rem_state)
          pids=sorted({x.get("prediction_id") for x in rem_state.get("items",[]) if isinstance(x.get("prediction_id"),str)});rem.update(provider_references=pids,status="completed_charge_not_authoritatively_reported");update_totals(ledger)
          rec["removal"]={"prediction_ids":pids,"configured_maximum_inflight":rem_state.get("maximum_inflight"),"observed_maximum_inflight":rem_state.get("observed_maximum_inflight")}
          cutouts=sorted([x for x in job["artifacts"] if x["name"].startswith("cutout-frame-")],key=lambda x:x["name"])
          if len(cutouts)!=expected or len(pids)!=expected:raise RuntimeError("cold removal count/prediction-ID count mismatch")
          for a in cutouts:approve(c,headers,job_id,a)
          export_preset="derived-native-80-v1" if case["cell"]==80 else "derived-native-160-v1"
          t=time.monotonic();start=utc();q=c.post(f"/v1/jobs/{job_id}/stages",headers=headers,json={"stage":"spatial_export","params":{"source":"video-output.mp4","selection_receipt":"automatic-review-result.json","selection_mode":"automatic_model_validated","export_preset":export_preset,"removal_preset":"waldlicht-removal-v1","removal_recipe":"wavespeed-image-background-remover-output-v1"}});q.raise_for_status();esid=q.json()["id"]
          job,polls=poll_job(c,headers,job_id,"spatial_export",900);stage_event(rec,"spatial_export",esid,start,t,polls,state=job["state"])
          if job["state"]!="completed":raise RuntimeError("spatial export terminal state: "+job["state"]+" "+str(job.get("message")))
          dl=c.get(f"/v1/jobs/{job_id}/download",headers=headers);dl.raise_for_status();zpath=folder/"api-job-download.zip";zpath.write_bytes(dl.content)
          with zipfile.ZipFile(zpath) as z:bad=z.testzip();names=z.namelist()
          if bad:raise RuntimeError("ZIP CRC failure: "+bad)
          wanted=[x["name"] for x in job["artifacts"] if x["name"] in {f"atlas-{case['cell']}.png",f"atlas-{case['cell']}-manifest.json",f"all-frames-{case['cell']}-light.png",f"all-frames-{case['cell']}-dark.png",f"all-frames-{case['cell']}-petrol.png","spatial-export.zip","spatial-verification.json","spatial-export-result.json","preview.html"} or (x["name"].startswith(f"preview-{case['cell']}-") and x["name"].endswith(".mp4"))]
          outputs={}
          for name in wanted:
            item=c.get(f"/v1/jobs/{job_id}/artifacts/{name}",headers=headers);item.raise_for_status();(folder/name).write_bytes(item.content);outputs[name]={"sha256":sha_bytes(item.content),"bytes":len(item.content)}
          manifest=json.loads((folder/f"atlas-{case['cell']}-manifest.json").read_text())
          rec.update(status="completed",ended_at_utc=utc(),actual_stage_achieved="actual authenticated HTTP ZIP download",output={"zip":{"path":str(zpath),"sha256":sha(zpath),"crc_ok":True,"entry_count":len(names)},"artifacts":outputs,"manifest":{"frame_count":len(manifest["frames"]),"action":manifest.get("action"),"loop":manifest.get("loop"),"cell":case["cell"],"frame_durations_seconds":manifest.get("frame_durations_seconds")}})
        except Exception as exc:
          rec.update(status="terminal_failed_or_blocked",ended_at_utc=utc(),failure=str(exc),actual_stage_achieved=rec["stages"][-1]["name"] if rec["stages"] else "automatic_review_and_extraction")
        write(OUT/"results.json",results)
    print(json.dumps([{"id":x["id"],"status":x["status"],"failure":x.get("failure"),"job_id":x.get("job_id")} for x in results["records"]],indent=2))

def finish_after_cache_fix():
    """Re-ingest already completed removals and finish the two approved API jobs."""
    results=json.loads((OUT/"results.json").read_text());ledger=json.loads((OUT/"cost-ledger.json").read_text())
    env,token=load_env();headers={"Authorization":f"Bearer {token}"}
    with httpx.Client(base_url=BASE,timeout=60,follow_redirects=False) as c:
      for i,case in enumerate(CASES):
        rec=results["records"][i]
        if rec.get("failure")!="spatial export terminal state: failed server cutout cache is not configured":continue
        rec.update(status="running",failure=None,ended_at_utc=None);write(OUT/"results.json",results)
        folder=OUT/case["id"];job_id=rec["job_id"]
        try:
          job=public_get(c,f"/v1/jobs/{job_id}",headers)
          selected=sorted([x for x in job["artifacts"] if x["name"].startswith("selected-frame-")],key=lambda x:x["name"])
          expected=int(case["frame_policy"])
          if len(selected)!=expected:raise RuntimeError(f"selected frame count {len(selected)} != {expected}")
          rem=entry(ledger,case["id"]+":removal");old_ids=set(rem.get("provider_references") or [])
          if len(old_ids)!=expected:raise RuntimeError("existing completed remover prediction IDs are incomplete")
          t=time.monotonic();start=utc()
          payload={"stage":"remove_background","params":{"inputs":[x["name"] for x in selected],"preset":"waldlicht-removal-v1"},"authorize_paid":True,"budget_cap_usd":len(selected)*REMOVAL_UNIT}
          q=c.post(f"/v1/jobs/{job_id}/stages",headers=headers,json=payload);q.raise_for_status();sid=q.json()["id"]
          job,polls=poll_job(c,headers,job_id,"remove_background",180)
          stage_event(rec,"reingest_completed_removals_after_cache_fix",sid,start,t,polls,state=job["state"])
          if job["state"]!="needs_review":raise RuntimeError("completed removal re-ingest failed: "+job["state"]+" "+str(job.get("message")))
          state_art=artifact(job,"remove-background-state.json");raw=c.get(f"/v1/jobs/{job_id}/artifacts/{state_art['name']}",headers=headers);raw.raise_for_status();rem_state=json.loads(raw.content)
          current_ids={x.get("prediction_id") for x in rem_state.get("items",[]) if isinstance(x.get("prediction_id"),str)}
          if current_ids!=old_ids:raise RuntimeError("removal re-ingest changed exact provider prediction IDs")
          ingest=artifact(job,"cutout-cache-ingest.json")
          if ingest is None:raise RuntimeError("server did not publish cutout cache ingest receipt")
          for a in [x for x in job["artifacts"] if x["name"].startswith("cutout-frame-")]:approve(c,headers,job_id,a)
          export_preset="derived-native-80-v1" if case["cell"]==80 else "derived-native-160-v1"
          t=time.monotonic();start=utc();q=c.post(f"/v1/jobs/{job_id}/stages",headers=headers,json={"stage":"spatial_export","params":{"source":"video-output.mp4","selection_receipt":"automatic-review-result.json","selection_mode":"automatic_model_validated","export_preset":export_preset,"removal_preset":"waldlicht-removal-v1","removal_recipe":"wavespeed-image-background-remover-output-v1"}});q.raise_for_status();esid=q.json()["id"]
          job,polls=poll_job(c,headers,job_id,"spatial_export",900);stage_event(rec,"spatial_export_after_cache_fix",esid,start,t,polls,state=job["state"])
          if job["state"]!="completed":raise RuntimeError("spatial export terminal state after cache fix: "+job["state"]+" "+str(job.get("message")))
          dl=c.get(f"/v1/jobs/{job_id}/download",headers=headers);dl.raise_for_status();zpath=folder/"api-job-download.zip";zpath.write_bytes(dl.content)
          with zipfile.ZipFile(zpath) as z:bad=z.testzip();names=z.namelist()
          if bad:raise RuntimeError("ZIP CRC failure: "+bad)
          wanted=[x["name"] for x in job["artifacts"] if x["name"] in {f"atlas-{case['cell']}.png",f"atlas-{case['cell']}-manifest.json",f"all-frames-{case['cell']}-light.png",f"all-frames-{case['cell']}-dark.png",f"all-frames-{case['cell']}-petrol.png","spatial-export.zip","spatial-verification.json","spatial-export-result.json","preview.html","cutout-cache-ingest.json"} or (x["name"].startswith(f"preview-{case['cell']}-") and x["name"].endswith(".mp4"))]
          outputs={}
          for name in wanted:
            item=c.get(f"/v1/jobs/{job_id}/artifacts/{name}",headers=headers);item.raise_for_status();(folder/name).write_bytes(item.content);outputs[name]={"sha256":sha_bytes(item.content),"bytes":len(item.content)}
          manifest=json.loads((folder/f"atlas-{case['cell']}-manifest.json").read_text())
          rec.update(status="completed",ended_at_utc=utc(),failure=None,actual_stage_achieved="actual authenticated HTTP ZIP download after free cache integration repair",output={"zip":{"path":str(zpath),"sha256":sha(zpath),"crc_ok":True,"entry_count":len(names)},"artifacts":outputs,"manifest":{"frame_count":len(manifest["frames"]),"action":manifest.get("action"),"loop":manifest.get("loop"),"cell":case["cell"],"frame_durations_seconds":manifest.get("frame_durations_seconds")}})
        except Exception as exc:
          rec.update(status="terminal_failed_or_blocked",ended_at_utc=utc(),failure=str(exc),actual_stage_achieved=rec["stages"][-1]["name"] if rec["stages"] else "remove_background")
        write(OUT/"results.json",results)
    print(json.dumps([{"id":x["id"],"status":x["status"],"failure":x.get("failure"),"job_id":x.get("job_id")} for x in results["records"]],indent=2))

def report():
    results=json.loads((OUT/"results.json").read_text());ledger=json.loads((OUT/"cost-ledger.json").read_text())
    terminal=sum(x["status"] in {"completed","terminal_failed_or_blocked"} for x in results["records"])
    if len(results["records"])!=3 or terminal!=3:raise RuntimeError(f"expected exactly 3 terminal records, got {len(results['records'])}/{terminal}")
    rows=[]
    for x in results["records"]:
      out=x.get("output",{});man=out.get("manifest",{});rows.append({"case":x["id"],"job_id":x.get("job_id"),"status":x["status"],"provider_source_id":(x.get("source") or {}).get("provider_prediction_id"),"stage":x.get("actual_stage_achieved"),"source_seconds":x["duration"],"frame_count":man.get("frame_count"),"cell":x["cell"],"action":x["action"],"loop":x["loop"],"zip_path":(out.get("zip") or {}).get("path"),"zip_sha256":(out.get("zip") or {}).get("sha256"),"failure":x.get("failure")})
    summary={"exact_record_count":len(rows),"terminal_record_count":terminal,"new_video_submission_count":sum(bool((x.get("source") or {}).get("provider_prediction_id")) for x in results["records"]),"facing_generation_tested":False,"implementation_changed":True,"public_config_changed":False,"visual_quality_certified":False,"cost":ledger,"cases":rows}
    write(OUT/"REPORT.json",summary)
    lines=["# Three fresh live Isoani API examples","",f"Generated: {utc()}","","Facing generation tested: no. The same previously accepted NE reference was uploaded to each fresh public API job and approved by exact hash.","","| Case | Job | Outcome | Reached | Frames | Cell | Action / loop | Source provider ID | ZIP SHA-256 |","|---|---|---|---|---:|---:|---|---|---|"]
    for r in rows:lines.append(f"| {r['case']} | {r['job_id'] or '-'} | {r['status']} | {r['stage']} | {r['frame_count'] or '-'} | {r['cell']} | {r['action']} / {str(r['loop']).lower()} | {r['provider_source_id'] or '-'} | {r['zip_sha256'] or '-'} |")
    lines += ["","Costs: quotes/reservations and authoritative reviewer charges are separate in cost-ledger.json. WaveSpeed stages retain open liabilities because provider receipts do not report authoritative charges.","","No provider output URLs, bearer tokens, or credentials are included. Public job artifacts remain authenticated. visual_quality_certified=false pending parent inspection of every delivered frame and playback.","","Machine-readable details: results.json and REPORT.json."]
    (OUT/"REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2))

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("mode",choices=["preflight","run","resume","finish","report"]);a=p.parse_args()
    {"preflight":preflight,"run":run,"resume":resume_after_review_lookup_fix,"finish":finish_after_cache_fix,"report":report}[a.mode]()
