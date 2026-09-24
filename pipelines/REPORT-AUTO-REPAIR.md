# Automatische Terrain-Reparatur — echtes Ergebnis und Grenzen

## Ergebnis zuerst

**Arbeitsfähiger, persistenter Hintergrundlauf implementiert und über den echten Browser-/HTTP-Start ausgeführt. Noch kein erfolgreich reparierter Produktionskandidat.** Ein echter Muse-Edit wurde autonom eingereicht, gepollt und importiert. Die konservative automatische Registrierung stoppte mit `needs_attention`: größte Rahmen-Landmarkenabweichung **3.009814170035101 kanonische Pixel**, über der **vor dem Start festgeschriebenen 2.5px-Grenze**. Diese Grenze wurde nicht nachträglich gelockert. Kein manueller Kandidat wurde dem Lauf zwischen Stufen zugeschoben; kein weiterer bezahlter Reroll, kein erfundenes Review und keine Produktionsfreigabe.

Der neue Original-Output zeigt deutlich größere, ruhigere Gehwegplatten und weniger Straßensprenkel. Grasbüschel/-fransen bleiben sichtbar. Das ist eine Bildbeobachtung, **kein final-density Gate-PASS**. Der letzte Source ist 2000×1040, die unveränderte Zielprojektion 768×408. Die neue Ausgabe wurde nicht heimlich zu einem spielbaren Kandidaten gemacht.

## Echte IDs

- Run: `8e96cc6e6289256aead3f64d8ea86bfc132d7c47dee27898749bf43428cc1577`
- Iteration: `8e96cc6e6289256aead3f64d8ea86bfc132d7c47dee27898749bf43428cc1577:1`
- Generationjob/Quote: `eecf2eb1de215ae2157516d1fe4102ed079e29720e78ea534c22ab0f544be85f`
- WaveSpeed prediction: `012136556fb342a789b4cb931f1fe774`
- Latest, abgelehnter unregistrierter Source: `4d278b961c6f074b98ab7b2dd1475dba3d36b4e582ecd917b9eb7c3f0be4bd60`
- Best/weiterhin verwendbarer, aber NICHT freigegebener vorheriger Kandidat: `f3bdc310f809cf7a6b95015cc16af343e337a192e1865432ac530eb2b02fa96a`
- Beste/ursprüngliche Evaluation: `22af8b5b6da99ac99e9426e8f8d6a2609d773ef0590a6450768b5f16121e41e3`
- Unveränderter Stil: `d02eb595824e1632a68c50e3b201e7b27bada67f93b20bc1df0bbe60813419f5`
- Unverändertes Layout: `057137d51849cde09c0d12565f3232267e1b1dee239c14e8de64bb6b6c49ffb1`

**1 von maximal 15 autorisierten Reparaturiterationen ausgeführt, nicht 15.** Normaler neuer Request hat weiterhin Default 3. Frühstopp bei einer nicht sicher autonom registrierbaren Quelle entspricht der Autorisierung; Restbudget ist kein Grund, blind weiterzukaufen.

## Implementierung

- `auto_repair.py`: SQLite-State-Machine `plan → prepare → submit/submitting → poll → register → review → assess`; persistierte Iterationen, Ereignisse, Best/Latest und Stopgrund. Ein Start bindet die ganze begrenzte Ausführung. Ein Projektlauf unter dieser Autorisierung, kein Counter-Reset durch neue Start-IDs oder geänderte Caps.
- OS-Dateilock über jeden Arbeitsschritt verhindert parallel arbeitende Prozesse; In-Process-Registry verhindert doppelte Worker-Threads. Start dedupliziert in `BEGIN IMMEDIATE`. Serverneustart startet nur unterbrochene `running`-Läufe; terminale Sicherheitsstopps werden durch Resume **nicht** zu neuen Käufen.
- Frozen: ursprüngliche Evaluationsbindung inklusive Geometrie/Collision/Referenzen, Stil, Dichte, Gate-Dateihash, Autorisierung und Registrierungsgrenzen. Jeder Schritt prüft erneut. Stil-/Geometrieabsicht bleibt unverändert.
- `auto_adapter.py`: Klassifikation der echten Blocking Findings, präzise Prompt-/Material-/Avoid-/Referenzänderungen pro Versuch. Globaler reiner Translation/Skalierungsbefund nimmt den kostenlosen Registrierungsweg statt einer neuen Generation.
- Tatsächlicher Edit: **6 Bilder**: kanonischer Guide, unveränderte Style-Referenz, drei unveränderte Materialcrops, tatsächlich aktuell gerenderter Kandidat als ausdrücklich bezeichnetes Korrekturziel. Nur unterstützte Providerfelder `prompt`, `image_urls`, `output_format`; keine erfundene `negative_prompt`/Mask-/Strength-Steuerung. Aktueller Kandidat ist nicht Stilautorität.
- Gratis Auth/Metadaten vor Kauf; genaue hochgeladene Eingaben erneut gequotet; vorhandener zentraler Transaktionsledger reserviert vor dem POST. Vorabprüfung berücksichtigt zusätzlich das konservative volle Kontextreview. **Kein** Geld aus alten Holds freigegeben; keine neue Budgetquelle.
- Genau ein Generation-POST pro durable Intent. Nach Crash ohne Receipt keine neue Einreichung. Bekannte Predictions können ausschließlich gepollt/importiert werden. Review-Recovery kann den bereits vorhandenen unveränderten Receipt nach Crash fertig auswerten, ohne neuen POST. Keine reparierten/erfundenen Zitate.
- Registrierung: drei feste Vordergrundschwellen 60/80/100 gegen dunklen/transparenten Surround, beobachtete vier Extrema, ein positiver Skalar plus Translation, maximale Residuen/Schwellenstabilität dokumentiert. Keine Achsenverzerrung, kein Maskieren/Extrapolieren, kein nachträglicher Schwellenumbau. Ein passender Rahmen wäre noch kein Semantiknachweis; dann folgt das strikte Review.
- Best-Promotion nur bei kriteriumsweiser Nichtverschlechterung und mindestens einer Verbesserung, oder echtem komplett bestandenem Gate. Invalides Review, unbekannter Ausgang, gleiche Quelle, identischer Korrekturplan, Budget/Cap oder zweimal ausbleibende Kriteriumsverbesserung stoppen.
- UI: ein Startdialog, automatische Fortschrittsabfrage, persistierte Run-ID, eingefrorenes tatsächliches Maximum nach Reload, Resume/Cancel, ausdrücklich getrennte Best/Latest-Anzeige. Cancel stoppt zukünftige Stufen, löscht nie Jobs/Receipts/Holds.

## Verifikation — echt vs. Mock

**Echt:** Browserstart mit genau einer Bestätigung → Hintergrund-Generierung → Providerpoll → Originalimport → gemessener Registrierungsstopp, ohne Operatorübergabe. Frischer Prozessneustart bewahrt den terminalen Lauf; Resume kauft nichts. Browserstatus/Reload/Mobilbreite, Quelle/Best-Auswahl, tatsächlicher Best-ZIP-Download, Produktions-HTTP409 und Latest-Export-HTTP422 geprüft. Alle Zielrouten, Pflanzflächen-/Objekt-/Weltgrenzenblockaden und technische Straßentraversierung des erhaltenen Best-Kandidaten mit echten Tastatureingaben getestet.

**86 Python-Tests PASS.** Neue Transport-/Fault-Tests sind ausdrücklich MOCKS: Duplikatstart/concurrent workers, Thread-Deduplikation, 15-Cap über Resume/Neuerzeugung, Crash vor/nach Receipt, Cancellation samt erhaltener Liability, erschöpftes Budget, stuck polling, gleiche Quelle/Stagnation, invalides Review/keine Regression-Promotion und kostenloser globaler Transformweg. Bestehende Tests prüfen reale Hash-/Revision-/Referenzdrift, gemeinsame Budgettransaktionen und jedes FAIL/UNCERTAIN-Gatekriterium. Bibliothekswarnungen: Starlette/httpx-Testclient und FastAPI `on_event`-Deprecations; keine Testfehler.

Browserregressionen PASS: Layout (alle drei Beispiele), technische Kandidatenfixtures auf isoliertem Nullbudgetserver, urbaner echter Best-Kandidat/Navigation, strikter Stil-/Gateeditor, echter alter Waldpilot und neuer Auto-Status. Sie kaufen keine neuen Bilder/Reviews.

**Nicht live bewiesen:** erfolgreich registrierter neuer Kandidat → neues finales bezahltes Review → zweiter autonomer Korrekturversuch. Dieser Pfad ist implementiert und mit Mocks geprüft, aber der echte Lauf stoppte vorher. Kein neuer brauchbarer Gameplay-After-Screenshot möglich. Das frische Gameplaybild zeigt daher ausdrücklich das unveränderte Best. Die Vorher/Nachher-Tafel kennzeichnet rechts eine FAILED-FIT-DIAGNOSE, nicht Gameplay oder einen an den Lauf übergebenen Kandidaten. Endgültige Astra-Hauptsession-/Nutzerabnahme bleibt offen.

## Kosten — keine Reset-/Freigabetricks

- Vorher konservativ gehalten: **USD3.206128**.
- Ein neuer echter Edit: exakte Providerquote/zusätzlicher Hold **USD0.011**; Quote ist keine Abrechnungsquittung.
- Nachher konservativ gehalten: **USD3.217128**, davon Generation **USD0.033**, Reviews **USD3.184128**.
- Noch konservativ verfügbar unter USD10: **USD6.782872**.
- In den vorhandenen Reviewreceipts tatsächlich gemeldete Usage zusammen **USD0.02717625**; ist in Holds enthalten, NICHT zusätzlich darauf rechnen.
- Historischer Review `paid-pilot-01`: **USD0.794112** weiterhin ohne Receipt konservativ gehalten. Nichts willkürlich gestrichen.
- Kein neuer bezahlter Review: unsichere Registrierung war der frühe Stop. Deshalb wurde keine engere Tokenreservierung/Settlementlogik benötigt oder vorgetäuscht.
- Generationcap war für diesen Lauf explizit von 2 auf 17 (2 Originale + 15 Repairs) geöffnet. Nach seinem terminalen Stopp wieder auf tatsächlich verbrauchte **3/3** geschlossen; Reviewer wieder deaktiviert. USD10, alte Holds und Run-Maximum15 bleiben unverändert. Neue direkte Käufe sind nach Neustart damit blockiert.

## Belege / genaue Dateien

Alle Pfade relativ zu `/root/services/layout-terrain-pipeline`:

- `evidence/auto-repair/run-final.json`: vollständiger Run, jeder Plan/Prompt, die gemessenen Registrierungsfits und Stopgrund.
- `evidence/auto-repair/verification.json`: Kostenreadback, IDs, Request-/Receipt-/Sourcehashes und ZIP-Prüfung.
- `evidence/auto-repair/free-preflight.json`: echte kostenlose Modellmetadaten/Authpfad vor dem Kauf.
- `evidence/auto-repair/browser/phase-*.png`, `running.png`, `final-status.png`: tatsächlich laufende UI-Stufen.
- `evidence/auto-repair/verification/reload-persisted.png`, `mobile-status.png`, `browser-report.json`: frische Reload-/UI-Verifikation.
- `evidence/auto-repair/navigation/canvas-native.png`: echter Gameplaymaßstab 768×408, 48×24 Tiles, DPR1/CSS1:1.
- `evidence/auto-repair/before-after-diagnostic.png`: Before vs. fehlgeschlagene Fitdiagnose (KEIN spielbares After).
- `evidence/auto-repair/verification/latest-original.png`: tatsächliches neues 2000×1040 Provideroriginal.
- `evidence/auto-repair/verification/diagnostic-candidate-f3bdc310f809-d1.zip`: exakt im Browser heruntergeladener **Best**, 57 Mitglieder; CRC, alle Checksums, Layout und direkter Original-Pixelreplay bestanden. SHA256 `160071fcc5c05e3e683773759ef4dc02df8af97a92afe0952ca426776c85a876`.
- Request SHA256 `c2a6545dcc82c020311b228f596163d8edfff211ff4630e349d79035331d8ebb`.
- Durable Prediction-Binding-Receipt SHA256 `23c1695d91a308b66188630b80c21de15ef97a6c70188a493f8c869ff19f6fea`; dieser bestehende Generation-Receiptvertrag enthält Job/Quote/Requesthash/Prediction-ID, nicht den kompletten HTTP-Responsebody.
- Echte exakte Requests in `data/generation.sqlite3`, Receipt `data/eecf2eb1de215ae2157516d1fe4102ed079e29720e78ea534c22ab0f544be85f.receipt.json`, unveränderte Uploadbytes in `data/generation-sources/`; signierte temporäre Providerlinks bleiben serverseitig.

## Neustart / sicher prüfen

```sh
cd /root/services/layout-terrain-pipeline
python3 -m uvicorn app:app --host 127.0.0.1 --port 59649
# separat, KEINE bezahlten Aufrufe:
python3 -m pytest tests -q
BASE_URL=http://127.0.0.1:59649 node tests/auto-browser.mjs
python3 tools/verify_auto_repair.py
curl http://127.0.0.1:59649/api/auto-repair/8e96cc6e6289256aead3f64d8ea86bfc132d7c47dee27898749bf43428cc1577
```

Worker-Prozesse aus der Delegation enden ggf. bei deren Rückgabe: Parent muss selbst neu starten. **`tools/live_auto_run.mjs` ist ein einmaliger autorisierter Kaufharness, KEINE Regression.** Terminale Stopps nicht durch Datenbankänderung/Counter-Reset/erneute Anmeldung umgehen. Ein weiterer Entwicklungsauftrag müsste den Registrierungsblocker fachlich lösen und seine neue Befugnis explizit dokumentieren; bestehende Qualitätsgrenzen nicht heimlich passend machen.

Keine öffentliche Bereitstellung, keine Animation-/Spieländerungen.
