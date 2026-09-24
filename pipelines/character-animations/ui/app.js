(() => {
  'use strict';

  const $ = (selector) => document.querySelector(selector);
  const prefix = (() => {
    const marker = location.pathname.indexOf('/ui');
    return marker >= 0 ? location.pathname.slice(0, marker) : '';
  })();
  const apiUrl = (path) => `${prefix}/v1${path}`;
  const tokenKey = 'animation-pipeline-token';
  const reviewModel = 'google/gemini-3.8-flash';
  const configurableSourcePreset = 'minimax-h3-action-3s-480p-v1';
  const state = {
    token: sessionStorage.getItem(tokenKey) || '',
    capabilities: null,
    jobs: [],
    job: null,
    artifact: null,
    objectUrls: [],
    demoPlayer: null,
    jobPlayer: null,
    sourceVideoSettings: {duration: 3, resolution: '480p'},
  };

  const stageNames = {
    inspect_reference: 'Referenz prüfen',
    generate_facing: 'Neue Ansicht generieren',
    generate_video: 'Bewegungsvideo generieren',
    extract_frames: 'Frames auswählen',
    automatic_review: 'Automatische Quellenauswahl',
    remove_background: 'Hintergrund entfernen',
    pack: 'Atlas packen',
    mirror: 'Atlas spiegeln',
  };
  const stateNames = {
    queued: 'Wartet', running: 'Läuft', needs_review: 'Freigabe nötig',
    completed: 'Abgeschlossen', failed: 'Fehlgeschlagen', needs_attention: 'Klärung nötig',
  };

  function showNotice(message, error = true) {
    const box = $('#notice');
    box.textContent = message;
    box.className = `notice${error ? ' error' : ''}`;
    clearTimeout(showNotice.timer);
    showNotice.timer = setTimeout(() => box.classList.add('hidden'), 9000);
  }

  async function apiFetch(path, options = {}) {
    if (!state.token) throw new Error('Bitte zuerst den API-Token eingeben.');
    const headers = new Headers(options.headers || {});
    headers.set('Authorization', `Bearer ${state.token}`);
    const response = await fetch(apiUrl(path), {...options, headers});
    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      try {
        const body = await response.json();
        detail = body.detail || detail;
      } catch (_) { /* Response was not JSON. */ }
      throw new Error(detail);
    }
    return response;
  }

  function revokeObjectUrls() {
    state.objectUrls.forEach((url) => URL.revokeObjectURL(url));
    state.objectUrls = [];
  }

  async function blobUrl(path) {
    const response = await apiFetch(path);
    const url = URL.createObjectURL(await response.blob());
    state.objectUrls.push(url);
    return url;
  }

  function createAtlasPlayer(canvas, manifest, image) {
    if (manifest.schema !== 'animation-pipeline-atlas-v1') {
      throw new Error('Nicht unterstütztes Atlas-Manifest.');
    }
    const byId = new Map(manifest.frames.map((frame) => [frame.id, frame]));
    const frames = manifest.clip.frames.map((id) => byId.get(id)).filter(Boolean);
    if (!frames.length) throw new Error('Das Manifest enthält keine abspielbaren Frames.');
    const context = canvas.getContext('2d');
    context.imageSmoothingEnabled = false;
    let playing = true;
    let mirrored = false;
    let frameIndex = 0;
    let lastStep = performance.now();
    const fps = Number(manifest.clip.fps) || 1;
    const loop = manifest.clip.loop !== false;
    let raf = 0;

    function draw() {
      const frame = frames[frameIndex];
      const rect = frame.rect;
      const anchor = frame.anchor || {x: 0.5, y: 1};
      const scale = Math.max(1, Math.floor(Math.min(canvas.width / rect.width, canvas.height / rect.height) * 0.78));
      const width = rect.width * scale;
      const height = rect.height * scale;
      const rootX = Math.round(canvas.width / 2);
      const rootY = Math.round(canvas.height * 0.87);
      const x = Math.round(rootX - anchor.x * width);
      const y = Math.round(rootY - anchor.y * height);
      context.clearRect(0, 0, canvas.width, canvas.height);
      context.save();
      if (mirrored) {
        context.translate(canvas.width, 0);
        context.scale(-1, 1);
      }
      context.drawImage(image, rect.x, rect.y, rect.width, rect.height, x, y, width, height);
      context.restore();
      canvas.dataset.frame = String(frameIndex);
      canvas.dataset.frameId = frame.id;
      canvas.dataset.playing = String(playing);
      canvas.dataset.mirrored = String(mirrored);
      canvas.dataset.anchor = `${anchor.x},${anchor.y}`;
    }

    function tick(now) {
      if (playing && now - lastStep >= 1000 / fps) {
        const steps = Math.floor((now - lastStep) / (1000 / fps));
        const next = frameIndex + steps;
        frameIndex = loop ? next % frames.length : Math.min(next, frames.length - 1);
        lastStep = now;
        draw();
        if (!loop && frameIndex === frames.length - 1) playing = false;
      }
      raf = requestAnimationFrame(tick);
    }

    draw();
    raf = requestAnimationFrame(tick);
    return {
      pause() { playing = false; draw(); },
      play() { playing = true; lastStep = performance.now(); draw(); },
      toggle() { playing ? this.pause() : this.play(); return playing; },
      mirror(value = !mirrored) { mirrored = Boolean(value); draw(); return mirrored; },
      destroy() { cancelAnimationFrame(raf); },
      get playing() { return playing; },
      get frame() { return frameIndex; },
      get mirrored() { return mirrored; },
    };
  }

  async function loadDemo() {
    try {
      const [manifestResponse, image] = await Promise.all([
        fetch('./demo/atlas-manifest.json'),
        new Promise((resolve, reject) => {
          const atlas = new Image();
          atlas.onload = () => resolve(atlas);
          atlas.onerror = () => reject(new Error('Demo-Atlas konnte nicht geladen werden.'));
          atlas.src = './demo/atlas.png';
        }),
      ]);
      if (!manifestResponse.ok) throw new Error('Demo-Manifest konnte nicht geladen werden.');
      const manifest = await manifestResponse.json();
      state.demoPlayer = createAtlasPlayer($('#demoCanvas'), manifest, image);
      $('#demoDirection').textContent = `Richtung ${manifest.clip.direction.toUpperCase()}`;
      $('#demoMeta').textContent = `${manifest.frames.length} Frames · ${manifest.clip.fps} FPS · Anker aus Manifest`;
    } catch (error) {
      $('#demoMeta').textContent = error.message;
      showNotice(error.message);
    }
  }

  async function loadAgentPrompt() {
    const field = $('#agentPrompt');
    const button = $('#copyAgentPrompt');
    try {
      const response = await fetch('../agent-prompt.txt');
      if (!response.ok) throw new Error('Agent-Prompt konnte nicht geladen werden.');
      field.value = await response.text();
      button.disabled = false;
    } catch (error) {
      field.value = error.message;
      $('#agentCopyStatus').textContent = error.message;
    }
  }

  async function copyAgentPrompt() {
    const field = $('#agentPrompt');
    const status = $('#agentCopyStatus');
    const text = field.value;
    if (!text || $('#copyAgentPrompt').disabled) return;
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard API nicht verfügbar');
      await navigator.clipboard.writeText(text);
    } catch (_) {
      field.focus();
      field.select();
      field.setSelectionRange(0, field.value.length);
      if (!document.execCommand('copy')) {
        status.textContent = 'Kopieren nicht möglich. Der Prompt ist vollständig ausgewählt.';
        return;
      }
    }
    status.textContent = 'Prompt kopiert — ohne API-Token.';
  }

  function updateConnection(connected) {
    $('#connectionState').textContent = connected ? 'Verbunden' : 'Nicht verbunden';
    $('#connectionState').className = `pill ${connected ? 'ok' : 'muted'}`;
    $('#uploadButton').disabled = !connected;
  }

  async function connect() {
    try {
      const [capabilitiesResponse, jobsResponse] = await Promise.all([
        apiFetch('/capabilities'), apiFetch('/jobs'),
      ]);
      state.capabilities = await capabilitiesResponse.json();
      state.jobs = await jobsResponse.json();
      updateConnection(true);
      renderPolicy();
      renderJobs();
      if (state.job) await openJob(state.job.id, false);
    } catch (error) {
      updateConnection(false);
      showNotice(`Verbindung fehlgeschlagen: ${error.message}`);
    }
  }

  function renderPolicy() {
    if (!state.capabilities) return;
    const policy = state.capabilities.paid_policy;
    $('#paidPolicy').textContent = policy.enabled
      ? `Bezahlte Stufen sind serverseitig aktiv · max. $${policy.max_stage_usd.toFixed(3)} pro Stufe.`
      : `Bezahlte Stufen sind serverseitig gesperrt · Limit $${policy.max_stage_usd.toFixed(3)}. Freie Stufen bleiben nutzbar.`;
  }

  function formatDate(seconds) {
    return new Intl.DateTimeFormat('de-DE', {dateStyle: 'short', timeStyle: 'short'}).format(new Date(seconds * 1000));
  }

  function renderJobs() {
    $('#jobsEmpty').classList.toggle('hidden', state.jobs.length > 0);
    const list = $('#jobsList');
    list.replaceChildren(...state.jobs.map((job) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `job-card${state.job?.id === job.id ? ' selected' : ''}`;
      const info = document.createElement('span');
      const title = document.createElement('strong');
      title.textContent = stageNames[job.latest_stage] || 'Neuer Auftrag';
      const details = document.createElement('small');
      details.textContent = `${job.id.slice(0, 8)} · ${formatDate(job.created_at)}`;
      info.append(title, details);
      const status = document.createElement('span');
      status.className = `state ${job.state}`;
      status.textContent = stateNames[job.state] || job.state;
      button.append(info, status);
      button.addEventListener('click', () => openJob(job.id));
      return button;
    }));
  }

  async function refreshJobs(silent = false) {
    if (!state.token) return;
    try {
      state.jobs = await (await apiFetch('/jobs')).json();
      renderJobs();
      if (state.job) await openJob(state.job.id, false);
    } catch (error) {
      if (!silent) showNotice(`Aufträge konnten nicht geladen werden: ${error.message}`);
    }
  }

  async function openJob(id, scroll = true) {
    try {
      state.job = await (await apiFetch(`/jobs/${encodeURIComponent(id)}`)).json();
      const index = state.jobs.findIndex((job) => job.id === id);
      if (index >= 0) state.jobs[index] = {...state.jobs[index], ...state.job};
      renderJobs();
      renderJob();
      if (scroll) $('#jobDetail').scrollIntoView({behavior: 'smooth', block: 'start'});
    } catch (error) {
      showNotice(`Auftrag konnte nicht geladen werden: ${error.message}`);
    }
  }

  function renderJob() {
    const job = state.job;
    $('#jobDetail').classList.remove('hidden');
    $('#detailId').textContent = job.id.slice(0, 8);
    const message = job.message ? ` · ${job.message}` : '';
    $('#jobStatus').innerHTML = `<span class="state ${job.state}">${stateNames[job.state] || job.state}</span> · ${stageNames[job.latest_stage] || 'Upload'}${escapeHtml(message)}`;
    $('#downloadZip').onclick = downloadZip;
    const list = $('#artifactList');
    list.replaceChildren(...job.artifacts.map((artifact) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `artifact-button${state.artifact?.name === artifact.name ? ' selected' : ''}`;
      const name = document.createElement('span');
      name.textContent = artifact.name;
      const details = document.createElement('small');
      details.textContent = `Revision ${artifact.revision} · ${artifact.sha256.slice(0, 12)}… · ${formatBytes(artifact.bytes)}`;
      button.append(name, details);
      button.addEventListener('click', () => selectArtifact(artifact));
      return button;
    }));
    renderStageForm();
    renderAutomaticReview();
  }

  async function renderAutomaticReview() {
    if (!state.job || !state.capabilities) return;
    const capability = state.capabilities.automatic_review;
    if (capability.model !== reviewModel) throw new Error('Unerwartetes automatisches Review-Modell.');
    const videos = state.job.artifacts.filter((item) => /\.(mp4|mov|webm|mkv)$/i.test(item.name));
    const select = $('#automaticReviewArtifact');
    const previous = select.value;
    select.replaceChildren(...videos.map((artifact) => {
      const option = document.createElement('option');
      option.value = artifact.name;
      option.textContent = `${artifact.name} · Revision ${artifact.revision}`;
      option.dataset.sha256 = artifact.sha256;
      option.dataset.revision = String(artifact.revision);
      return option;
    }));
    if (videos.some((item) => item.name === previous)) select.value = previous;
    const reviewer = capability.reviewer;
    const framePolicy = capability.frame_policy;
    const frameSelect = $('#automaticReviewFramePolicy');
    if (!framePolicy.allowed.includes(frameSelect.value)) frameSelect.value = framePolicy.default;
    $('#automaticReviewPolicy').textContent = reviewer.available
      ? `Lokale Analyse verfügbar · Reviewer ${capability.model} verfügbar · kein Fallback · max. $${reviewer.max_review_usd.toFixed(3)}.`
      : `Lokale Analyse verfügbar · Reviewer blockiert: ${reviewer.blocked_reason}.`;
    $('#authorizeAutomaticReview').disabled = !reviewer.available;
    $('#automaticReviewBudget').disabled = !reviewer.available;
    $('#automaticReviewBudget').max = String(reviewer.max_review_usd || 0);
    $('#startAutomaticReview').disabled = videos.length === 0;
    const container = $('#automaticReviewCandidates');
    const review = state.job.automatic_reviews?.[0];
    if (!review) {
      container.textContent = videos.length ? 'Noch keine automatische Analyse für dieses Video.' : 'Kein Videoartefakt vorhanden.';
      return;
    }
    container.replaceChildren();
    const summary = document.createElement('div');
    summary.className = `candidate-card ${review.status}`;
    const title = document.createElement('strong');
    title.textContent = review.status === 'approved' ? 'Modellvalidierte Auswahl' : review.status === 'rejected' ? 'Lokal abgelehnt' : 'Klärung nötig';
    const meta = document.createElement('small');
    meta.textContent = `${review.model} · Quelle ${review.source_sha256.slice(0, 12)}… · ${review.candidate_count} Kandidaten`;
    summary.append(title, meta);
    container.append(summary);
    const analysisArtifact = state.job.artifacts.find((item) => item.name === review.analysis_artifact);
    if (!analysisArtifact) return;
    try {
      const analysis = await (await apiFetch(`/jobs/${state.job.id}/artifacts/${encodeURIComponent(analysisArtifact.name)}`)).json();
      analysis.candidates.forEach((candidate) => {
        const card = document.createElement('div');
        card.className = `candidate-card${review.selected_candidate?.id === candidate.id ? ' selected' : ''}`;
        const heading = document.createElement('strong');
        heading.textContent = `${candidate.id}${review.selected_candidate?.id === candidate.id ? ' · ausgewählt' : ''}`;
        const timing = document.createElement('small');
        timing.textContent = `${candidate.start_timestamp_seconds.toFixed(3)}–${candidate.end_timestamp_seconds.toFixed(3)} s · native Frames ${candidate.start_source_frame_index}–${candidate.end_source_frame_index - 1} · Heuristik ${candidate.heuristic_score.toFixed(3)}`;
        card.append(heading, timing);
        container.append(card);
      });
    } catch (error) {
      const failure = document.createElement('span');
      failure.textContent = `Kandidaten konnten nicht geladen werden: ${error.message}`;
      container.append(failure);
    }
  }

  async function startAutomaticReview() {
    const select = $('#automaticReviewArtifact');
    const option = select.selectedOptions[0];
    if (!option || !state.job) return;
    const authorize = $('#authorizeAutomaticReview').checked;
    const payload = {
      artifact: option.value,
      sha256: option.dataset.sha256,
      revision: Number(option.dataset.revision),
      authorize_paid_review: authorize,
      budget_cap_usd: authorize ? Number($('#automaticReviewBudget').value) : null,
      frame_policy: $('#automaticReviewFramePolicy').value,
    };
    try {
      await apiFetch(`/jobs/${state.job.id}/automatic-review`, {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload),
      });
      showNotice('Automatische lokale Analyse wurde eingereiht.', false);
      await refreshJobs(true);
    } catch (error) {
      showNotice(`Automatische Analyse konnte nicht gestartet werden: ${error.message}`);
    }
  }

  function formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KiB`;
    return `${(bytes / 1048576).toFixed(1)} MiB`;
  }

  function escapeHtml(value) {
    const span = document.createElement('span');
    span.textContent = value;
    return span.innerHTML;
  }

  async function selectArtifact(artifact) {
    state.artifact = artifact;
    renderJob();
    $('#reviewBox').classList.remove('hidden');
    $('#reviewIdentity').textContent = `SHA-256 ${artifact.sha256} · Revision ${artifact.revision}`;
    const preview = $('#artifactPreview');
    preview.textContent = 'Wird geladen …';
    try {
      const encoded = encodeURIComponent(artifact.name);
      const response = await apiFetch(`/jobs/${state.job.id}/artifacts/${encoded}`);
      const blob = await response.blob();
      const lower = artifact.name.toLowerCase();
      preview.replaceChildren();
      if (/\.(png|jpe?g|webp)$/.test(lower)) {
        const image = document.createElement('img');
        const url = URL.createObjectURL(blob);
        state.objectUrls.push(url);
        image.src = url;
        image.alt = artifact.name;
        preview.append(image);
      } else if (/\.mp4$/.test(lower)) {
        const video = document.createElement('video');
        const url = URL.createObjectURL(blob);
        state.objectUrls.push(url);
        video.src = url;
        video.controls = true;
        preview.append(video);
      } else if (/\.json$/.test(lower)) {
        const data = JSON.parse(await blob.text());
        if (data.schema === 'animation-pipeline-atlas-v1' && state.job.artifacts.some((item) => item.name === data.image.file)) {
          await renderJobAtlas(preview, data);
        } else {
          const pre = document.createElement('pre');
          pre.textContent = JSON.stringify(data, null, 2);
          preview.append(pre);
        }
      } else {
        preview.textContent = 'Für dieses Dateiformat gibt es keine direkte Vorschau.';
      }
    } catch (error) {
      preview.textContent = `Vorschau fehlgeschlagen: ${error.message}`;
    }
  }

  async function renderJobAtlas(preview, manifest) {
    if (state.jobPlayer) state.jobPlayer.destroy();
    const canvas = document.createElement('canvas');
    canvas.width = 320;
    canvas.height = 320;
    const controls = document.createElement('div');
    controls.className = 'controls';
    const play = document.createElement('button');
    play.type = 'button'; play.className = 'secondary'; play.textContent = 'Pause';
    const mirror = document.createElement('button');
    mirror.type = 'button'; mirror.className = 'secondary'; mirror.textContent = 'Spiegeln';
    const meta = document.createElement('span');
    meta.className = 'meta'; meta.textContent = `${manifest.clip.direction.toUpperCase()} · ${manifest.clip.fps} FPS · ${manifest.frames.length} Frames`;
    controls.append(play, mirror, meta);
    preview.append(canvas, controls);
    const image = new Image();
    image.src = await blobUrl(`/jobs/${state.job.id}/artifacts/${encodeURIComponent(manifest.image.file)}`);
    await image.decode();
    state.jobPlayer = createAtlasPlayer(canvas, manifest, image);
    play.addEventListener('click', () => {
      const playing = state.jobPlayer.toggle();
      play.textContent = playing ? 'Pause' : 'Abspielen';
    });
    mirror.addEventListener('click', () => mirror.setAttribute('aria-pressed', String(state.jobPlayer.mirror())));
  }

  async function review(decision) {
    if (!state.artifact || !state.job) return;
    try {
      await apiFetch(`/jobs/${state.job.id}/reviews`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({artifact: state.artifact.name, sha256: state.artifact.sha256, decision}),
      });
      showNotice(decision === 'approve' ? 'Exakte Artefakt-Revision freigegeben.' : 'Artefakt abgelehnt.', false);
      await openJob(state.job.id, false);
    } catch (error) {
      showNotice(`Freigabe fehlgeschlagen: ${error.message}`);
    }
  }

  function availableStageTemplates(job) {
    const names = new Set(job.artifacts.map((item) => item.name));
    const images = job.artifacts.map((item) => item.name).filter((name) => /\.(png|webp|jpe?g)$/.test(name));
    const selected = images.filter((name) => /^(selected|cutout|normalized)-frame-/.test(name));
    const templates = [{stage: 'inspect_reference', params: {input: 'reference.png'}}];
    if (names.has('reference.png')) templates.push({stage: 'generate_facing', params: {input: 'reference.png', preset: presetFor('image_edit'), prompt: 'Drehe die Figur in eine neue isometrische Blickrichtung.', aspect_ratio: '1:1', output_format: 'png'}});
    if (names.has('facing-output.png')) {
      const videoPreset = sourceVideoPreset();
      const videoParams = videoParamsForPreset(videoPreset, 'facing-output.png');
      if (videoPreset === configurableSourcePreset) Object.assign(videoParams, state.sourceVideoSettings);
      templates.push({stage: 'generate_video', params: videoParams});
    }
    if (names.has('video-output.mp4')) templates.push({stage: 'extract_frames', params: {input: 'video-output.mp4', fps: 12, indices: [0, 1, 2, 3], output_prefix: 'selected'}});
    if (selected.length) templates.push({stage: 'remove_background', params: {inputs: selected.slice(0, 16), preset: presetFor('background_removal')}});
    if (selected.length) templates.push({stage: 'pack', params: {inputs: selected.slice(0, 16), image_id: 'sprite-walk', action: 'walk', direction: 'se', fps: 12, loop: true, canvas: {width: 80, height: 80}, target_visible_height: 58, target_root: {x: 40, y: 72}, anchor: {x: 0.5, y: 0.9}, gutter: 2, columns: 8, resample: 'nearest'}});
    if (names.has('automatic-review-result.json') && names.has('video-output.mp4')) templates.push({stage: 'spatial_export', params: {source: 'video-output.mp4', selection_receipt: 'automatic-review-result.json', selection_mode: 'automatic_model_validated', export_preset: 'derived-native-160-v1', removal_preset: 'waldlicht-removal-v1', removal_recipe: 'wavespeed-image-background-remover-output-v1'}});
    if (names.has('atlas.png') && names.has('atlas-manifest.json')) templates.push({stage: 'mirror', params: {atlas: 'atlas.png', manifest: 'atlas-manifest.json', target_direction: 'nw', target_image_id: 'sprite-walk-nw-derived'}});
    return templates.filter((item) => state.capabilities?.stages[item.stage]?.supported !== false && !Object.values(item.params).includes(null));
  }

  function presetFor(capability) {
    return state.capabilities?.presets.find((preset) => preset.capability === capability)?.name || null;
  }

  function sourceVideoPreset() {
    return state.capabilities?.presets.find((preset) => preset.name === configurableSourcePreset)?.name
      || presetFor('image_to_video');
  }

  function videoParamsForPreset(presetName, input = 'facing-output.png') {
    const preset = state.capabilities?.presets.find((item) => item.name === presetName);
    const defaults = Object.fromEntries(
      Object.entries(preset?.defaults || {}).filter(([key]) => key !== 'first_equals_last'),
    );
    return {
      input,
      preset: presetName,
      prompt: 'Eine saubere, zyklische Gehbewegung auf der Stelle.',
      ...defaults,
    };
  }

  function syncSourceVideoFields(params, presetName) {
    const preset = state.capabilities?.presets.find((item) => item.name === presetName);
    const options = preset?.parameter_options || {};
    const visible = presetName === configurableSourcePreset
      && Array.isArray(options.duration) && Array.isArray(options.resolution);
    $('#sourceVideoFields').classList.toggle('hidden', !visible);
    if (!visible) return;
    const duration = options.duration.includes(params.duration) ? params.duration : preset.defaults.duration;
    const resolution = options.resolution.includes(params.resolution) ? params.resolution : preset.defaults.resolution;
    $('#sourceDuration').value = String(duration);
    $('#sourceResolution').value = resolution;
    state.sourceVideoSettings = {duration, resolution};
    const quote = preset.option_quotes?.find((item) =>
      item.priced_inputs.duration === duration && item.priced_inputs.resolution === resolution
    );
    $('#sourceVideoQuote').textContent = quote ? `Preisrahmen für diese Auswahl: ca. $${quote.quoted_usd.toFixed(3)}.` : '';
  }

  function applySourceVideoFields() {
    const params = JSON.parse($('#stageParams').value);
    params.duration = Number($('#sourceDuration').value);
    params.resolution = $('#sourceResolution').value;
    state.sourceVideoSettings = {duration: params.duration, resolution: params.resolution};
    $('#stageParams').value = JSON.stringify(params, null, 2);
    syncSourceVideoFields(params, $('#presetName').value);
  }

  function applyExportResolution() {
    const params = JSON.parse($('#stageParams').value);
    params.export_preset = `derived-native-${$('#exportResolution').value}-v1`;
    $('#stageParams').value = JSON.stringify(params, null, 2);
  }

  function renderStageForm() {
    if (!state.capabilities || !state.job) return;
    const select = $('#stageName');
    const previous = select.value;
    const templates = availableStageTemplates(state.job);
    select.replaceChildren(...templates.map((item) => {
      const option = document.createElement('option');
      option.value = item.stage;
      const config = state.capabilities.stages[item.stage];
      option.textContent = `${stageNames[item.stage]}${config.paid ? ' · bezahlt' : ' · kostenlos'}`;
      return option;
    }));
    if (templates.some((item) => item.stage === previous)) select.value = previous;
    select.onchange = updateStageFields;
    select.dataset.templates = JSON.stringify(templates);
    updateStageFields();
  }

  function updateStageFields() {
    const select = $('#stageName');
    const templates = JSON.parse(select.dataset.templates || '[]');
    const template = templates.find((item) => item.stage === select.value);
    if (!template) return;
    const config = state.capabilities.stages[template.stage];
    $('#stageParams').value = JSON.stringify(template.params, null, 2);
    const capability = config.capability;
    const presets = state.capabilities.presets.filter((preset) => preset.capability === capability);
    $('#presetLabel').classList.toggle('hidden', presets.length === 0);
    $('#presetName').replaceChildren(...presets.map((preset) => {
      const option = document.createElement('option');
      option.value = preset.name;
      option.textContent = `${preset.name} · ca. $${preset.quote.quoted_usd.toFixed(3)}`;
      return option;
    }));
    if (presets.some((preset) => preset.name === template.params.preset)) {
      $('#presetName').value = template.params.preset;
    }
    syncSourceVideoFields(template.params, $('#presetName').value);
    const isSpatialExport = template.stage === 'spatial_export';
    $('#exportResolutionFields').classList.toggle('hidden', !isSpatialExport);
    if (isSpatialExport) $('#exportResolution').value = template.params.export_preset.includes('-80-') ? '80' : '160';
    $('#presetName').onchange = () => {
      const params = JSON.parse($('#stageParams').value);
      const selected = $('#presetName').value;
      const next = template.stage === 'generate_video'
        ? videoParamsForPreset(selected, params.input)
        : {...params, preset: selected};
      $('#stageParams').value = JSON.stringify(next, null, 2);
      syncSourceVideoFields(next, selected);
    };
    const paid = config.paid;
    $('#paidFields').classList.toggle('hidden', !paid);
    $('#submitStage').disabled = paid && !state.capabilities.paid_policy.enabled;
    $('#submitStage').textContent = paid && !state.capabilities.paid_policy.enabled ? 'Server sperrt bezahlte Stufen' : 'Stufe anfordern';
    $('#budgetCap').max = String(state.capabilities.paid_policy.max_stage_usd);
  }

  async function submitStage(event) {
    event.preventDefault();
    try {
      const stage = $('#stageName').value;
      const config = state.capabilities.stages[stage];
      if (stage === 'generate_video' && $('#presetName').value === configurableSourcePreset) {
        applySourceVideoFields();
      }
      if (stage === 'spatial_export') applyExportResolution();
      const payload = {stage, params: JSON.parse($('#stageParams').value)};
      if (config.paid) {
        payload.authorize_paid = $('#authorizePaid').checked;
        payload.budget_cap_usd = Number($('#budgetCap').value);
      }
      await apiFetch(`/jobs/${state.job.id}/stages`, {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload),
      });
      showNotice('Stufe wurde eingereiht.', false);
      await refreshJobs(true);
    } catch (error) {
      showNotice(`Stufe konnte nicht gestartet werden: ${error.message}`);
    }
  }

  async function downloadZip(event) {
    event.preventDefault();
    try {
      const response = await apiFetch(`/jobs/${state.job.id}/download`);
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url;
      link.download = `animation-job-${state.job.id}.zip`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      showNotice(`ZIP-Download fehlgeschlagen: ${error.message}`);
    }
  }

  $('#tokenForm').addEventListener('submit', (event) => {
    event.preventDefault();
    state.token = $('#token').value;
    sessionStorage.setItem(tokenKey, state.token);
    $('#token').value = '';
    connect();
  });
  $('#forgetToken').addEventListener('click', () => {
    state.token = '';
    sessionStorage.removeItem(tokenKey);
    updateConnection(false);
    state.jobs = []; state.job = null; state.artifact = null;
    renderJobs(); $('#jobDetail').classList.add('hidden');
  });
  $('#reference').addEventListener('change', (event) => {
    const file = event.target.files[0];
    if (!file) return;
    const preview = $('#localPreview');
    preview.src = URL.createObjectURL(file);
    preview.classList.remove('hidden');
    $('#dropText').classList.add('hidden');
  });
  $('#uploadForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const file = $('#reference').files[0];
    if (!file) return;
    const data = new FormData();
    data.append('reference', file, file.name);
    data.append('options', JSON.stringify({auto_start: true}));
    $('#uploadButton').disabled = true;
    $('#uploadButton').textContent = 'Wird geprüft …';
    try {
      const job = await (await apiFetch('/jobs', {method: 'POST', body: data})).json();
      showNotice('Referenz hochgeladen. Die kostenlose Prüfung läuft.', false);
      await refreshJobs(true);
      await openJob(job.id);
    } catch (error) {
      showNotice(`Upload fehlgeschlagen: ${error.message}`);
    } finally {
      $('#uploadButton').disabled = !state.token;
      $('#uploadButton').textContent = 'Hochladen & prüfen';
    }
  });
  $('#refreshJobs').addEventListener('click', () => refreshJobs());
  $('#approveArtifact').addEventListener('click', () => review('approve'));
  $('#rejectArtifact').addEventListener('click', () => review('reject'));
  $('#stageForm').addEventListener('submit', submitStage);
  $('#sourceDuration').addEventListener('change', applySourceVideoFields);
  $('#sourceResolution').addEventListener('change', applySourceVideoFields);
  $('#exportResolution').addEventListener('change', applyExportResolution);
  $('#startAutomaticReview').addEventListener('click', startAutomaticReview);
  $('#copyAgentPrompt').addEventListener('click', copyAgentPrompt);
  $('#demoPlay').addEventListener('click', () => {
    if (!state.demoPlayer) return;
    const playing = state.demoPlayer.toggle();
    $('#demoPlay').textContent = playing ? 'Pause' : 'Abspielen';
  });
  $('#demoMirror').addEventListener('click', () => {
    if (!state.demoPlayer) return;
    $('#demoMirror').setAttribute('aria-pressed', String(state.demoPlayer.mirror()));
  });

  window.__animationUi = {
    getDemoFrame: () => state.demoPlayer?.frame,
    isDemoPlaying: () => state.demoPlayer?.playing,
    apiPrefix: prefix,
    getAgentPrompt: () => $('#agentPrompt').value,
  };
  window.addEventListener('beforeunload', revokeObjectUrls);
  setInterval(() => { if (state.token && !document.hidden) refreshJobs(true); }, 2500);
  loadDemo();
  loadAgentPrompt();
  if (state.token) connect();
})();
