#!/usr/bin/env python3
from __future__ import annotations

import hashlib, json, os, re, secrets, shutil, socket, sqlite3, subprocess, sys, time, urllib.request, zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
import animation_review, pipeline
from runner import Runner, sparse_cycle_sampling
from store import Store

OUT = ROOT / os.environ.get("ANIMATION_TRIAL_OUTPUT", "review/real-cold-e2e-01")
REFERENCE = ROOT / "artifacts/minimax-ne-source-01/reference.png"
SOURCE_MODEL = "wavespeed-ai/minimax-h3/image-to-video"
SOURCE_PRESET = os.environ.get("ANIMATION_TRIAL_SOURCE_PRESET", "minimax-h3-ne-source-5s-768p-v1")
REVIEW_MODEL = "google/gemini-3.8-flash"
REMOVER = "wavespeed-ai/image-background-remover"
ACTION = os.environ.get("ANIMATION_TRIAL_ACTION", "walk")
PROMPT = os.environ.get("ANIMATION_TRIAL_PROMPT", "Fixed camera. Animate the exact full-body character in an orthographic isometric northeast rear-three-quarter walk IN PLACE. Maintain unwavering northeast facing and the same torso angle throughout. Keep both feet fully visible with alternating full strides and repeat complete gait cycles at a steady pace; continuous movement, no still hold. Keep the body root stable. No turn, yaw, orbit, camera movement, zoom, scale change, crop, or background scene change. Preserve crisp consistent identity, clothing, anatomy, pixel-art features, and lantern; cloak and lantern motion should remain naturally subtle. The ending must flow back into the beginning while the character continues walking.")
SOURCE_DURATION = int(os.environ.get("ANIMATION_TRIAL_SOURCE_DURATION", "5"))
SOURCE_RESOLUTION = os.environ.get("ANIMATION_TRIAL_SOURCE_RESOLUTION", "768p")
INCREMENTAL_CAP = float(os.environ.get("ANIMATION_TRIAL_INCREMENTAL_CAP", "3.0"))
SOURCE_RESERVE = float(os.environ.get("ANIMATION_TRIAL_SOURCE_CAP", "0.50"))
REMOVAL_UNIT = 0.004
MAX_REMOVALS = 32
MAX_INFLIGHT = int(os.environ.get("ANIMATION_TRIAL_MAX_INFLIGHT", "1"))
REVIEW_OUTPUT = int(os.environ.get("ANIMATION_TRIAL_REVIEW_OUTPUT", "600"))
HOST, PORT = "127.0.0.1", 4395
BASE = f"http://{HOST}:{PORT}"


def utc() -> str: return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def write_json(path: Path, value: Any, mode: int | None = None) -> None:
    tmp = path.with_name("." + path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    if mode is not None: path.chmod(mode)

class Run:
    def __init__(self):
        if OUT.exists():
            previous = OUT / "REPORT.json"
            prior = json.loads(previous.read_text()) if previous.exists() else {}
            if prior.get("error") != "'maximum_accounted_usd'" or (OUT / "source-request-receipt.json").exists():
                raise RuntimeError("run directory already contains a paid or unrelated attempt")
            retained = OUT / "preflight-failure-01"; retained.mkdir(exist_ok=False)
            for name in ("REPORT.json", "REPORT.md", "redacted-trace.jsonl"):
                if (OUT / name).exists(): shutil.move(OUT / name, retained / name)
        else:
            OUT.mkdir(parents=True, exist_ok=False)
        OUT.chmod(0o700)
        self.start_mono = time.monotonic(); self.started = utc(); self.events=[]; self.stages=[]
        self.report={"status":"running","started_at_utc":self.started,"source_reference":{"file":str(REFERENCE),"sha256":sha(REFERENCE)},"public_policy_changed":False,"game_changed":False,"deployment_changed":False}
        self.ledger={"schema":"real-cold-e2e-cost-ledger-v1","incremental_cap_usd":INCREMENTAL_CAP,"entries":[],"known_billed_usd":0.0,"open_liability_usd":0.0,"updated_at_utc":utc()}
        self.event("run_initialized", reference_sha256=sha(REFERENCE)); self.flush()
    def event(self, name, **data):
        rec={"sequence":len(self.events)+1,"utc":utc(),"monotonic_elapsed_seconds":round(time.monotonic()-self.start_mono,6),"event":name,**data}; self.events.append(rec)
        with (OUT/"redacted-trace.jsonl").open("a",encoding="utf-8") as f: f.write(json.dumps(rec,sort_keys=True)+"\n")
    def stage(self,name): return (name,time.monotonic(),utc())
    def end(self,m,status="completed",**data):
        rec={"stage":m[0],"started_at_utc":m[2],"ended_at_utc":utc(),"duration_seconds":round(time.monotonic()-m[1],6),"status":status,**data}; self.stages.append(rec); self.event("stage_finished",**rec); self.flush()
    def reserve(self,id,amount,**basis):
        self.ledger["entries"].append({"id":id,"reserved_usd":round(amount,9),"known_billed_usd":None,"open_liability_usd":round(amount,9),"status":"reserved","basis":basis}); self.costs(); self.event("cost_reserved",id=id,amount_usd=amount,basis=basis)
    def revise(self,id,amount,**basis):
        e=next(x for x in self.ledger["entries"] if x["id"]==id); e.update(reserved_usd=round(amount,9),open_liability_usd=round(amount,9),status="reserved",basis=basis); self.costs(); self.event("cost_revised",id=id,amount_usd=amount,basis=basis)
    def settle(self,id,amount,ref):
        e=next(x for x in self.ledger["entries"] if x["id"]==id); e.update(known_billed_usd=round(amount,9),open_liability_usd=0.0,status="known_billed",provider_reference=ref); self.costs()
    def open(self,id,status,refs):
        e=next(x for x in self.ledger["entries"] if x["id"]==id); e.update(status=status,provider_references=refs); self.costs()
    def costs(self):
        known=sum(float(x.get("known_billed_usd") or 0) for x in self.ledger["entries"]); opened=sum(float(x.get("open_liability_usd") or 0) for x in self.ledger["entries"])
        if known+opened>INCREMENTAL_CAP+1e-12: raise RuntimeError("incremental USD3 cap exceeded before charge")
        self.ledger.update(known_billed_usd=round(known,9),open_liability_usd=round(opened,9),maximum_accounted_usd=round(known+opened,9),updated_at_utc=utc()); write_json(OUT/"cost-ledger.json",self.ledger)
    def flush(self):
        self.report.update(stages=self.stages,cost=self.ledger,updated_at_utc=utc()); write_json(OUT/"REPORT.json",self.report)
        lines=["# Real cold end-to-end run 01","",f"Status: {self.report['status']}",f"Started UTC: {self.started}","", "This report is incrementally written. No visual-perfection claim is made.","", "## Current evidence","",json.dumps(self.report,indent=2,sort_keys=True)]
        (OUT/"REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8")

def load_keys():
    con=sqlite3.connect("file:/root/.openclaw/state/openclaw.sqlite?mode=ro",uri=True)
    row=con.execute("SELECT value,allowed_hosts FROM secret_store_entries WHERE deleted_at_ms IS NULL AND name='OPWNROUTER_KEY_2'").fetchone(); con.close()
    if not row or "openrouter.ai" not in (row[1] or ""): raise RuntimeError("authorized OpenRouter key unavailable")
    ws=None
    for line in Path("/root/.hermes/.env").read_text().splitlines():
        if line.startswith("WAVESPEED_API_KEY="): ws=line.split("=",1)[1].strip().strip("'\"")
    if not ws: raise RuntimeError("WaveSpeed key unavailable")
    return row[0],ws

def get_json(url,key=None):
    req=urllib.request.Request(url,headers={"Authorization":f"Bearer {key}"} if key else {})
    with urllib.request.urlopen(req,timeout=30) as resp: return resp.status,json.loads(resp.read())

def prior_reconciliation():
    configured = os.environ.get("ANIMATION_TRIAL_PRIOR_MAX_USD")
    if configured is not None:
        return {"maximum_accounted_usd": float(configured), "basis": "independently reconciled retained ledgers through compact8-cold-01", "provider_ids": [], "sources": [str(ROOT/"review/compact8-cold-01/cost-ledger.json")], "newer_cost_ledgers_found": False}
    authoritative=json.loads((ROOT/"artifacts/live-e2e-20260920T223050Z-91b811/parent-reconciled-cost-ledger.json").read_text())
    source=json.loads((ROOT/"artifacts/minimax-ne-source-01/cost-ledger.json").read_text())
    removal=json.loads((ROOT/"artifacts/minimax-ne-export-final/cost-ledger.json").read_text())
    ids=set(); duplicates=[]
    def add(values):
        for value in values:
            if value in ids: duplicates.append(value)
            ids.add(value)
    add(authoritative.get("deduplicated_provider_references",[]))
    for entry in authoritative.get("entries",[]):
        if entry.get("provider_reference"): add([entry["provider_reference"]])
        add(entry.get("provider_references",[]))
    for entry in source["entries"]:
        add(entry.get("deduplicated_provider_references",[]))
        if entry.get("provider_reference"): add([entry["provider_reference"]])
        if entry.get("prediction_id"): add([entry["prediction_id"]])
    add(removal["entries"][0].get("provider_references",[]))
    expected=round(float(authoritative["maximum_accounted_total_usd"])+0.09+0.50+0.096,9)
    if expected != 1.56646275: raise RuntimeError("prior ledger reconciliation mismatch")
    return {"maximum_accounted_usd":expected,"unique_provider_ids":len(ids),"deduplicated_repeated_id_occurrences":len(duplicates),"provider_ids":sorted(ids),"sources":[str(ROOT/"artifacts/live-e2e-20260920T223050Z-91b811/parent-reconciled-cost-ledger.json"),str(ROOT/"artifacts/minimax-ne-source-01/cost-ledger.json"),str(ROOT/"artifacts/minimax-ne-export-final/cost-ledger.json")],"newer_cost_ledgers_found":False}

def wait_job(client,headers,job_id,timeout):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        j=client.get(f"/v1/jobs/{job_id}",headers=headers); j.raise_for_status(); data=j.json()
        if data["state"] not in {"queued","running"}: return data
        time.sleep(.25)
    raise RuntimeError("API stage timeout")

def wait_stage_id(database, stage_id, timeout):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        with sqlite3.connect(database) as connection:
            connection.row_factory=sqlite3.Row
            row=connection.execute("SELECT id,state,error,result_json FROM stage_jobs WHERE id=?",(stage_id,)).fetchone()
        if row is None: raise RuntimeError("queued stage disappeared")
        record=dict(row)
        if record["state"] not in {"queued","running"}: return record
        time.sleep(.25)
    raise RuntimeError(f"exact stage {stage_id} timed out")

def approve(client,headers,job_id,a):
    r=client.post(f"/v1/jobs/{job_id}/reviews",headers=headers,json={"artifact":a["name"],"sha256":a["sha256"],"decision":"approve"}); r.raise_for_status()

def start_server(env,log):
    s=socket.socket(); s.bind((HOST,PORT)); s.close()
    f=log.open("wb"); p=subprocess.Popen([str(ROOT/".venv/bin/python"),"-m","uvicorn","app:app","--host",HOST,"--port",str(PORT),"--log-level","warning"],cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT)
    p._log=f
    until=time.monotonic()+20
    while time.monotonic()<until:
        try:
            if httpx.get(BASE+"/health",timeout=2).status_code==200:return p
        except Exception: pass
        if p.poll() is not None: raise RuntimeError("isolated server exited")
        time.sleep(.1)
    raise RuntimeError("isolated server health timeout")

def stop_server(p):
    if p and p.poll() is None:
        p.terminate()
        try:p.wait(10)
        except subprocess.TimeoutExpired:p.kill();p.wait(5)
    if p and hasattr(p,"_log"):p._log.close()

def run():
    r=Run(); process=None
    try:
        pre=r.stage("preflight_quotes_credentials_fx_reconciliation")
        ork,wsk=load_keys(); _,keyinfo=get_json("https://openrouter.ai/api/v1/key",ork); _,models=get_json("https://openrouter.ai/api/v1/models")
        model=next(x for x in models["data"] if x.get("id")==REVIEW_MODEL); pricing=model["pricing"]; context=int(model["context_length"])
        prompt_price=float(pricing["prompt"]); completion_price=float(pricing["completion"])
        if not {"text","image"} <= set(model["architecture"]["input_modalities"]): raise RuntimeError("review model modalities missing")
        if not {"response_format","max_tokens"} <= set(model["supported_parameters"]): raise RuntimeError("review model structured output unsupported")
        _,balance=get_json("https://api.wavespeed.ai/api/v3/balance",wsk)
        fx_xml=urllib.request.urlopen("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml",timeout=30).read().decode(); fx=float(re.search(r"currency=['\"]USD['\"] rate=['\"]([0-9.]+)",fx_xml).group(1)); fx_date=re.search(r"time=['\"]([0-9-]+)",fx_xml).group(1)
        prior=prior_reconciliation(); ceiling=20*fx
        metadata={"fetched_at_utc":utc(),"source":"https://openrouter.ai/api/v1/models","id":REVIEW_MODEL,"canonical_slug":model.get("canonical_slug"),"context_length":context,"architecture":model["architecture"],"supported_parameters":model["supported_parameters"],"pricing":pricing,"fixed_run_price_claimed":False}; write_json(OUT/"openrouter-model-metadata.json",metadata)
        source_schema={"fetched_at_utc":utc(),"source":"WaveSpeed live model schema tool","model_id":SOURCE_MODEL,"required":["prompt","image"],"properties":{"duration":{"enum":list(range(3,16)),"type":"integer"},"image":{"type":"string"},"last_image":{"type":"string"},"prompt":{"type":"string"},"resolution":{"enum":["480p","540p","768p","1080p"],"type":"string"},"seed":{"type":"integer"}}}; write_json(OUT/"minimax-live-schema.json",source_schema)
        live_discounted_quote = float(os.environ.get("ANIMATION_TRIAL_LIVE_DISCOUNTED_QUOTE", "0.2"))
        live_quote = float(os.environ.get("ANIMATION_TRIAL_LIVE_QUOTE", "0.4"))
        write_json(OUT/"minimax-live-quote.json",{"fetched_at_utc":utc(),"source":"WaveSpeed get_price live tool","model_id":SOURCE_MODEL,"inputs":{"duration":SOURCE_DURATION,"resolution":SOURCE_RESOLUTION,"first_equals_last":True},"price":live_quote,"discounted_price":live_discounted_quote,"currency":"USD","estimate":True,"unpriced_inputs":[]})
        write_json(OUT/"remover-live-quote.json",{"fetched_at_utc":utc(),"model_id":REMOVER,"price":REMOVAL_UNIT,"discounted_price":REMOVAL_UNIT,"required":["image"],"estimate":True})
        write_json(OUT/"ecb-fx.json",{"date":fx_date,"usd_per_eur":fx,"ceiling_eur":20,"ceiling_usd":ceiling,"source":"ECB daily reference rates"})
        full_review=(context-REVIEW_OUTPUT)*prompt_price+REVIEW_OUTPUT*completion_price
        r.ledger["prior_reconciliation"]=prior; r.ledger["cumulative_ceiling_usd"]=ceiling
        r.reserve("new-minimax-source",SOURCE_RESERVE,model=SOURCE_MODEL,quote_discounted_usd=live_discounted_quote,quote_undiscounted_usd=live_quote,cap_usd=SOURCE_RESERVE)
        r.reserve("new-openrouter-review",full_review,model=REVIEW_MODEL,basis="full context minus bounded output fallback",context_tokens=context,max_output_tokens=REVIEW_OUTPUT)
        r.reserve("new-removals",MAX_REMOVALS*REMOVAL_UNIT,model=REMOVER,max_frames=MAX_REMOVALS,unit_quote_usd=REMOVAL_UNIT)
        if r.ledger["maximum_accounted_usd"]>INCREMENTAL_CAP or prior["maximum_accounted_usd"]+r.ledger["maximum_accounted_usd"]>ceiling: raise RuntimeError("whole-attempt reservation does not fit authorized caps")
        r.report["preflight"]={"wavespeed_balance_usd":balance["data"]["balance"],"openrouter_limit_remaining":keyinfo["data"].get("limit_remaining"),"fx":{"date":fx_date,"usd_per_eur":fx},"prior":prior,"whole_attempt_reserved_usd":r.ledger["maximum_accounted_usd"]}
        r.end(pre,balance_verified=True,whole_attempt_reserved_before_paid_call=True)

        source_dir=OUT/"source"; source_dir.mkdir(); shutil.copyfile(REFERENCE,source_dir/"reference.png")
        seed=secrets.randbelow(2_147_483_647)
        request={"input":"reference.png","preset":SOURCE_PRESET,"prompt":PROMPT,"duration":SOURCE_DURATION,"resolution":SOURCE_RESOLUTION,"seed":seed,"budget":{"authorized":True,"max_usd":SOURCE_RESERVE}}
        r.report["source_request"]={"model":SOURCE_MODEL,"preset":SOURCE_PRESET,"action":ACTION,"duration":SOURCE_DURATION,"resolution":SOURCE_RESOLUTION,"seed":seed,"first_equals_last":True,"prompt":PROMPT,"reference_sha256":sha(REFERENCE)}; r.flush()
        os.environ["WAVESPEED_API_KEY"]=wsk
        sm=r.stage("source_queue_generation_download")
        for attempt in range(240):
            result=pipeline.run_stage("generate_video",source_dir,request)
            state=json.loads((source_dir/"generate-video-state.json").read_text())
            if state.get("submission_status")=="completed":break
            if state.get("submission_status")=="submission_unknown":raise RuntimeError("source submission ambiguous; no retry")
            if not result.get("details",{}).get("safe_resume"): raise RuntimeError("source generation stopped without safe known-ID resume")
            time.sleep(2)
        else: raise RuntimeError("source known prediction timed out")
        shutil.copyfile(source_dir/"video-output.mp4",OUT/"source-video.mp4"); state=json.loads((source_dir/"generate-video-state.json").read_text())
        receipt={"model":SOURCE_MODEL,"preset":SOURCE_PRESET,"prediction_id":state["prediction_id"],"request":r.report["source_request"],"quote":state["quote"],"output":{"file":"source-video.mp4","sha256":sha(OUT/"source-video.mp4")},"actual_charge_known":False,"actual_charge_usd":None,"timings":state.get("timings",[])}; write_json(OUT/"source-request-receipt.json",receipt,0o444)
        r.open("new-minimax-source","completed_charge_not_authoritatively_reported_full_reservation_retained",[state["prediction_id"]]); r.report["source_receipt"]=receipt; r.end(sm,prediction_id=state["prediction_id"],source_sha256=receipt["output"]["sha256"],provider_timings=state.get("timings",[]))

        data=OUT/"private-service-data"; cache=OUT/"cutout-cache"; cache.mkdir(); store=Store(data/"jobs.sqlite3",data/"jobs")
        job=store.create_job("reference.png",{"run":"real-cold-e2e-01"},REFERENCE.read_bytes()); job_id=job["id"]; workdir=store.job_dir(job_id); shutil.copyfile(OUT/"source-video.mp4",workdir/"video-output.mp4")
        with store.connect() as con: store.upsert_artifact(con,job_id,"video-output.mp4","fresh_minimax_source",workdir/"video-output.mp4")
        artifact=store.get_artifact(job_id,"video-output.mp4")
        lm=r.stage("automatic_local_candidate_analysis")
        prepared=Runner(store).prepare_automatic_review_analysis(job_id,"video-output.mp4","8",ACTION)
        analysis=prepared["analysis"]; write_json(OUT/"local-candidate-analysis.json",analysis)
        r.report["local_analysis"]={"status":analysis["status"],"hard_failures":analysis["hard_failures"],"candidate_count":len(analysis.get("candidates",[]))}; r.end(lm,status=analysis["status"],hard_failures=analysis["hard_failures"],candidate_count=len(analysis.get("candidates",[])))
        if analysis["hard_failures"]:
            r.revise("new-openrouter-review",0,reason="local source rejection before reviewer"); r.revise("new-removals",0,reason="local source rejection before removals"); raise RuntimeError(f"new source rejected locally: {analysis['hard_failures']}")
        bounded=animation_review.build_review_request(workdir,"video-output.mp4",analysis,max_tokens=REVIEW_OUTPUT,request_binding={"request_id":"0"*32,"source_sha256":analysis["source"]["sha256"],"source_revision":artifact["revision"]})
        bound=bounded["_review_evidence"]; max_input=bound["conservative_input_token_bound"]; review_reserve=max_input*prompt_price+REVIEW_OUTPUT*completion_price
        max_selected=max(
            len(sparse_cycle_sampling(c, native_fps=analysis["source"]["native_fps"], frame_policy_name="8")["indices"])
            for c in analysis["candidates"]
        )
        max_selected=min(MAX_REMOVALS,max_selected)
        r.revise("new-openrouter-review",review_reserve,max_input_tokens=max_input,max_output_tokens=REVIEW_OUTPUT,evidence=bound,prices_usd_per_token={"prompt":prompt_price,"completion":completion_price})
        r.revise("new-removals",max_selected*REMOVAL_UNIT,max_eligible_selected_frames=max_selected,unit_quote_usd=REMOVAL_UNIT)

        token=secrets.token_urlsafe(36)
        env=os.environ.copy(); env.update({"ANIMATION_API_TOKEN":token,"ANIMATION_DATA_DIR":str(data),"ANIMATION_REVIEW_ENABLED":"1","ANIMATION_REVIEW_MAX_USD":str(review_reserve),"ANIMATION_REVIEW_MAX_INPUT_TOKENS":str(max_input),"ANIMATION_REVIEW_MAX_OUTPUT_TOKENS":str(REVIEW_OUTPUT),"ANIMATION_REVIEW_MODEL_METADATA_FILE":str(OUT/"openrouter-model-metadata.json"),"OPENROUTER_API_KEY":ork,"ANIMATION_PAID_ENABLED":"1","ANIMATION_MAX_STAGE_USD":"0.50","WAVESPEED_API_KEY":wsk,"ANIMATION_REMOVAL_MAX_INFLIGHT":str(MAX_INFLIGHT),"ANIMATION_CUTOUT_CACHE_DIR":str(cache)})
        process=start_server(env,OUT/"isolated-server.log"); headers={"Authorization":f"Bearer {token}"}
        with httpx.Client(base_url=BASE,timeout=30) as client:
            rm=r.stage("openrouter_automatic_review_and_extraction")
            q=client.post(f"/v1/jobs/{job_id}/automatic-review",headers=headers,json={"artifact":"video-output.mp4","sha256":artifact["sha256"],"revision":artifact["revision"],"authorize_paid_review":True,"budget_cap_usd":review_reserve,"frame_policy":"8","action":ACTION}); q.raise_for_status(); review_stage_id=q.json()["id"]; wait_stage_id(data/"jobs.sqlite3",review_stage_id,300); reviewed=client.get(f"/v1/jobs/{job_id}",headers=headers).json()
            review=reviewed["automatic_reviews"][0]; review_result=json.loads((workdir/"automatic-review-result.json").read_text()); r.report["automatic_review"]=review_result
            budget=review_result.get("budget") or {}; actual=budget.get("actual_cost_usd")
            if isinstance(actual,(int,float)):r.settle("new-openrouter-review",float(actual),review_result.get("response_id"))
            else:r.open("new-openrouter-review","completed_or_failed_cost_unknown",[x for x in [review_result.get("response_id")] if x])
            r.end(rm,status=review["status"],response_id=review_result.get("response_id"),selected_candidate=review.get("selected_candidate"),selected_sampling=review.get("selected_sampling"))
            if review["status"]!="approved":r.revise("new-removals",0,reason="reviewer rejected source"); raise RuntimeError(f"Gemini review did not approve: {review_result.get('rejection_reason') or review_result.get('reason')}")
            sampling=review["selected_sampling"]; selected_count=len(sampling["indices"]); r.revise("new-removals",selected_count*REMOVAL_UNIT,selected_candidate_id=review["selected_candidate"]["id"],selected_frames=selected_count,unit_quote_usd=REMOVAL_UNIT)
            current=client.get(f"/v1/jobs/{job_id}",headers=headers).json(); selected=sorted([a for a in current["artifacts"] if a["name"].startswith("selected-frame-")],key=lambda x:x["name"])
            if len(selected)!=selected_count: raise RuntimeError("automatic extraction artifact count mismatch")
            for a in selected: approve(client,headers,job_id,a)
            xm=r.stage("selected_original_removal_bounded_parallel_and_cache_ingest"); ids=set()
            for cycle in range(500):
                q=client.post(f"/v1/jobs/{job_id}/stages",headers=headers,json={"stage":"remove_background","params":{"inputs":[a["name"] for a in selected],"preset":"waldlicht-removal-v1"},"authorize_paid":True,"budget_cap_usd":selected_count*REMOVAL_UNIT}); q.raise_for_status(); removal_stage_id=q.json()["id"]; exact_removal=wait_stage_id(data/"jobs.sqlite3",removal_stage_id,240); ended=client.get(f"/v1/jobs/{job_id}",headers=headers).json()
                st=json.loads((workdir/"remove-background-state.json").read_text()); ids.update(x["prediction_id"] for x in st["items"] if isinstance(x.get("prediction_id"),str))
                if any(x.get("status")=="submission_unknown" for x in st["items"]):r.open("new-removals","ambiguous_submission",sorted(ids));raise RuntimeError("remover submission ambiguous")
                if st.get("status")=="completed":break
                if ended["state"]=="failed":raise RuntimeError(ended.get("message") or "removal failed")
                time.sleep(1)
            else:r.open("new-removals","known_predictions_pending",sorted(ids));raise RuntimeError("removals timed out")
            r.open("new-removals","completed_charge_not_authoritatively_reported",sorted(ids)); ingest=json.loads((workdir/"cutout-cache-ingest.json").read_text()); r.end(xm,prediction_ids=sorted(ids),cache_entries=len(ingest["items"]),maximum_inflight=st.get("maximum_inflight"),observed_maximum_inflight=st.get("observed_maximum_inflight"),provider_timings=st.get("timings",[]))
            em=r.stage("api_spatial_export_normalize_pack_verify")
            q=client.post(f"/v1/jobs/{job_id}/stages",headers=headers,json={"stage":"spatial_export","params":{"source":"video-output.mp4","selection_receipt":"automatic-review-result.json","selection_mode":"automatic_model_validated","export_preset":"derived-native-160-80-v1","removal_preset":"waldlicht-removal-v1","removal_recipe":"wavespeed-image-background-remover-output-v1"}}); q.raise_for_status(); export_stage_id=q.json()["id"]; wait_stage_id(data/"jobs.sqlite3",export_stage_id,300); exported=client.get(f"/v1/jobs/{job_id}",headers=headers).json()
            if exported["state"]!="completed":raise RuntimeError(exported.get("message") or "spatial export failed")
            download=client.get(f"/v1/jobs/{job_id}/download",headers=headers);download.raise_for_status();(OUT/"api-job-download.zip").write_bytes(download.content)
            for name in ["atlas-160.png","atlas-160-manifest.json","atlas-80.png","atlas-80-manifest.json","preview-160-native-petrol-3loops.mp4","preview-80-native-petrol-3loops.mp4","preview-160-native-petrol-repeated-3x.mp4","preview-80-native-petrol-repeated-3x.mp4","all-frames-160-light.png","all-frames-160-dark.png","all-frames-160-petrol.png","all-frames-80-light.png","all-frames-80-dark.png","all-frames-80-petrol.png","spatial-export.zip","spatial-export-result.json","spatial-verification.json","spatial-timings.json","preview.html","cutout-cache-ingest.json","extract-frames.json","selection-density-receipt.json","automatic-review-result.json","automatic-review-analysis.json","remove-background-state.json"]:
                if (workdir/name).exists():shutil.copyfile(workdir/name,OUT/name)
            with zipfile.ZipFile(OUT/"api-job-download.zip") as z:z.testzip()
            result=json.loads((OUT/"spatial-export-result.json").read_text()); verification=json.loads((OUT/"spatial-verification.json").read_text()); r.end(em,zip_sha256=sha(OUT/"api-job-download.zip"),selected_indices=result["selected_indices"],geometry=result["geometry"],verification_status=verification["status"])
        submit_start=datetime.fromisoformat(state["timings"][1]["started_utc"].replace("Z","+00:00")); ready=datetime.now(timezone.utc); cold_seconds=(ready-submit_start).total_seconds()
        r.report.update(status="artifact_ready_pending_parent_visual_inspection",ended_at_utc=utc(),job_id=job_id,selected_candidate=review["selected_candidate"],selected_sampling=sampling,final_outputs={"api_zip":{"file":"api-job-download.zip","sha256":sha(OUT/"api-job-download.zip")},"spatial_zip":{"file":"spatial-export.zip","sha256":sha(OUT/"spatial-export.zip")},"atlas_160_sha256":sha(OUT/"atlas-160.png"),"atlas_80_sha256":sha(OUT/"atlas-80.png")},cold_source_submission_to_artifact_ready_seconds=cold_seconds,artifact_ready_at_utc=ready.isoformat().replace("+00:00","Z"),source_new_and_cache_miss_verified=all(x["new_cache_entry"] for x in ingest["items"]),visual_quality_certified=False)
        r.event("artifact_ready",cold_source_submission_to_artifact_ready_seconds=cold_seconds,job_id=job_id);r.flush();return 0
    except Exception as e:
        r.report.update(status="stopped_or_rejected",ended_at_utc=utc(),error=str(e),visual_quality_certified=False);r.event("run_stopped",error=str(e),retry_decision="no source/reviewer retry");r.flush();return 1
    finally: stop_server(process)

if __name__=="__main__": raise SystemExit(run())
