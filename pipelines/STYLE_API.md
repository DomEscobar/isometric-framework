# Versionierter Stil und Produktionsgate — API-Vertrag

Diese Erweiterung ersetzt keine historischen Generierungsbehauptungen. Layouts/Kollisionen und Originalkandidaten bleiben unverändert. Der vorhandene Urban-Kandidat wird über eine **separate unveränderliche Evaluation** gegen eine neue Stilversion geprüft. Ein automatisches Gate ist keine finale Nutzerabnahme.

## Lokale Daten und Standards

- `data/generation.sqlite3`: bestehende Quotes/Jobs/Review-Reservierungen plus `style_specs`, `style_presets`, `evaluations`, `corrections`. **Kein zweites Budget.**
- Referenzen verwenden weiterhin `data/styles/{id}/source.png` und den integritätsgeprüften bestehenden Datensatz.
- Spezifikation: SHA-256 über kanonisches JSON mit aufgelöster Referenz-/Crop-Lineage. Alte Versionen unveränderlich. Ein Preset ist nur ein veränderbarer benannter Zeiger.
- Evaluation: SHA-256 über Kandidatdatensatz, Original, Layout, Guide, finale Dichte/PNG, Stildefinition, frühere lokale Prüfevidenz und alle Bildinputs. Kein rückwirkendes `style_spec_id` im alten Kandidatdatensatz.
- Jede HTTP-Mutation muss per GET readback geprüft werden. Fremde Schlüssel, ungültige Material-/Referenzrollen, leere/out-of-bounds Crops und Typkoercion werden abgelehnt.
- OpenAPI: `/openapi.json`; interaktive Schemas: `/docs`. Pydantic-Schemas enthalten die echten Request-Typen, keine UI-only Felder.

## Stildefinition

`POST /api/styles` bleibt `{ "png_base64": "<PNG bytes base64>", "role": "style_only" }`.
Das speichert einen referenzierbaren Original-PNG-Datensatz. Die **Verwendung** als Gesamtstil oder Materialcrop wird danach in der Stildefinition deklariert.

`POST /api/style-specs` → 201, `{id, spec, reference_lineage}`. Beispiel mit tatsächlich vorhandenem Referenzdatensatz:

```json
{
  "version": 1,
  "prompt": "Friendly coherent isometric pixel-art urban ground. Preserve canonical geometry, not reference arrangement.",
  "avoid": ["dense tiny uniform pavers", "cool speckled asphalt", "wild meadow grass"],
  "materials": {
    "sidewalk": {
      "prompt": "Large calm warm cream slabs with broad faces, sparse seams and precise curbs.",
      "reference_ids": ["ef8024f3b713242c25da8df0c70b13b19b7adaac34a534766b0e2a4c5edccc69"]
    }
  },
  "references": [
    {
      "reference_id": "ef8024f3b713242c25da8df0c70b13b19b7adaac34a534766b0e2a4c5edccc69",
      "role": "style_only", "material": null, "crop": null
    },
    {
      "reference_id": "ef8024f3b713242c25da8df0c70b13b19b7adaac34a534766b0e2a4c5edccc69",
      "role": "material_only", "material": "sidewalk", "crop": [264, 77, 53, 41]
    }
  ]
}
```

Grenzen: `version` exakt Integer 1; Haupt-/Materialprompt je 1–2000 Zeichen; `avoid` höchstens 24 Einträge mit je 1–160 Zeichen; maximal 8 Referenzverwendungen; Materialien exakt `grass,soil,path,water,street,sidewalk,planting`. `crop` = `[x,y,width,height]` in Originalpixeln, vollständig innerhalb des Originals, positive Ausdehnung. Crops sind verlustlose Ausschneidungen, keine Resizes. Jede Materialreferenz muss zum gleichen Material und `material_only` passen; unbenutzte Materialreferenzen werden abgelehnt. Mehrere Materialcrops dürfen dasselbe Original benutzen. Exakt doppelte Rollen/Crops werden abgelehnt. Mindestens eine `style_only`-Verwendung erforderlich. Referenzen sind **nie** Geometrieautorität.

Die vollständig tatsächlich verwendete Dreimaterial-Definition liegt unter `evidence/strict-style/style-spec-request.json`. Ihre unveränderliche Version ist:

`d02eb595824e1632a68c50e3b201e7b27bada67f93b20bc1df0bbe60813419f5`

```sh
BASE=http://127.0.0.1:59645
curl -fsS "$BASE/api/style-specs" -H 'Content-Type: application/json' \
  --data-binary @evidence/strict-style/style-spec-request.json
curl -fsS "$BASE/api/style-specs/d02eb595824e1632a68c50e3b201e7b27bada67f93b20bc1df0bbe60813419f5"
curl -fsS -X PUT "$BASE/api/style-presets/urban-calm-warm" -H 'Content-Type: application/json' \
  -d '{"style_spec_id":"d02eb595824e1632a68c50e3b201e7b27bada67f93b20bc1df0bbe60813419f5"}'
curl -fsS "$BASE/api/style-presets"
```

Preset-Namen: `[a-z][a-z0-9-]{0,47}`. Zum Editieren neue Spezifikation speichern, dann Preset auf die neue ID setzen. Alte ID bleibt lesbar und reproduzierbar. Presetnamen sind bewusst **nicht** die Quote-/Reviewautorität: immer die exakte Version wählen.

## Quote, Anfrage, Kandidat

```json
POST /api/generation/quote
{
  "revision": "057137d51849cde09c0d12565f3232267e1b1dee239c14e8de64bb6b6c49ffb1",
  "style_spec_id": "d02eb595824e1632a68c50e3b201e7b27bada67f93b20bc1df0bbe60813419f5"
}
```

Kostenlos: live Schema/Preis, keine Medienübertragung. Prompt enthält **die gesamte exakte Stildefinition**, einschließlich avoid und Materialdefinitionen. Bild 1 ist Guide, folgende Bilder entsprechen `reference_lineage` in deklarierter Reihenfolge; Crops werden wirklich als entsprechende Bildbytes übertragen. Quote bindet Stil-ID, aufgelöste Bildhashes und Prompt. Bei Bestätigung `{quote_id, revision, style_spec_id}` sind dieselben IDs Pflicht. Vermischung mit Legacy-`style_id`/`prompt` wird abgelehnt. Historische Legacy-Quotes bleiben unterstützt, aber liefern allein keine Produktionsfreigabe.

Nach Stiländerung muss der Client Quote und Evaluationsauswahl verwerfen; UI tut dies bereits bei Entwurfsänderungen. API bestätigt keine andere Stil-ID als die Quote. Alte unveränderliche Versionen bleiben explizit reproduzierbar. Ein Generierungsjob übernimmt die Stilbindung in `provider_origin`; Export enthält Spezifikation und alle Referenzbytes. **Aktuell ist die reale Generierung gesperrt: globaler Versuchscap 2/2 erschöpft.** Kein Test darf diese Policy zurücksetzen.

## Strikte Evaluation und Export

```json
POST /api/terrain/f3bdc310f809cf7a6b95015cc16af343e337a192e1865432ac530eb2b02fa96a/evaluations
{
  "style_spec_id": "d02eb595824e1632a68c50e3b201e7b27bada67f93b20bc1df0bbe60813419f5",
  "density": 1
}
```

Kostenlose, deduplizierte Bindung. `GET /api/evaluations/{id}` prüft aktuelle Quellen, Style-Lineage, Guide, finale Ausgabebytes, lokale Evidenz, gespeicherte Inputs, Request-/Metadatenhashes und Receipt erneut. Tatsächliche Urban-Evaluation:

`22af8b5b6da99ac99e9426e8f8d6a2609d773ef0590a6450768b5f16121e41e3`

Inputs: exaktes finales PNG in angeforderter Dichte, canonical Guide, Routen- und sichere-Zentren-Masken, tatsächliche Referenzbilder/-crops, native Materialausschnitte mit Parenthash und Cropkoordinaten. **Kein Thumbnail der finalen Ausgabe.** Materialcrops sind Ausschnitte der finalen Ausgabe, keine neue Art. Bekannte lokale Fringe-/Clearancebefunde bleiben blockierend. Metadataframe allein beweist keine Bildausrichtung.

Modellantwort-Schema:

```json
{
  "criteria": {
    "layout_fidelity": {"verdict":"uncertain","observations":[{"observation":"Concrete visible observation, at least twenty characters.","location":"top-right curb","evidence_ids":["final","guide"]}]},
    "materials": {"verdict":"uncertain","observations":[{"observation":"Concrete comparison to material reference.","location":"sidewalk center","evidence_ids":["final","reference-1"]}]},
    "pixel_style": {"verdict":"uncertain","observations":[{"observation":"Concrete cluster-scale comparison at final density.","location":"center","evidence_ids":["final","reference-0"]}]},
    "walkable_clearance": {"verdict":"uncertain","observations":[{"observation":"Concrete evidence around the actor footprint boundary.","location":"planting edge","evidence_ids":["final","guide","safe-centers"]}]}
  },
  "findings": [{"criterion":"materials","blocking":true,"observation":"Concrete visible mismatch, not a generic rating.","location":"sidewalk center","evidence_ids":["final","reference-1"],"correction":"Specific bounded visual correction preserving canonical geometry."}]
}
```

Das Beispiel ist **Schemaillustration, keine Modellantwort**. Alle vier Kriterien erforderlich; Werte ausschließlich `pass|fail|uncertain`; jeweils mindestens eine konkrete sichtbare Beobachtung samt Ort und existierenden Evidenz-IDs. Jeder Kriterienblock muss `final` zitieren, Layout/Clearance zusätzlich `guide`, Material/Pixelstil mindestens eine `reference-*`. Fehlende/ungültige Zitate sperren, löschen aber nicht die echte gespeicherte Modellentscheidung. Keine gewichtete Durchschnittsnote. Jeder Fail/Uncertain oder Blocking Finding verhindert PASS.

- `GET /api/terrain/{id}/download?revision=...&density=1&mode=diagnostic&style_spec_id=...&evaluation_id=...`: ungeprüfter Diagnoseexport, deutlich benannt, `X-Production-Approved: false`. Alte Aufrufe ohne `mode` bleiben diagnostic.
- `mode=production` benötigt exakte passende Evaluation **und** Stil-ID und Dichte plus vollständig bestandenes Gate; sonst HTTP409. Nicht nur ein deaktivierter UI-Button.
- Neue Dichte, Quelle, Layout, Stilversion oder lokale Befunde benötigen neue Evaluation; alte Bewertung wird nicht umgebunden.
- ZIP: finale PNG, unverändertes Original, kanonisches Layout/Masks, Spezifikation/Referenzen, separate Evaluation und exakte Reviewinputs, Provenienz und Checksums. Credentials und kurzlebige Provider-URLs bleiben serverseitig.

## Austauschbares Reviewmodell und sichere Kosten

`data/reviewer-config.json`, nur Operator, kein HTTP-Budget-/Credentialeditor:

```json
{"adapter":"openrouter-json-vision-v1","model":"google/gemini-3.8-flash","auth":"environment","auth_label":null,"enabled":false}
```

`OPENROUTER_API_KEY` nur serverseitig. Alternativ ausdrücklich `auth:"hermes_pool"` plus exakter freigegebener `auth_label`; keine automatische Credential-Fallbacksuche. Der Adapter unterstützt konfigurierte OpenRouter-Modelle nur, wenn der **Livekatalog** Text+Bild-Eingabe, Textausgabe sowie `response_format`, `temperature`, `max_tokens`, positive Preise und Kontextgrenze meldet. Ein Modelltausch ist Operator-Konfiguration plus Neustart, kein stiller Fallback. Nur Gemini3.8-flash wurde hier live ausgeführt.

`GET /api/reviewer/config` enthält keine Credentials. `POST /api/reviewer/preflight` führt **kostenlos zuerst Auth**, dann Live-Metadaten/Capabilityprüfung aus. `POST /api/evaluations/{id}/review` verlangt exakt `{ "confirm_paid": true }` und aktivierte Operator-Konfiguration. Es erfolgt nochmals Free Preflight, dann Shared-SQLite-Reservierung (voller Modellkontext-Eingangspreis + 4096 maximale Ausgabetokens) vor **einem** bezahlten POST. Atomarer Attempt-Lock, persistierter Request und Receipt, kein Retry bei unklarem Ausgang. Usage und tatsächlich gelieferte Modell-ID werden erhalten; Modellabweichung/trunkierte Antwort blockiert. Der ursprüngliche breite Legacy-Review bleibt als historische Evidenz erhalten.

## Optionale Korrektur, Standard AUS

`POST /api/corrections` mit `{evaluation_id, enabled:true, max_attempts:1}` erzeugt nur den dauerhaften Workflow. Standard `enabled:false` wird als fehlendes Opt-in abgelehnt. Maximal 1–3 Schritte, **zusätzlich** zum unveränderten globalen Generationcap und gemeinsamen Projektbudget, nie ein Zusatzbudget.

`POST /api/corrections/{id}/step` mit `{evaluation_id, confirm_paid:true}` nimmt ausschließlich die strukturierten Blocking Findings der gebundenen Evaluation als Korrekturauftrag. Gleiche Layout-/Stilautorität, neue Quote, bestehender einzelner Generationpfad. `GET /api/corrections/{id}` liefert durable Job-ID und Zustand. Anschließend nur den vorhandenen Generationjob `/resume` pollen/importieren; den neuen Kandidaten separat evaluieren. Erst dessen Review darf einen weiteren explizit bestätigten Schritt treiben. Identische Quelle, gleiche schon verarbeitete Evaluation, fehlende Findings oder vollständiger PASS sind No-op/Sperre. Unbekannte/ambige Ergebnisse werden niemals blind neu eingereicht; reservierte Haftung bleibt.

Dies ist ein **kontrollierter, schrittweiser Workflow**, kein unbeaufsichtigter Hintergrundagent. UI bereitet ihn optional vor; bezahlte Korrekturschritte verlangen API-Bestätigung. Der reale Pilot hat ihn nicht aktiviert und keine neue Generierung gekauft. Mocktests prüfen Cap/Budget/No-op/Ambiguität; sie sind keine Live-Korrekturevidenz.
