# Extern steuerbarer Stil + striktes Produktionsgate

## Ergebnis

Implementiert und lokal ausgeführt in `/root/services/layout-terrain-pipeline`. **75 Python-Tests bestehen** (Baseline 45), echte Browser-Workflows und tatsächlicher Diagnose-ZIP-Download verifiziert. Keine neue Terrain-Generierung gekauft. Unveränderte Urban-Geometrie, Originaldatei und Kandidaten-ID; historische Generierungs-/Reviewdatensätze nicht umgeschrieben. **Produktionsausgabe des Urban-Kandidaten bleibt serverseitig gesperrt. Finale visuelle Hauptsession-/Nutzerabnahme bleibt offen.**

- Strikte versionierte Style-Spec mit Prompt, begrenzter avoid-Liste, Materialdefinitionen, Gesamtstil-/Materialrollen und validierten Crops samt Parent-/Inputhashes.
- Neue unveränderliche Stilversionen, editierbare benannte Preset-Zeiger im bestehenden SQLite statt dupliziertem Store; Quote/Request/neue Kandidaten/Export übernehmen Bindungen.
- UI-JSON-Editor, Presetbearbeitung, Quote-/Reviewinvalidierung ohne Geometrieänderung. API/OpenAPI und [STYLE_API.md](STYLE_API.md) mit tatsächlichen IDs/Requests.
- Vier getrennte Kriterien mit `pass/fail/uncertain`, konkreten sichtbaren Beobachtungen und überprüften Evidenzzitaten. Fail-closed gegen fehlende/veraltete Inputs, andere Dichte/Stil/Layout/Quelle/Ausgabe, Request-/Metadata-/Receipt-Drift, lokale Blocking Findings.
- Diagnose bleibt erlaubt und klar als `diagnostic`/`X-Production-Approved:false` beschriftet. Produktionsdownload verlangt exakte aktuelle Evaluation und vollständiges Gate; HTTP409 bei Sperre.
- Konfigurierbarer OpenRouter-JSON-Vision-Adapter, kostenlose Auth-/Live-Capabilityprüfung vor bezahltem POST, exakte Inputs, echte Usage, atomarer Attempt-Lock, keine blinden Retries, gemeinsames Budget.
- Optionaler dauerhafter Korrekturworkflow, Standard AUS: explizites Opt-in, 1–3 Schritte zusätzlich zum globalen Versuchslimit, strukturierte Findings, unverändertes Layout/Stil, No-op-/Ambiguitäts-/Budget-/Cap-Sperren. Jede bezahlte Stufe separat bestätigt; kein unbeaufsichtigter Autoloop.

## Genau EIN tatsächliches neues Review

Modell angefordert und geliefert: **`google/gemini-3.8-flash`**. Response-ID `gen-1790019330-n83driy7mBlX28Zu2FF5`. Freier `/auth/key`-Check HTTP200 und Livekatalog/Capability-/Preissichtung vor dem bezahlten Request. Kein Credentials-Fallback, keine Credentials in Browser/Artefakten. Nach dem einzelnen Review ist `data/reviewer-config.json` wieder `enabled:false`; API-Readback bestätigt dies. Kein weiterer bezahlter Test.

Tatsächliche Modellurteile, unverändert aus dem gespeicherten Receipt:

| Kriterium | Modell | Konkrete Beobachtung |
|---|---|---|
| Layouttreue | PASS | Vier rechteckige Pflanzzonen, diagonale Straße und Gehwegflächen entsprechen grundsätzlich dem Guide. |
| Materialien | FAIL | Kleine unregelmäßige, eng verfugte Polygon-/Flagstone-Pflasterstücke statt großer ruhiger warm-beiger rechteckiger Gehwegplatten. |
| Pixelstil | PASS | Modell sieht klare isometrische Pixelkonturen und zur Referenz passende Pixelschattierung. |
| Begehbare Freiräume | FAIL | Gezackte Gras-/Büschelkanten ragen über kanonische Pflanzrechtecke in die Gehweg-/Akteurfreiräume. |

Das Modell beurteilte den Asphalt als grundsätzlich passenden neutralen Schieferton mit dezenter Sprenkelung; Grün als grundsätzlich brauchbar, aber mit Randbüscheln. **Es hat nicht jede Kritik des Nutzers/Parents übernommen.** Insbesondere Pixelstil blieb PASS. Diese Aussage wurde nicht zu FAIL umgeschrieben. Worker-Eigenbetrachtung: der Kandidat liest sich weiterhin deutlich kleinteiliger/unruhiger als die großen ruhigen Referenzplatten; die Spezifikation verlangt mehr als bloß ähnlichen Farbton. Das ist getrennt vom echten Modellurteil, nicht finale Parent-/Nutzerabnahme.

Zusätzlicher harter Formfehler: Der Materialkriterienblock zitiert native finale Materialcrops und Referenzen, aber nicht explizit die verlangte `final`-ID. Das Gate weist daher **zusätzlich** `materials: missing final evidence citation` aus, statt Zitate nachträglich zu erfinden. Die vier realen Urteile und zwei strukturierten Korrekturfindings bleiben sichtbar. Kein kostenpflichtiger Retry zur Formatreparatur. Unabhängig davon sperren zwei echte FAILs und bestehende lokale Fringebefunde die Produktion.

### Unveränderliche Bindungen

- Layout: `057137d51849cde09c0d12565f3232267e1b1dee239c14e8de64bb6b6c49ffb1`
- Kandidat: `f3bdc310f809cf7a6b95015cc16af343e337a192e1865432ac530eb2b02fa96a`
- Original-SHA: `706474479cf17c3db5ec95175b45c183f6bb2bdfdde0bf9f9acde0b901309c2c`
- Finale Dichte1-PNG: `c8619f78c9a2c8356c7791d763400e884e537ee6e8d51616b7e2716b554df211`
- Stilversion: `d02eb595824e1632a68c50e3b201e7b27bada67f93b20bc1df0bbe60813419f5`
- Evaluation: `22af8b5b6da99ac99e9426e8f8d6a2609d773ef0590a6450768b5f16121e41e3`
- Preset: `urban-calm-warm`

Elf echte Bildinputs: exaktes 768×408-Endbild, Guide, Routen- und sichere-Zentren-Masken, neueste Nutzerreferenz vollständig, drei Materialreferenzcrops und drei native Endbild-Materialcrops. Bytehashes, Größen und Cropkoordinaten: `evidence/strict-style/evaluation-final-readback.json`. Alle Reviewinputs ohne Thumbnail/Resize übertragen. Stilreferenz ausschließlich Stil/Material; fehlende Fahrzeuge, Figuren, Bäume, Bänke oder Gebäude ausdrücklich nicht bewertet. Keine Browser-Screenshots als Modellprompt hochgeladen.

`evidence/strict-style/user-original.jpg`, `user-decoded.png`, `user-reference-lineage.json` erhalten die neueste Nutzer-JPEG und einmalig verlustlos als PNG kodierte identische dekodierte RGB-Pixel. Die PNG-Original-/Crop-Lineage steckt in der Style-Spec/ZIP; der JPEG-Konvertierungsnachweis und JPEG liegen separat im Evidenzverzeichnis. Eine kostenlose vorbereitete, vor dem Review korrigierte Crop-Rollenversion bleibt als historische Version erhalten; nur die oben genannte korrekte Version wurde bezahlt reviewed.

## Verifizierte Ausführung

- `python3 -m pytest tests -q` → **75 passed**, eine vorbestehende Starlette/httpx-DeprecationWarning; `evidence/strict-style/tests-final.txt`.
- RED→GREEN nachgewiesen für fehlende Style-Spec-/Reviewendpunkte, unbeachtet durchgelassenen Produktionsmodus, Spec-Bindung/Crops im bezahlten Mockrequest, separate Kriterien-Fails/Uncertain, fehlenden Revieweradapter, Einmalbestätigung/Boolean-Typ, Rollenanzahl, sekundären Source-Hash-Drift, Request-Hash-Drift, Soil-/Versionvalidierung und abgeschnittene UI-Urteile. Mocks klar bezeichnet, kein erfundenes Live-Ergebnis.
- `node --check static/workflows.js` und Python-Compileprüfung erfolgreich.
- `/openapi.json` strikte Schemas und echte Beispiele geprüft; Snapshot `evidence/strict-style/openapi.json`.
- `tests/style-browser.mjs`: echte Stileditierung → neue immutable Version → Preset speichern/readback → Originalpreset laden → gültige kostenlose Livequote → strikten vorhandenen Reviewstatus laden → echter Diagnosedownload → tatsächliche HTTP409-Produktionssperre. Geometrie unverändert, Mobile 390px ohne Horizontaloverflow, keine Pageerrors.
- `tests/urban-browser.mjs`, `tests/paid-browser.mjs`: bestehende Stadt-/Waldkandidaten, echte Navigation/Kollision und Downloads bestanden.
- `tests/browser.mjs`, `tests/candidate-browser.mjs`: drei alte Layoutworkflows und technischer Import/Quote/Download auf **isoliertem Nullbudget-Fixtureserver** bestanden, echte Projektpolicy unverändert.
- `python3 tools/verify_strict_style.py`: tatsächliches Browser-ZIP mit **57 Einträgen / 56 Checksums**, CRC, Originalbytes, direktem Original→Endbild-Pixelreplay, allen elf Reviewinputs, Stil-/Evaluationsbindung und Produktions-HTTP409 verifiziert.

### Sicht- und Downloadnachweise

Alle relativ zum Servicerepo:

- `evidence/strict-style/browser/style-editor.png`
- `evidence/strict-style/browser/strict-review.png` — alle vier Urteile ohne abgeschnittene Scrollfläche
- `evidence/strict-style/browser/production-blocked.png`
- `evidence/strict-style/browser/review-mobile.png`
- `evidence/strict-style/browser/actual-candidate.png`
- **`evidence/strict-style/browser/diagnostic-candidate-f3bdc310f809-d1.zip`**
- ZIP-SHA256: `160071fcc5c05e3e683773759ef4dc02df8af97a92afe0952ca426776c85a876`
- `evidence/strict-style/browser/browser-report.json`
- `evidence/strict-style/verification-final.json` und `verification-final.log`
- Regressionen: `evidence/strict-style/{urban-regression,forest-regression,layout-regression,candidate-regression}/`
- Originaler neuer Providerrequest/-receipt/-metadata/-inputbytes: `data/reviews/22af8b5b6da99ac99e9426e8f8d6a2609d773ef0590a6450768b5f16121e41e3/`

## Frische gemeinsame Abrechnung

Nach SQLite- und API-Readback, `evidence/strict-style/accounting-final.json`:

- Projektdeckel unverändert **USD10.00**.
- Vorherige konservative Reservierungen **USD2.404336** unverändert erhalten.
- Genau ein neuer Reviewhold **USD0.801792**, vollständiger Kontext + 4096 Outputtokens.
- Echte gemeldete Usage: **18 524 Prompt-, 910 Completion-, 19 434 Gesamttokens; USD0.0173055**. Dies ist in der konservativen Reservierung enthalten, wird nicht addiert.
- Insgesamt konservativ gehalten **USD3.206128**; verbleibender Rahmen unter Holds **USD6.793872**.
- Weiter **zwei Generationjobs**, nun **vier Reviewhaftungen**, einschließlich früherem HTTP401. Keine Liability freigegeben oder zurückgesetzt.
- Globales Generierungslimit **2/2 erschöpft**. Korrekturmechanik wurde ausschließlich gemockt getestet, nicht bezahlt aktiviert. Verbleibendes Geld hebt den Versuchscap nicht auf.

## Neustart und Reproduktion ohne Kauf

Child-Server enden bei Delegationsende; alte Parent-Port53047-Module sind wahrscheinlich veraltet. Parent bitte frisch starten:

```sh
cd /root/services/layout-terrain-pipeline
python3 -m uvicorn app:app --host 127.0.0.1 --port 59645
# separate Shell
curl -fsS http://127.0.0.1:59645/api/reviewer/config
curl -fsS http://127.0.0.1:59645/api/generation/status
python3 -m pytest tests -q
BASE_URL=http://127.0.0.1:59645 node tests/style-browser.mjs
python3 tools/verify_strict_style.py
```

Reviewer-Konfiguration aktuell `enabled:false`, Auto-Reparatur AUS. `strict_urban_review.py run` **nicht** erneut als Test ausführen; gespeicherten Review lesen. Weitere Reviews benötigen ausdrückliche neue Operatoraktivierung, keine automatische Wiederholung. Der bestehende Konfigurationsadapter wurde live nur mit Gemini3.8-flash ausgeführt; alternative Modelle sind capability-validiert austauschbar, nicht vergleichend bewertet.

## Geänderte Dateien / offene Grenzen

Neue Kernmodule: `style_specs.py`, `production_gate.py`, `evaluations.py`, `reviewer_provider.py`, `corrections.py`. Angepasst: `app.py`, `generation.py`, `generation_api.py`, `review.py`, `static/index.html`, `static/workflows.js`. Neue Tests: `test_style_gate.py`, `test_strict_review.py`, `test_corrections.py`, `style-browser.mjs`. Tools: `strict_urban_review.py`, `verify_strict_style.py`. Dokumente: `STYLE_API.md`, dieser Bericht, README/REPORT-Verweise; projektspezifische Reviewer-Konfiguration und neue unveränderliche Daten/Evidenzen.

Keine Git-Metadaten vorhanden, kein Commit behauptet. Statischer Scan fand keine Shell-/SQL-Injection-, eval/exec- oder Pickle-Ausführungsmuster. Keine fremden Services/Spiele, keine Public-Deployment-/nginx-/DNS-Änderungen. Keine unabhängige Code-Reviewer-Subdelegation ausgeführt; Parent-Code-/Visualreview bleibt ausdrücklich offen.

Grenzen: JSON-Editor statt grafischem Crop-Picker; Korrekturworkflow bewusst stufenweise API-bestätigt, kein autonomer Hintergrundloop; keine neue reale Korrekturgenerierung; native Dichte2 braucht eigenen visuellen Review; semantische Urteile bleiben modellabhängige Evidenz, kein mathematischer Stilbeweis. **Vollständige finale visuelle Nutzerabnahme nicht erteilt.**
