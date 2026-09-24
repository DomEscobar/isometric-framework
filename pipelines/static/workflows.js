/* All provider operations go through the local server; no credentials in the browser. */
window.styleReference=null;
let generationStatus=null, currentQuote=null, quoteEpoch=0;
window.styleSpec=null;window.currentEvaluation=null;let styleDraftDirty=false,reviewEpoch=0,reviewerEnabled=false;
async function api(url,body){const r=await fetch(url,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const value=await r.json();if(!r.ok)throw Error(typeof value.detail==='string'?value.detail:JSON.stringify(value.detail));return value;}
function generationControls(){
 const reasons=[...(generationStatus?.reasons||['Providerstatus unbekannt'])];
 if(!window.workbench)reasons.push('Zuerst Layout erzeugen.');
 if(!window.styleReference&&!window.styleSpec)reasons.push('Stilreferenz mit expliziter Rolle fehlt.');
 if(styleDraftDirty)reasons.push('Stilentwurf zuerst als unveränderliche Version speichern.');
 $('generationReason').textContent=reasons.length?reasons.join(' · '):'Budget konfiguriert. Erst Quote prüfen, dann gesondert bestätigen.';
 $('quoteGeneration').disabled=!(generationStatus?.authenticated&&window.workbench&&(window.styleReference||window.styleSpec)&&!styleDraftDirty);
 $('confirmGeneration').disabled=!(generationStatus?.enabled&&currentQuote&&window.workbench?.revision===currentQuote.binding.layout_revision&&currentQuote.expires_at>Date.now()/1000);
 $('confirmGeneration').title=reasons.join(' · ')||'Frische Quote erforderlich';
}
async function refreshGeneration(){generationStatus=await api('/api/generation/status');document.querySelector('.badge').textContent=`Projektlimit ${generationStatus.total_budget_usd} USD · reserviert ${generationStatus.reserved_usd} USD (inkl. Reviews)`;generationControls();}
function invalidateQuote(){quoteEpoch++;currentQuote=null;$('generationReport').textContent='';invalidateEvaluation();generationControls();}
function resetCandidate(){window.candidate=null;window.candidateImage=null;invalidateEvaluation();$('candidateDownload').classList.add('hidden');$('candidateStatus').textContent='Kein Kandidat für diese Revision. Ungeprüfte Kandidaten niemals automatisch freigeben.';$('comparison').classList.add('hidden');$('compareSource').removeAttribute('src');$('compareGuide').removeAttribute('src');}
function downloadLink(){if(!window.candidate)return;$('candidateDownload').href=exportUrl('diagnostic');}
async function selectCandidate(record){
 if(record.layout_revision!==window.workbench?.revision)throw Error('Veraltete Bindung: Kandidat gehört zu anderer Layoutrevision.');
 const active=window.workbench.revision;
 resetCandidate();
 $('terrainReport').textContent=JSON.stringify(record,null,2);
 const review=await api(`/api/terrain/${record.id}/review`);
 $('candidateStatus').textContent=`${record.status} · Technik ${review.technical_verdict||'Metadatenprüfung'} · Semantik ${review.semantic_verdict} · Visuell ${review.visual_verdict} · KEINE Produktionsfreigabe`;
 $('candidateId').value=record.id;
 $('compareSource').src=`/api/terrain/${record.id}/source.png`;
 $('compareGuide').src=`/api/layouts/${record.layout_revision}/artifacts/clean-guide.png`;
 await Promise.all([$('compareSource').decode(),$('compareGuide').decode()]);
 if(window.workbench.revision!==active)throw Error('Revision während Laden geändert.');
 window.candidate=record;
 if(record.status==='rejected'){$('candidateStatus').textContent+=' · Vorschau/Export gesperrt: Maße oder Rahmen falsch.';return;}
 const im=new Image();im.src=`/api/terrain/${record.id}/preview.png`;await im.decode();
 if(window.workbench.revision!==active)return;
 window.candidateImage=im;
 downloadLink();$('candidateDownload').classList.remove('hidden');
 $('view').value='candidate';await showView();
}
$('finalDensity').onchange=()=>{invalidateEvaluation();downloadLink();};
$('loadCandidate').onclick=async()=>{try{await selectCandidate(await api('/api/terrain/'+encodeURIComponent($('candidateId').value)));}catch(e){$('candidateStatus').textContent=e.message;}};
$('form').addEventListener('input',e=>{if(e.target.id!=='example')$('example').value='custom';invalidateQuote();});
$('example').addEventListener('change',invalidateQuote);
$('terrainPrompt').oninput=()=>{if(window.styleSpec){const spec=JSON.parse($('styleSpecEditor').value);spec.prompt=$('terrainPrompt').value;$('styleSpecEditor').value=JSON.stringify(spec,null,2);window.styleSpec=null;styleDraftDirty=true;}invalidateQuote();};
$('styleFile').onchange=()=>{window.styleReference=null;invalidateQuote();};
$('uploadStyle').onclick=async()=>{try{const f=$('styleFile').files[0];if(!f||f.size>8000000)throw Error('PNG auswählen (max. 8 MB).');const encoded=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=reject;r.readAsDataURL(f);});window.styleReference=await api('/api/styles',{png_base64:encoded,role:$('styleRole').value});const check=await api('/api/styles/'+window.styleReference.id);if(check.id!==window.styleReference.id)throw Error('Referenzprüfung fehlgeschlagen');$('styleStatus').textContent=`Gespeichert: ${check.id} · Rolle: ${check.role} · unreviewed`;invalidateQuote();}catch(e){$('styleStatus').textContent=e.message;}};
$('quoteGeneration').onclick=async()=>{const epoch=++quoteEpoch;currentQuote=null;$('quoteGeneration').disabled=true;$('confirmGeneration').disabled=true;$('generationReport').textContent='Kostenlose Live-Schema-/Preisabfrage …';try{const q=await api('/api/generation/quote',{revision:window.workbench.revision,...(window.styleSpec?{style_spec_id:window.styleSpec.id}:{style_id:window.styleReference.id,prompt:$('terrainPrompt').value})});if(epoch!==quoteEpoch)return;currentQuote=await api('/api/generation/quotes/'+q.id);$('generationReport').textContent=JSON.stringify({id:q.id,model:q.model,quote:q.quote,reserve_microusd:q.reserve_microusd,roles:q.roles,binding:q.binding,max_submissions:q.max_submissions,expires_at:q.expires_at},null,2);await refreshGeneration();}catch(e){$('generationReport').textContent=e.message+' (metadata unavailable)';}finally{generationControls();}};
$('confirmGeneration').onclick=async()=>{try{if(!currentQuote||!generationStatus?.enabled)throw Error('Budget/Quote nicht freigegeben.');const q=currentQuote;if(!confirm(`Einmaliger bezahlter Aufruf: Reservierung ${q.reserve_microusd/1000000} USD (Schätzung). ${q.roles.length} Bilder (Guide und deklarierte Referenzen) werden an WaveSpeed übertragen. Fortfahren?`))return;$('confirmGeneration').disabled=true;const j=await api('/api/generation/confirm',{quote_id:q.id,revision:window.workbench.revision,...(window.styleSpec?{style_spec_id:window.styleSpec.id}:{})});$('jobId').value=j.id;$('generationReport').textContent=JSON.stringify(await api('/api/generation/jobs/'+j.id),null,2);currentQuote=null;await refreshGeneration();}catch(e){$('generationReport').textContent=e.message+' Keine automatische Wiederholung.';}};
$('resumeJob').onclick=async()=>{try{const id=$('jobId').value;const j=await api('/api/generation/jobs/'+encodeURIComponent(id)+'/resume',{});const readback=await api('/api/generation/jobs/'+encodeURIComponent(id));$('generationReport').textContent=JSON.stringify(readback,null,2);if(j.candidate_id)await selectCandidate(await api('/api/terrain/'+j.candidate_id));await refreshGeneration();}catch(e){$('generationReport').textContent=e.message;}};
refreshGeneration().catch(e=>{$('generationReason').textContent=e.message;});
function invalidateEvaluation(){reviewEpoch++;window.currentEvaluation=null;$('strictReviewStatus').textContent='unreviewed — Bindung/Review ungültig nach Änderung. Geometrie bleibt unverändert.';$('paidReview').disabled=true;downloadLink();}
function exportUrl(mode){const p=new URLSearchParams({revision:window.workbench.revision,density:$('finalDensity').value,mode});if(window.styleSpec)p.set('style_spec_id',window.styleSpec.id);if(window.currentEvaluation)p.set('evaluation_id',window.currentEvaluation.id);return `/api/terrain/${window.candidate.id}/download?${p}`;}
async function refreshPresets(){const list=await api('/api/style-presets');$('stylePreset').replaceChildren(new Option('Preset wählen',''),...list.map(p=>new Option(p.name,p.name)));window.stylePresets=list;}
function activateSpec(spec){window.styleSpec=spec;styleDraftDirty=false;$('styleSpecEditor').value=JSON.stringify(spec.spec,null,2);$('styleSpecEditor').scrollTop=0;$('terrainPrompt').value=spec.spec.prompt;$('styleSpecStatus').textContent=`Unveränderliche Version ${spec.id}`;invalidateQuote();}
$('styleSpecEditor').oninput=()=>{window.styleSpec=null;styleDraftDirty=true;invalidateQuote();};
$('saveStyleSpec').onclick=async()=>{const text=$('styleSpecEditor').value;try{const spec=await api('/api/style-specs',JSON.parse(text));const read=await api('/api/style-specs/'+spec.id);if($('styleSpecEditor').value!==text)return;activateSpec(read);}catch(e){$('styleSpecStatus').textContent=e.message;}};
$('loadPreset').onclick=async()=>{try{const name=$('stylePreset').value;const list=await api('/api/style-presets');const p=list.find(p=>p.name===name);if(!p)throw Error('Preset wählen');activateSpec(await api('/api/style-specs/'+p.style_spec_id));$('presetName').value=name;}catch(e){$('styleSpecStatus').textContent=e.message;}};
$('savePreset').onclick=async()=>{try{if(!window.styleSpec)throw Error('Stilversion zuerst speichern');const name=$('presetName').value;const r=await fetch('/api/style-presets/'+encodeURIComponent(name),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({style_spec_id:window.styleSpec.id})});if(!r.ok)throw Error('Ungültiges Preset');const saved=await r.json();await refreshPresets();const p=window.stylePresets.find(p=>p.name===name);if(p?.style_spec_id!==saved.style_spec_id)throw Error('Preset-Readback fehlgeschlagen');$('styleSpecStatus').textContent='Preset gespeichert: '+name+' → '+p.style_spec_id;}catch(e){$('styleSpecStatus').textContent=e.message;}};
function showEvaluation(ev){window.currentEvaluation=ev;const lines=Object.entries(ev.gate.criteria).map(([k,v])=>`${k}: ${v.verdict}\n${v.observations.map(o=>`  ${o.location}: ${o.observation} [${o.evidence_ids.join(', ')}]`).join('\n')}`);$('strictReviewStatus').textContent=`${ev.status} · ${ev.gate.aggregate} · Produktion ${ev.gate.production_approved?'GATE PASS (Nutzerabnahme offen)':'GESPERRT'}\n${lines.join('\n')}\n${ev.gate.blockers.join('\n')}\nEvaluation: ${ev.id}`;$('paidReview').disabled=!(reviewerEnabled&&ev.status==='prepared_unreviewed');downloadLink();}
$('prepareEvaluation').onclick=async()=>{const epoch=++reviewEpoch;try{if(!window.candidate||!window.styleSpec)throw Error('Kandidat und gespeicherte Stilversion erforderlich');const ev=await api(`/api/terrain/${window.candidate.id}/evaluations`,{style_spec_id:window.styleSpec.id,density:Number($('finalDensity').value)});const read=await api('/api/evaluations/'+ev.id);if(epoch!==reviewEpoch)return;showEvaluation(read);}catch(e){$('strictReviewStatus').textContent=e.message;}};
$('paidReview').onclick=async()=>{try{const ev=window.currentEvaluation;if(!ev||!confirm('EIN kostenpflichtiges Bildreview im gemeinsamen Projektbudget? Exakte Guide-, Terrain- und Referenzbilder werden übertragen. Keine automatische Wiederholung.'))return;$('paidReview').disabled=true;const epoch=reviewEpoch;const result=await api('/api/evaluations/'+ev.id+'/review',{confirm_paid:true});if(epoch===reviewEpoch)showEvaluation(await api('/api/evaluations/'+result.id));await refreshGeneration();}catch(e){$('strictReviewStatus').textContent=e.message+' Keine Wiederholung bei unbekanntem Ausgang.';}};
$('productionExport').onclick=async()=>{try{if(!window.candidate)throw Error('Kandidat fehlt');const r=await fetch(exportUrl('production'));if(!r.ok){const body=await r.json();throw Error(body.detail);}const blob=await r.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='production-candidate.zip';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){$('strictReviewStatus').textContent+='\n'+e.message;}};
$('createCorrection').onclick=async()=>{try{if(!window.currentEvaluation||!$('repairOptIn').checked)throw Error('Standard AUS: Review und ausdrückliches Opt-in erforderlich');const w=await api('/api/corrections',{evaluation_id:window.currentEvaluation.id,enabled:true,max_attempts:Number($('repairMax').value)});$('correctionStatus').textContent=JSON.stringify(await api('/api/corrections/'+w.id),null,2)+'\nNoch kein Kauf. API /step erfordert confirm_paid:true; kein automatischer Start.';}catch(e){$('correctionStatus').textContent=e.message;}};
refreshPresets().catch(e=>{$('styleSpecStatus').textContent=e.message;});api('/api/reviewer/config').then(c=>{reviewerEnabled=c.enabled;});
let autoRun=null,autoTimer=null;
async function showAutoRun(id){
 const w=await api('/api/auto-repair/'+encodeURIComponent(id));autoRun=w;window.autoRun=w;$('autoRepairMax').value=String(w.max_iterations);$('autoRepairMax').disabled=true;$('autoRepairId').value=w.id;localStorage.setItem('terrain-auto-run',w.id);
 $('autoRepairProgress').textContent=`${w.status} · Phase ${w.phase} · ${(w.inherited_iterations||0)+w.iterations.length}/${w.max_iterations} Iterationen gesamt (${w.inherited_iterations||0} aus Vorgängern)\nStopp: ${w.stop_reason||'—'}\nBest: ${w.best_candidate_id}\nLatest: ${w.latest_candidate_id}\nLauf: ${w.id}\n`+w.iterations.map(a=>`#${a.number} ${a.id}\n${a.plan.action} / ${a.plan.classification?.join(', ')||a.plan.control?.strategy||'—'}\nJob: ${a.job_id||'—'} ${a.job_status||''}\nKandidat: ${a.candidate_id||'—'}\nReview: ${a.review?.id||'—'} · ${a.review?.blockers?.join('; ')||a.stop_reason||''}`).join('\n');
 $('constrainedOriginalLink')?.remove();
 const rejected=w.iterations.findLast(a=>a.preservation?.preserved===false);
 if(rejected){
  const p=rejected.preservation;
  $('autoRepairProgress').textContent+=`\nProviderbild erhalten, lokal verworfen: ${p.blocker}.\nAngefordert: ${p.source_size?.join('×')||'exakter Quellrahmen'}; erhalten: ${p.output_size?.join('×')} ${p.provider_format||''}.\nKein neuer Kandidat / kein Finalreview. Latest zeigt weiterhin die alte Eingabe. Historischer Stoppcode bleibt unverändert.`;
  if(/^[a-f0-9]{64}$/.test(rejected.job_id)){
   const link=document.createElement('a');link.id='constrainedOriginalLink';link.href='/api/generation/jobs/'+rejected.job_id+'/constrained-original';link.textContent='Verworfenes Provider-Original unverändert anzeigen / herunterladen';link.target='_blank';link.rel='noopener';$('autoRepairProgress').after(link);
  }
 }
 clearTimeout(autoTimer);if(w.status==='running')autoTimer=setTimeout(()=>showAutoRun(id).catch(e=>{$('autoRepairProgress').textContent=e.message;}),1500);
 await refreshGeneration();return w;
}
$('autoRepairStart').onclick=async()=>{try{if(!window.currentEvaluation||styleDraftDirty)throw Error('Aktuelle unveränderte Evaluation erforderlich');if(!confirm(`Einen automatischen Lauf mit maximal ${$('autoRepairMax').value} Reparaturen starten? Alle Bild- und Reviewkosten teilen denselben Projektdeckel. Keine neue Bestätigung pro Versuch.`))return;const w=await api('/api/auto-repair/start',{evaluation_id:window.currentEvaluation.id,confirm_paid:true,max_iterations:Number($('autoRepairMax').value)});await showAutoRun(w.id);}catch(e){$('autoRepairProgress').textContent=e.message;}};
$('autoRepairStatus').onclick=()=>showAutoRun($('autoRepairId').value).catch(e=>{$('autoRepairProgress').textContent=e.message;});
for(const [button,action] of [['autoRepairResume','resume'],['autoRepairCancel','cancel']])$(button).onclick=async()=>{try{const id=$('autoRepairId').value;await api('/api/auto-repair/'+encodeURIComponent(id)+'/'+action,{});await showAutoRun(id);}catch(e){$('autoRepairProgress').textContent=e.message;}};
for(const [button,which] of [['autoRepairBest','best_candidate_id'],['autoRepairLatest','latest_candidate_id']])$(button).onclick=async()=>{try{const w=await showAutoRun($('autoRepairId').value);if(window.workbench?.revision!==w.frozen.revision)throw Error('Zuerst die unveränderte Layoutrevision laden');await selectCandidate(await api('/api/terrain/'+w[which]));activateSpec(await api('/api/style-specs/'+w.frozen.style));$('finalDensity').value=String(w.frozen.density);const eid=which==='best_candidate_id'?w.best_evaluation_id:w.evaluation_id;const ev=await api('/api/evaluations/'+eid);if(ev.binding.candidate_id===w[which])showEvaluation(ev);}catch(e){$('autoRepairProgress').textContent=e.message;}};
$('autoRepairReadiness').onclick=async()=>{
 const id=$('autoRepairId').value.trim();if(!id){$('autoRepairReadinessStatus').textContent='Zuerst eine gespeicherte Lauf-ID laden.';return;}
 $('autoRepairReadiness').disabled=true;
 try{const proof=await api('/api/auto-repair/'+encodeURIComponent(id)+'/continuation-readiness');if($('autoRepairId').value.trim()!==id)return;
 $('autoRepairReadinessStatus').textContent=(proof.eligible?'Belegprüfung bestanden — kein neuer Lauf gestartet.':'GESPERRT — keine sichere Fortsetzung.')+'\n'+(proof.blockers||[]).join('\n');
 }catch(e){$('autoRepairReadinessStatus').textContent='Prüfung fehlgeschlagen: '+e.message;}finally{$('autoRepairReadiness').disabled=false;}
};
const savedRun=localStorage.getItem('terrain-auto-run');if(savedRun)showAutoRun(savedRun).catch(()=>{});

// Retained batch readback never needs the original chat-cache reference files.
let batchEpoch=0,batchTimer=null;
function batchError(e){$('batchProgress').textContent=e.message;$('batchResume').disabled=true;$('batchCancel').disabled=true;}
async function showBatch(id){
 const epoch=++batchEpoch;clearTimeout(batchTimer);
 $('batchResume').disabled=true;$('batchCancel').disabled=true;
 const w=await api('/api/overnight-batch/'+encodeURIComponent(id));if(epoch!==batchEpoch)return;
 window.overnightBatch=w;$('batchId').value=w.id;localStorage.setItem('terrain-overnight-batch',w.id);
 $('batchProgress').textContent=`${w.display_status} · gespeichert: ${w.status}\nLauf: ${w.id}\nLayout: ${w.frozen.revision}\nGrenzen: ${w.limits.initial_per_style} Initialbild/Stil, ${w.limits.repair_per_style} Repairs/Stil\nNutzerabnahme separat; vorhandene Holds bleiben.\n`+w.styles.map((a,i)=>`Stil ${i+1}: ${a.style_spec_id}\n${a.display_status} · Phase ${a.phase}\nStopp: ${a.stop_reason||'—'}\nQuelle: ${a.source_candidate_id||'—'}\nKandidat: ${a.candidate_id||'—'}\nEvaluation: ${a.evaluation_id||'—'}`).join('\n\n');
 $('batchResume').disabled=!w.can_resume;$('batchCancel').disabled=!w.can_cancel;
 $('batchArtifacts').replaceChildren();
 for(const [i,a] of w.styles.entries()){
  for(const [label,url] of [[`Stil ${i+1}: Originalquelle (Diagnose, nicht Gameplay)`,a.source_candidate_id?`/api/terrain/${a.source_candidate_id}/source.png`:null],[`Stil ${i+1}: gespeicherte Evaluation`,a.evaluation_id?`/api/evaluations/${a.evaluation_id}`:null]]){
   if(!url)continue;const link=document.createElement('a');link.textContent=label;link.href=url;link.target='_blank';link.rel='noopener';$('batchArtifacts').append(link,document.createElement('br'));
  }
 }
 if(w.status==='running')batchTimer=setTimeout(()=>showBatch(w.id).catch(batchError),1500);
 return w;
}
async function discoverBatches(){
 const list=await api('/api/overnight-batch');$('savedBatches').replaceChildren(new Option('Batch wählen',''),...list.map(w=>new Option(`${w.display_status} · ${w.id.slice(0,12)}`,w.id)));
 const saved=localStorage.getItem('terrain-overnight-batch');const id=list.find(w=>w.id===saved)?.id||list[0]?.id;
 if(id){$('savedBatches').value=id;await showBatch(id);}
}
$('batchRefresh').onclick=()=>discoverBatches().catch(batchError);
$('batchStatus').onclick=()=>showBatch($('batchId').value.trim()).catch(batchError);
$('savedBatches').onchange=()=>{if($('savedBatches').value)showBatch($('savedBatches').value).catch(batchError);};
$('batchId').oninput=()=>{batchEpoch++;clearTimeout(batchTimer);$('batchResume').disabled=true;$('batchCancel').disabled=true;};
for(const [button,action] of [['batchResume','resume'],['batchCancel','cancel']])$(button).onclick=async()=>{
 const id=window.overnightBatch?.id;if(!id)return;
 $('batchResume').disabled=true;$('batchCancel').disabled=true;
 try{await api('/api/overnight-batch/'+encodeURIComponent(id)+'/'+action,{});await showBatch(id);}catch(e){batchError(e);}
};
discoverBatches().catch(batchError);

