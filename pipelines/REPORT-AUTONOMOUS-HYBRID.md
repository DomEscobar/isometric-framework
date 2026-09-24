# Umsetzung: autonomer Hybrid-Terrain-Prototyp

## Ergebnis und Abnahmegrenze

**Ein eigenständiger begrenzter Service ist implementiert und läuft**, nicht nur ein Plan. UI/API **http://127.0.0.1:48765/**, separate aktivierte systemd-API und -Worker, beide PPID1. Kein Hermes-Prozess/Chat/Subagent im Runtimepfad. Keine Veröffentlichung, keine Spiel-/Animationsänderung. Die Legacy-Werkbank antwortet weiterhin.

**Die volle geplante autonome Liveabnahme ist NICHT abgeschlossen.** Keine neue bezahlte Generierung oder Modellbewertung wurde durchgeführt. Das vorhandene OpenRouter-Umgebungscredential liefert beim kostenlosen Auth-GET **HTTP401**; keine neue laufgebundene Hybrid-Budgetautorisierung vorhanden. Die jüngste bestehende Hybridfreigabe war genau ein bereits ausgeführter Materialbildversuch und erlaubt ausdrücklich keine Reviewer-Käufe. Sie wurde nicht wiederverwendet.

Implementiert:
- freie Beschreibung plus Style-only-Upload → echter direkter OpenRouter-Planneradapter mit strukturiertem JSON-Schema, expliziten unsupported/uncertainty-Feldern und Interpretation;
- materialunabhängige rechteckige Layouts4..28, Land/Wasser/Wege/Plätze/Plateaus/Treppen, Höhe0..64px/8px-Schritte,48×24-Kacheln, vorhandene statische64px-Figur;
- deterministischer Compiler: ganze stehende/gesweepte Actor-Footprints, Wasserverbot, kardinale explizite Treppen, Klippen, erforderliche Zielkonnektivität;
- kostenlose lokale editierbare Vorschau **nach kostenpflichtigem Planner**, optionaler expliziter Auto-Continue; Freeze von Layout/Config und separaten akzeptierten Guidebytes; neue HTTP-Läufe pinnen Runtime-/Compiler-/Rendererrevision;
- WaveSpeed Muse-Referenzeditadapter, automatische OpenRouter-Crop-Lokalisierung/Semantikentscheidung mit Bounds/Source-/Belegvalidierung, direkte Source-RGB-Komposition plus dokumentierter Face-Lighting-Faktor;
- getrennte native Sample-/Finalreview-Aufrufe, sieben fail-closed Kriterien, strukturierte begrenzte Bildkorrektur, identische Source/gleicher Befund/uncertain/ungültige Belege/Budget/Call-/Zeitcap stoppen;
- zentrale atomare Call-Intents und Holds in bestehender Generation-SQLite, phasenbezogene Deduplizierung, immutable Receipts, bekannte Receipt-Recovery ohne POST, Unknown hält Budget und blockiert neue Hybridkäufe;
- persistenter Worker, Fencing/Lease/Prozesslock, separates Cancel-Intent, Reload/Resume/Listen/Events, Best/Latest getrennt, Diagnoseexport und receiptgebundenes Produktionsgate;
- tatsächliche Offline-Navigation und exportierbarer Renderer: genaue Source-XY-Pixelprovenienz, Tiefe, Actorbytes, Checksums, byteidentischer diagnostischer ZIP-Rebuild.

## Tatsächlich ausgeführte Verifikation

- **`python3 tools/test_hybrid_isolated.py` →252 passed,160 warnings,179.23s.** Gesamte vorhandene Suite plus neue Tests in temporärer Quellkopie ohne Produktionsdaten. Warnings sind bestehende FastAPI/Starlette-Deprecations plus Pydantics Warnung zum Feldnamen `schema`; nicht verschwiegen. Log `evidence/autonomous-hybrid/tests-final.txt`.
- Neue RED→GREEN-Nachweise u.a. Compiler, Renderer, Store, central call intent, Kostenobergrenze, Crop-/Citation-Gate, API, Worker, deterministischer Source-Rebuild, Signed-URL-Ausfilterung aus Events, Laufzähler, Metadatenpreisdrift und Runtime-Drift. Zusätzliche Negative für parallele Starts, zwei Claims, stale leases, Cancel, Unknown/Receipt, Bildcaps3/15 über Reopen, Wasser-/breite Footprints und Klippen/Treppen.
- **Ausdrücklich gemockter vollständiger Providertransport:** echter Worker/Adapterpfad mit4 strukturierten Modellantworten und1 Bildreceipt aus Testtransport, retained echten Pixeln, beiden Reviewgates, tatsächlicher Headless-Navigation/Rebuild und Produktions-ZIP. Zweiter Mockfall prüft FAIL→Bildkorrektur→identische Source→ehrlicher Stopp vor weiteren Modellcalls. Kein Live-Modellurteil behauptet.
- **Echter UI/HTTP-REPLAY:** `EVIDENCE=evidence/autonomous-hybrid/browser-final node tests/hybrid-browser.mjs` bestanden, keine Browserfehler. Lokaler Referenzupload, neuer Auftrag, technische Vorschau, Reload, kostenloses Validieren, Layout akzeptieren/einfrieren, Ergebnisiframe, echter Browser-ZIP-Download, Produktions-HTTP409,390px-Layout ohne Dokumentüberlauf.
- **Echte Controls:** `node tests/hybrid-controls-browser.mjs` bestanden: UI-Abbruch, Reload und Resume behalten `cancelled`, null Holds. `evidence/autonomous-hybrid/cancel-proof.json`, `cancel-ui.png`.
- **Exakter Download:** `python3 tools/verify_hybrid_delivery.py` bestanden.27 hashgebundene ZIP-Dateien geprüft; extrahiertes HTML offline navigiert, **1.152 gerichtete Kardinalprüfungen**, **neun echte Tastaturschritte** zum Plateautarget, null Browserfehler. Aus extrahiertem Source neu gebaut: ZIP byteidentisch. Native Canvasaufnahme gegen unabhängige Source/Actor/Depth-Komposition: **0 abweichende Pixel**.
- Alle vorbestehenden Dateien aus dem Baseline-Inventar unverändert außer `data/generation.sqlite3` (erwartete additive Migration/neue Hybridläufe). **Sämtliche alten jobs/reviews/quotes-Recordhashes und Anzahlen unverändert.** Keine neue Hybrid-Callzeile. Details `evidence/autonomous-hybrid/verification-final.json`.

## Exakte finale Evidenz

Repositorybasis `/root/services/layout-terrain-pipeline/`.

Finaler Replaylauf: **`434efd8711c64002a412cfb6f5f1cfeb`**.
Status: `needs_attention`, ausdrücklich REPLAY, `production_approved=false`.

- `evidence/autonomous-hybrid/browser-final/layout-preview-desktop.png`
- `evidence/autonomous-hybrid/browser-final/layout-preview-native.png`
- `evidence/autonomous-hybrid/browser-final/replay-completed-desktop.png`
- `evidence/autonomous-hybrid/browser-final/mobile.png`
- `evidence/autonomous-hybrid/browser-final/browser-diagnostic.zip`
- `evidence/autonomous-hybrid/browser-final/extracted/browser-native.png`
- `evidence/autonomous-hybrid/browser-final/extracted/index.html`
- `evidence/autonomous-hybrid/browser-final/extracted/source/rebuild.py`
- `evidence/autonomous-hybrid/browser-final/run.json`
- `evidence/autonomous-hybrid/verification-final.json`
- `evidence/autonomous-hybrid/service-final.json`

ZIP-SHA256: `ae0f68128161a38c73bf1cda3a01b836b3fb8cc606d1d0a56ff21fcff9551021`.
Persistiertes Serviceartefakt: `data/hybrid/434efd8711c64002a412cfb6f5f1cfeb/candidate-0/`.
Frühere Entwicklungsreplays/evidence `browser/` bleiben separat; finale Abnahme hier verwendet **browser-final**.

Worker-Bildinspektion (gpt-6-astra, keine Hauptsession-/Nutzerabnahme): Native Figur und Plateau/Treppe sind lesbar, kein sichtbares Clipping am Ziel. Die historischen Materialien haben weiterhin wiederholte Gras-Sprenkel und starke regelmäßige Pflasterfugen. Die eingebettete native Szene ist auf schmalen Bildschirmen scrollbar, nicht still verkleinert. UI trennt jetzt neuen Entwurf links und gespeicherten Replaystatus rechts, zeigt eingefrorenes Bildlimit und bezeichnet den Download als NICHT freigegeben. Kein neuer Stil-PASS.

## Kosten-/Authentifizierungsbefund

Free WaveSpeed-Auth/Katalog/Schema/Quote erfolgreich: `meta/muse-image/edit`, **USD0,011**. Bestehende explizite Modell-ID `google/gemini-3.8-flash` im öffentlichen OpenRouter-Katalog mit Image+Text/structured_outputs validiert. **OpenRouter Auth HTTP401**; keine versteckte Übernahme eines Hermes-Poolcredentials.

Konservative Reserve je Modellaufruf mit vollständigem Modellcontext und8192 Outputtokens: **USD0,817152**. Erste komplette Kandidatenprüfung mit vier Modellcalls plus einem Bild benötigt **USD3,279608 neu ausdrücklich freigegebenen Laufrahmen** (nicht tatsächliche erwartete Rechnung, nicht Freigabe für diesen Bericht). Max3 ist ein Limit, kein Kaufziel. Preisänderungen stoppen vor neuer Reservierung.

Zentraler Vorher/Nachherstand unverändert:
-10 Bildjobs:119.000 MicroUSD Holds;
-6 historische Revieweinträge:4.787.712 MicroUSD Holds;
-gesamt **USD4,906712** unter unverändertem USD10-Projektdeckel;
-**0 neue bezahlte Hybridcalls,0 neue Authorizationdateien**.

Eine frische vollständige Liveabnahme erfordert zunächst gültiges Service-OpenRouter-Credential, dann konkrete neue Runbudgetfreigabe. Vorgehen/JSON in `HYBRID_SERVICE.md`. Eine freie Schema-/Authprüfung ist kein echter Planner-/Reviewnachweis.

## Offen gegenüber dem vollen Auftrag

1. **Keine echte frische Beschreibung→Provider→automatische Cropauswahl→Review-Liveabnahme**, kein echter Paid-Crash/Receipt-Prozessrestart und kein mehrere-Referenzen-Nachweis; Replay nutzt ausdrücklich historische **manuell** ausgewählte Crops. Das ist der wesentliche Abnahmeblocker.
2. **In der kostenlosen Nachimplementierung geschlossen:** eigene native kleine Materialtestgeographie vor Finalrender; maximal2 automatisch klassifizierte Source-/Binding-gebundene Sampling-/Offsetkorrekturen. Kein freier Review: neue Modellbewertungen zählen im unveränderten Budget-/Calllimit. Details und Evidenz unten.
3. Zellbasierte rechteckige Einhöhenwelt, keine beliebigen Polygon-/Subcell-Layouts/Brücken/Gebäude/Props. Replayquelle enthält kein Wasser; Wassergeometrie ist getestet, live generiertes Wassermaterial noch nicht.
4. **In der kostenlosen Nachimplementierung geschlossen:** Originalreferenzbytes plus normalisierte Reviewreferenz, beide Hashes, Samplepaket/Guides und Gatebelege im Produktions-ZIP. Tatsächlicher Browserdownload aus isoliertem Transportmock und byteidentischer Gesamt-Rebuild belegt. Vollständige Providerrequests bleiben bewusst serverseitig (exportiert sind Bindungshashes, keine Signed-URLs/Credentials). Keine echte Liveproduktionsabnahme.
5. Laufautorisierung wird bewusst serverseitig proRun provisioniert; die notwendige neue Betreiberfreigabe ist offen und nicht durch einen beliebigen Browserhash ersetzt. Kein Mehrbenutzer-Autorisierungsdienst/öffentlicher Betrieb.

Diese Grenzen sind nicht als erledigt markiert. Eine allgemeine vollautonome Terrainproduktion kann anhand dieser Lieferung noch nicht behauptet werden.

## Kostenlose Nachimplementierung: drei zuvor offene Kriterien geschlossen

Dieser Abschnitt ist neuer als die oben dokumentierte Erstlieferung. **Kein neuer Paid-Aufruf, kein Providerupload, kein erneuter OpenRouter-Authversuch und keine Credential-/Live-Autorisierungsänderung.** HTTP401 bleibt ein bekannter, in diesem Schritt nicht erneut angefragter Blocker. Temporäre Testautorisierungen gelten ausschließlich in isolierten Transportmocks, nicht im produktiven Ledger.

### Implementiert und ausgeführt

- Persistente Phase `sampling` vor dem Zielrender: eigene native 4–5 Zellen breite Testgeographie mit allen verwendeten Groundmaterialien, zwei Wandrichtungen und derselben 64px-Figur. Sampleguide und Sampleartefakte haben eigene Hashbindungen. Erst Sample-PASS erlaubt `assembling` der eingefrorenen Zielgeographie; Finalreview bleibt zwingend. REPLAY rendert ebenfalls eine echte separate Probe, behauptet aber keinen Review.
- Automatische Klassifikation: reine Scale/Repetition-FAILs → strukturierte lokale Sampling-/Offsetkorrektur; Sourcehash und bisheriger Bindinghash müssen stimmen. Keine Cropgrenzen-/Geometrieänderung, Integer1..512, maxFaktor2 je Schritt, Offset nur innerhalb des Crops. Maximal2 lokale Schritte pro gesamtem Lauf, deaktivierbar mit0; No-op/Zyklus/unsichere Belege stoppen. Material-/Stil-/Lightingbefunde → begrenzte Sourcekorrektur; Layout/Clearance stoppt. Neue immutable Sample-/Kandidatenidentitäten und Reviewrollen, Quellenpixelprovenienz bleibt exakt. Neue Reviews zählen im selben zentralen Call-/Budgetledger; lokale Korrektur kauft kein zusätzliches Bild.
- Produktionspaket: ursprüngliche Uploadbytes (`reference-original.image`) plus tatsächlich verwendetes Review-PNG, SHA256/Rolle/Pixelbindung, Samplepaket/Guides und bisherige vollständige Terrain-/Actor-/Depth-/XY-Dateien. Safe image types, Hashformat und einmal-decodierte RGB-Gleichheit werden geprüft. Falsche oder fehlende Originalreferenz wird abgewiesen; keine Signed-Provider-URLs oder Servicecredentials exportiert. Originalmetadaten werden als Teil der unveränderten Uploadbytes nicht entfernt.
- `source/rebuild.py` baut das Terrain neu und rekonstruiert das **gesamte** `production.zip` byteidentisch; der Worker führt diesen Test vor Erfolg aus. Das Offlinepaket reproduziert gespeicherte Gateevidenz, es erzeugt keinen neuen Modell-PASS. Originale diagnostische Archive und alte sealed Läufe bleiben unverändert.

### Finale ausgeführte Verifikation

```
HYBRID_MOCK_EVIDENCE=/root/services/layout-terrain-pipeline/evidence/hybrid-completion/mock-browser-delivery HYBRID_TEST_LOG=/root/services/layout-terrain-pipeline/evidence/hybrid-completion/tests-delivery.txt python3 tools/test_hybrid_isolated.py
BASE_URL=http://127.0.0.1:48765 EVIDENCE=evidence/hybrid-completion/replay-delivery node tests/hybrid-browser.mjs
EVIDENCE=evidence/hybrid-completion/replay-delivery HYBRID_VERIFICATION=evidence/hybrid-completion/verification-delivery.json python3 tools/verify_hybrid_delivery.py
node tools/hybrid_artifact_probe.mjs evidence/hybrid-completion/mock-browser-delivery/extracted
```

- **261 passed,162 warnings,226.89s.** Gesamte Suite isoliert; bestehende FastAPI/Starlette/Pydantic-Warnings plus zwei Uvicorn/WebSockets-Deprecations im echten temporären HTTP-Browsertest. RED→GREEN u.a. separate Probe, lokale Korrektur, ursprüngliche Referenz, Gesamt-Rebuildgate, breite Actor-Footprints bei Wasser, HTTP-Samplezugriff.
- Vollständiger Transportmock mit lokaler Korrektur: **1 Bild,1 lokaler Schritt,6 gesamte Calls** (5 strukturierte Modellcalls). Worker wird zwischen Phasen neu instanziiert. Echte UI per isoliertem Uvicornserver, Browserdownload, Reload, extrahiertes Offline-HTML (120 Kardinalchecks,5 Tastaturschritte) und Gesamt-ZIP-Rebuild. Weitere Negative: local-cap0, falscher Sourcehash, uncertain, gesamtes Callcap4, falsche Originalreferenz, fehlender Gesamt-Rebuildbeweis, verändertes Finale, REPLAY-Produktion409. Keine Mockentscheidung als Livequalität ausgegeben.
- Mock-Produktionsdownload: `evidence/hybrid-completion/mock-browser-delivery/browser-production.zip`; **SHA256 `4f8523b2d69e452d7ca4d9e26f45a3ccef04562908ef9cf4186c1db46b0107ff`**. `verification.json`, `browser-proof.json`, `mock-production-ui.png`, `sample-native.png`, `extracted/`, `rebuilt/` daneben.
- Echter produktiver **No-paid REPLAY**: **`c9e393fc412b4a53a409e2d90ca7e24d`**, `needs_attention`, keine Produktionsfreigabe. `evidence/hybrid-completion/replay-delivery/`: UI/Upload/Preview/Freeze/Reload/Mobile/ZIP erfolgreich, keine Browserfehler. Download28 checksumgebundene Dateien,1.152 Kardinalchecks,9 Tastaturschritte,0 native Pixelabweichungen, ZIP byteidentisch rebuildbar. SHA256 **`aaefefaf227b2218c211a5ae941b41dada49ff3a4506c14bb25c609208490061`**.
- `preservation-delivery.json`: **93 alte Hybriddateien und sämtliche vorherigen Hybrid-/Jobs-/Reviews-/Quoteszeilen unverändert**,0 Hybridpaidcalls.10 historische Bildjobs/119000 MicroUSD und6 Reviews/4787712 MicroUSD unverändert. Zwei zusätzliche kostenlose Replayläufe, keine neuen Holds.
- Nur `layout-terrain-hybrid-api.service` und `layout-terrain-hybrid-worker.service` neugestartet; anschließend HTTP200, beide active/running, Port127.0.0.1:48765 unverändert. Ein unmittelbarer erster Readiness-GET während des Starts war zu früh (connection refused); nach gestarteter API200 und komplette Browserabnahme bestanden.

Neue Module `hybrid_sampling.py`, `hybrid_reference.py`, `hybrid_package.py`; angepasst `hybrid_worker.py`, `hybrid_models.py`, `hybrid_artifact.py`, `hybrid_export.py`, `hybrid_api.py`, `static/hybrid.html`, Reviewschema, Hybridtests, Browserharness und evidenzpfadparametrisierte Test-/Verifikationswerkzeuge. README/Servicehandbuch aktualisiert. Keine Legacy-Pythonänderung.

**Qualitätsgrenze bleibt:** Worker-Bildinspektion (Astra-Subagent, nicht Hauptsession/Nutzerabnahme) sieht lesbare Figur, kleine erhöhte Testfläche und sichtbare Gras-Sprenkel/Wiederholung. Kein echter neuer Referenzstil-PASS, keine beliebige Croprettung, kein allgemeiner Stiltransfer. Gültige dedizierte Serviceauthentifizierung und neue ausdrückliche Runbudgetfreigabe sowie echte autonome Liveabnahme/mehrere Referenzen/Paid-Crashbeweise bleiben offen; hier wurden sie weder gekauft noch erfunden.

## Dateien und Betrieb

Neu: `hybrid_{api,worker,store,layout,models,render,artifact,export}.py`, `static/hybrid.html`, `static/hybrid-navigator.html`, `schemas/hybrid-*-v1.json`, `tests/test_hybrid_*.py`, `tests/hybrid-browser.mjs`, `tests/hybrid-controls-browser.mjs`, `tools/hybrid_artifact_probe.mjs`, `tools/test_hybrid_isolated.py`, `tools/verify_hybrid_delivery.py`, `tools/systemd/layout-terrain-hybrid-*.service`, `HYBRID_SERVICE.md`, dieser Bericht und neue isolierte Evidenz.
Geändert: README/PROJECT_CONTRACT/PLAN (kleine ausdrückliche Beschreibungs-Erweiterung), Legacy-HTML nur um lokalen Hybridlink ergänzt. Keine Legacy-Python-Module oder Paid-Policies verändert. Reusable skill `autonomous-hybrid-terrain-expectations` um tatsächliche Entry-Points und Dedupe/Guide/ZIP-/Cancel-Lektionen ergänzt.

Systemd: `layout-terrain-hybrid-api.service`, `layout-terrain-hybrid-worker.service`, jeweils **active/running/enabled**. Units installiert in `/etc/systemd/system/`; Credentials in0600-Datei außerhalb des Repositorys. Beide Prozesse PPID1; keine delegierten Hintergrundprozesse, die beim Ende dieses Workers verschwinden. Start-/Stop-/Testbefehle in `HYBRID_SERVICE.md`.
