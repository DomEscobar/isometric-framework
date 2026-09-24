# Animation Pipeline: Anleitung für Coding-Agents

Öffentliche Basis-URL: `https://isoani.huecki.com/animation`

- Diese Anleitung: `https://isoani.huecki.com/animation/agent-guide.md`
- OpenAPI 3.1: `https://isoani.huecki.com/animation/openapi.json`
- Interaktive API-Doku: `https://isoani.huecki.com/animation/docs`
- Browser-UI: `https://isoani.huecki.com/animation/ui/`
- Healthcheck: `https://isoani.huecki.com/animation/health`

## Vertrauens- und Kostenmodell

Alle `/v1/*`-Routen benötigen `Authorization: Bearer …`. Lies das Geheimnis ausschließlich aus `ANIMATION_API_TOKEN`; setze es nie in eine URL, Ausgabe, Logdatei, Dokumentation, Test-Fixture oder einen Screenshot. V1 besitzt genau einen Owner-Token. Er gewährt Zugriff auf alle Jobs und Artefakte und ist kein eingeschränkter Drittanbieter-Token. Teile ihn nur mit vertrauenswürdigen Coding-Agents, nie mit nicht vertrauenswürdigen Nutzern oder Browser-Code.

`/health`, `/ui/`, `/docs`, `/openapi.json`, `/agent-guide.md` und `/agent-prompt.txt` sind öffentlich. Jobdaten, Capabilities, Uploads, Reviews und Downloads sind privat.

Bezahlte Pipeline-Stufen und der automatische OpenRouter-Review besitzen getrennte Server-Policies. Ein Client kann sie nicht aktivieren. Prüfe immer zuerst:

```sh
BASE='https://isoani.huecki.com/animation'
: "${ANIMATION_API_TOKEN:?ANIMATION_API_TOKEN fehlt}"
curl --fail-with-body \
  -H "Authorization: Bearer $ANIMATION_API_TOKEN" \
  "$BASE/v1/capabilities"
```

Wenn `paid_policy.enabled` false ist, keine bezahlte Pipeline-Stufe absenden. Wenn `automatic_review.reviewer.available` false ist, keinen bezahlten Review vortäuschen: melde den `blocked_reason` klar. Aktiviere keine Server-Policy selbst.

## Zustandsmodell und sichere Orchestrierung

Es gibt keinen `create-animation`-Endpunkt und keinen garantierten Ein-Aufruf-Autopiloten. Orchestriere die tatsächlich benötigten Stufen. Jobzustände:

- `queued`, `running`: weiter den exakt zurückgegebenen Job beobachten.
- `needs_review`: anhalten; konkrete Artefaktrevision visuell/inhaltlich prüfen und nur deren aktuellen SHA-256 freigeben oder ablehnen.
- `needs_attention`: anhalten und Grund untersuchen. Keine bezahlte POST-Anfrage blind wiederholen.
- `completed`, `failed`: terminal.

Eine Stufen-POST liefert eine Stufen-ID, Job-ID und den Stufennamen. Bewahre diese IDs auf. Der öffentliche Statusabruf erfolgt über die exakte Job-ID; verifiziere dabei `latest_stage`, damit ein alter terminaler Zustand nicht mit der neu angeforderten Stufe verwechselt wird. Eine erfolgreiche HTTP-Antwort ist weder visuelle Freigabe noch Qualitätszertifikat.

## Getesteter kostenloser PNG-Flow

Die Uploadroute akzeptiert PNG bis 20 MiB, höchstens 4096 px je Seite und 16 Millionen Pixel. `auto_start:true` reiht ausschließlich `inspect_reference` ein und verursacht keinen Provider-Aufruf.

```sh
BASE='https://isoani.huecki.com/animation'
AUTH="Authorization: Bearer $ANIMATION_API_TOKEN"

CREATE_JSON=$(curl --fail-with-body \
  -H "$AUTH" \
  -F 'reference=@/absolute/path/reference.png;type=image/png' \
  -F 'options={"auto_start":true}' \
  "$BASE/v1/jobs")
JOB_ID=$(printf '%s' "$CREATE_JSON" | jq -er '.id')

while :; do
  STATUS=$(curl --fail-with-body -H "$AUTH" "$BASE/v1/jobs/$JOB_ID")
  STATE=$(printf '%s' "$STATUS" | jq -er '.state')
  STAGE=$(printf '%s' "$STATUS" | jq -r '.latest_stage // ""')
  test "$STAGE" = inspect_reference || { echo "unerwartete latest_stage: $STAGE" >&2; exit 1; }
  case "$STATE" in
    queued|running) sleep 1 ;;
    completed|needs_review) break ;;
    failed|needs_attention) printf '%s\n' "$STATUS" >&2; exit 1 ;;
    *) echo "unbekannter Zustand: $STATE" >&2; exit 1 ;;
  esac
done

curl --fail-with-body -H "$AUTH" \
  -o inspect-reference.json \
  "$BASE/v1/jobs/$JOB_ID/artifacts/inspect-reference.json"
curl --fail-with-body -H "$AUTH" \
  -o "animation-job-$JOB_ID.zip" \
  "$BASE/v1/jobs/$JOB_ID/download"
```

Die Inspektion ist numerisch. Prüfe vor Folgestufen die Artefakte aus `GET /v1/jobs/{job_id}`. Freigaben sind an `artifact`, exakten aktuellen `sha256` und dessen `revision` gebunden:

```sh
curl --fail-with-body -X POST -H "$AUTH" -H 'Content-Type: application/json' \
  --data '{"artifact":"reference.png","sha256":"AKTUELLER_64_HEX_SHA256","decision":"approve"}' \
  "$BASE/v1/jobs/$JOB_ID/reviews"
```

Ein veralteter Hash führt zu 409. Niemals automatisch freigeben.

## Pipeline-Stufen und Parameter

`POST /v1/jobs/{job_id}/stages` hat einen generischen `params`-Objekttyp, weil jede Stufe ein eigenes Schema besitzt. OpenAPI kann diesen freien Container nicht erschöpfend typisieren. Verwende ausschließlich die folgenden implementierten Schemas und die Beispiele in `docs/PIPELINE.md` des Dienstes; unbekannte Stufen oder unzulässige Werte werden abgelehnt.

Kostenlose Stufen:

- `inspect_reference`: `{"input":"reference.png"}`
- `extract_frames`: `{"input":"video-output.mp4","fps":12,"indices":[6,7,8],"output_prefix":"selected"}`. Manuelle Indizes sind nullbasiert; Ergebnis bleibt prüfpflichtig.
- `pack`: benötigt `inputs`, `image_id`, `action`, `direction`, `fps`, `loop`, `canvas`, `target_visible_height`, `target_root`, `anchor`, `gutter`, `columns`, `resample`; optional `cleanup`. Das vollständige Beispiel steht weiter unten.
- `mirror`: `{"atlas":"atlas.png","manifest":"atlas-manifest.json","target_direction":"nw","target_image_id":"keeper-walk-nw-derived"}`. Gespiegelte Requisiten wechseln die Hand-/Bildseite.
- `spatial_export`: `{"source":"video-output.mp4","selection_receipt":"automatic-review-result.json","selection_mode":"automatic_model_validated","export_preset":"derived-native-160-v1","removal_preset":"waldlicht-removal-v1","removal_recipe":"wavespeed-image-background-remover-output-v1"}`. Erlaubte Export-Presets sind 80 oder 160 px und werden unabhängig vom Master abgeleitet. Cache-Miss stoppt ohne Provider-Aufruf.

Bezahlte Pipeline-Stufen setzen `authorize_paid` und `budget_cap_usd` auf der äußeren Anfrage, niemals in `params`. Der Server muss zusätzlich `paid_policy.enabled=true` melden:

```json
{
  "stage": "generate_facing",
  "params": {
    "input": "reference.png",
    "preset": "waldlicht-facing-v1",
    "prompt": "Drehe die vollständige Figur nach Nordost.",
    "aspect_ratio": "1:1",
    "output_format": "png"
  },
  "authorize_paid": true,
  "budget_cap_usd": 0.011
}
```

`generate_facing` kostet laut aufgezeichnetem Schätzwert USD 0.011 pro Lauf. Nach Erfolg `facing-output.png` anhand seines aktuellen Hashs freigeben, bevor `generate_video` angefordert wird.

Der konfigurierbare MiniMax-Quellvideo-Preset heißt `minimax-h3-action-3s-480p-v1`:

```json
{
  "stage": "generate_video",
  "params": {
    "input": "facing-output.png",
    "preset": "minimax-h3-action-3s-480p-v1",
    "prompt": "Eine vollständige Aktion auf der Stelle, Figur vollständig im Bild.",
    "duration": 3,
    "resolution": "480p",
    "seed": -1
  },
  "authorize_paid": true,
  "budget_cap_usd": 0.06
}
```

Erlaubte Quellvideodauern: 3, 5, 8, 10 Sekunden. Erlaubte Quellauflösungen: 480p, 768p. Die Schätzung beträgt USD 0.02/Sekunde bei 480p und USD 0.04/Sekunde bei 768p. Diese Auswahl ist unabhängig von den Export-Frameoptionen 8/12/16/native und den Spritegrößen 80/160 px. Eine längere Quelle erzwingt weder mehr Exportframes noch eine längere zugeschnittene Aktion.

Weitere von `GET /v1/capabilities` gelieferte Video-Presets besitzen bewusst engere Schemas:

- `waldlicht-video-v1`: `input`, `preset`, nicht leerer `prompt`, optional `negative_prompt`, exakt `duration:5`, optional ganzzahliger `seed` (Standard `-1`); Schätzwert USD 0.10.
- `gemini-omni-video-3s-v1`: `input`, `preset`, nicht leerer `prompt`, exakt `duration:3`, `resolution:"360p"`, `aspect_ratio:"16:9"`; Schätzwert USD 0.09. Keine WAN-Felder wie `seed` oder `negative_prompt` senden.
- `minimax-h3-ne-source-5s-768p-v1`: `input`, `preset`, nicht leerer `prompt`, exakt `duration:5`, `resolution:"768p"`, optional ganzzahliger `seed`; Schätzwert USD 0.20.

Unbekannte Presets und capability-fremde Presets werden vor Providerzugriff abgelehnt. Preise sind aufgezeichnete Schätzwerte, keine behaupteten Ist-Kosten; `actual_charge_usd` bleibt unbekannt, sofern der Provider keinen autoritativen Wert liefert.

`remove_background`:

```json
{
  "stage": "remove_background",
  "params": {
    "inputs": ["selected-frame-0000.png"],
    "preset": "waldlicht-removal-v1"
  },
  "authorize_paid": true,
  "budget_cap_usd": 0.004
}
```

Schätzwert USD 0.004 je Eingabeframe; die gesamte Batch-Schätzung muss in die Obergrenze passen. Bei `needs_attention` oder unklarer Provider-Annahme nicht erneut posten. Bekannte Prediction-IDs gehören zur bestehenden Anfrage und werden vom Dienst sicher weiter abgefragt.

## Automatische Quellprüfung

Dies ist eine eigene Route, keine generische Stufe. Verwende den aktuellen Video-Hash und die aktuelle Revision:

```json
{
  "artifact": "video-output.mp4",
  "sha256": "AKTUELLER_64_HEX_SHA256",
  "revision": 1,
  "frame_policy": "8",
  "action": "walk",
  "authorize_paid_review": true,
  "budget_cap_usd": 0.05
}
```

POST an `/v1/jobs/{job_id}/automatic-review`. `frame_policy` ist `8`, `12`, `16` oder `native`; Standard ist `8`. `action` ist `walk` oder `punch`. Lokale harte Gates laufen zuerst und können kostenlos ablehnen. Der Reviewer ist nur nutzbar, wenn `automatic_review.reviewer.available=true`. Es gibt keinen Modell-Fallback und keinen blinden bezahlten Retry. Eine validierte Auswahl bindet Modell, Quelle, SHA-256, Revision, Kandidat, native Framegrenzen und Policy-Hash.

## Pack-Beispiel und Timing

```json
{
  "stage": "pack",
  "params": {
    "inputs": ["cutout-frame-0000.png", "cutout-frame-0001.png"],
    "image_id": "keeper-punch-ne",
    "action": "punch",
    "direction": "ne",
    "fps": 12,
    "loop": false,
    "canvas": {"width": 160, "height": 160},
    "target_visible_height": 116,
    "target_root": {"x": 80, "y": 144},
    "anchor": {"x": 0.5, "y": 0.9},
    "gutter": 2,
    "columns": 8,
    "resample": "nearest",
    "cleanup": {"recipe":"conservative-alpha-fringe-v1","minimum_visible_alpha":8}
  }
}
```

Für automatische kompakte Exporte stammen die Framezeiten aus den Abständen der ausgewählten nativen Quellframes bis zum Ende des geprüften, zugeschnittenen Intervalls. Die Summe der `frame_durations_seconds` erhält die getrimmte Aktionsdauer; sie ist nicht automatisch gleich der gesamten Quellvideolänge. Consumer sollen vorhandene per-Frame-Dauern bevorzugen. Bei `loop:false` nach der letzten Dauer auf dem letzten Frame stoppen; nicht heimlich loopen, ping-pongen oder Frames duplizieren. Ein wiederholt abgespieltes Vorschauvideo ändert diese Semantik nicht.

## Artefakte, ZIP und Provenienz

Nur im Job registrierte sichere Basenames sind über `/artifacts/{name}` und im ZIP verfügbar. Absolute Pfade, `..`, Symlinks, beliebige Dateisystempfade, beliebige Client-URLs, Datenbank-/Quellcode-/Secret-Dateien und nicht registrierte Dateien sind ausgeschlossen. Der Download-Medientyp ist allgemein; validiere Inhalt, Hash und Manifest selbst.

`animation-pipeline-atlas-v1` ist das neutrale Atlasformat. Prüfe Manifest-Schema, Atlas-SHA-256, Frame-Rechtecke, Quell- und normalisierte Frame-Hashes, Anker, Timing, `loop`, Modell/Preset/Revision, Provider-/Prediction-ID und Ableitungskennzeichnungen. `completed` bedeutet nur technisch abgeschlossen; `visual_quality_certified` kann weiterhin false sein.

## Fehlerbehandlung

- 401: Token fehlt oder ist falsch.
- 403: bezahlte Stufe durch Server-Policy gesperrt.
- 409: Freigabe fehlt oder Hash/Revision ist veraltet.
- 413: Request, Upload oder Bildabmessungen zu groß.
- 415: kein unterstütztes PNG beim Upload.
- 422: Schema, Parameter, Budget oder Auswahl ungültig.
- 503: Server besitzt keinen konfigurierten Owner-Token.

Zeige den serverseitigen `detail`-Text ohne Bearer-Wert. Wiederhole sichere GETs bei temporären Transportfehlern begrenzt. Wiederhole bezahlte POSTs bei Timeout/unklarer Annahme niemals automatisch; behandle sie als mögliche Kostenverbindlichkeit und stoppe.
