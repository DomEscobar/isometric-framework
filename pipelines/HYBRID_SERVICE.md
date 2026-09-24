# Autonomer Hybrid-Terrain-Service — begrenzter Prototyp

## Neueste explizite Einmallauf-Freigabe

`HYBRID_SCOPED_AUTHORIZATION.md` supersedes the historical no-exception statement below for ONE exact new run only. `hybrid_liability_authorizations` records immutable acknowledgment of named unresolved liabilities, NOT billing settlement or completion receipts. Exact old call/request/hold bindings, new run/config, approval text, expiry, shared ceiling and lifetime call/image caps are checked transactionally at each new paid boundary. All holds remain. Any unlisted/new unknown outcome, drift, cancellation or stale fence blocks. No global bypass and no old identity retry. Historical auth failures/budget totals below are historical, not current status; current execution evidence is in `evidence/hybrid-scoped-attempt/`.

## Betrieb

Lokale UI/API: **http://127.0.0.1:48765/** · API-Schema `/docs`.
API und Worker sind getrennte aktivierte systemd-Dienste:

```
systemctl status layout-terrain-hybrid-api layout-terrain-hybrid-worker
systemctl restart layout-terrain-hybrid-api layout-terrain-hybrid-worker
```

Units: `tools/systemd/layout-terrain-hybrid-{api,worker}.service`, installiert unter `/etc/systemd/system/`. Direkter Start ohne systemd:

```
python3 -m uvicorn hybrid_api:create_app --factory --host 127.0.0.1 --port 48765
python3 hybrid_worker.py
```

`HYBRID_DATA` wählt das Datenverzeichnis; Standard ist das **bestehende `data/`**. Kein zweiter Ledger, keine Änderung alter Laufdatensätze oder globaler Paid-Policies. Import von `hybrid_api` initialisiert keine Anwendung/DB; die Factory tut dies ausdrücklich. Legacy-APIs bleiben unverändert.

Keine Hermes-Prozesse/-CLI/-Credential-Pools im Betrieb. Direkte HTTP-Aufrufe an OpenRouter und WaveSpeed. Ausgewählte Umgebungscredentials liegen für systemd in `/root/.config/layout-terrain-hybrid/environment` (0600); niemals in Downloads. `HYBRID_PLANNER_MODEL` und `HYBRID_REVIEWER_MODEL` überschreiben den expliziten bestehenden Reviewer-Modellnamen; kein stiller Modellfallback. Jede neue kostenpflichtige Modellstufe revalidiert Live-Auth, Fähigkeiten, Preise und Contextgrenzen; bekannte Receipts werden ohne erneuten POST wiederverwendet.

## Bedienung und API

1. Referenz lokal hochladen (`POST /api/hybrid/uploads`, `{base64_data}`), unveränderte Originalbytes plus einmal decodiertes PNG behalten. Das PNG ist `style_only`. Beide Upload-Hashes als `reference_sha256` und `reference_original_sha256` im Auftrag angeben; Originalformat/Hash und decodierte RGB-Gleichheit werden vor LIVE und Export geprüft.
2. Beschreibung, Rastermaße, Actor-Footprint, Laufbudget und Obergrenzen festlegen. Vorhandene statische **64px-Figur** bleibt erhalten; Kacheln48×24, native Darstellung.
3. `POST /api/hybrid-runs` mit neuem `Idempotency-Key`. LIVE benötigt `confirm_paid:true`, positives `budget_microusd`, Referenz und **zusätzlich eine neue serverseitige Laufautorisierung**. Wiederholung derselben Identität ist idempotent; andere Daten unter demselben Key werden abgewiesen.
4. Planner übersetzt Beschreibung+Referenz in strukturiertes `Plan`-JSON. Unterstützt werden rechteckige Raster4..28, Land/Wasser/Wege/Plätze/Plateaus/Treppen, eine Höhe jeXY. Höhen0..64 in8px; Höhenwechsel nur explizit kardinal8px an Treppen. Brücken/Gebäude/Props/gestapelte Flächen müssen als unsupported zurückgewiesen werden. Ungültiges/unsicheres Ergebnis stoppt, ohne Bild zu kaufen.
5. `layout_preview`: kostenloser lokaler Compiler/Renderer, aber der vorausgehende Planner ist **nicht kostenlos**. JSON bearbeiten, `POST .../{id}/preview` kostenlos prüfen. `POST .../{id}/accept-layout` friert validierte Geometrie einschließlich eigener neuer Guidebytes ein. Beschreibung neu planen: neuer Lauf mit neuer Freigabe; keine alte Freigabe übertragen. Optionales `auto_continue` gilt nur für den ausdrücklich konfigurierten Lauf.
6. Worker erstellt referenzgetriebenes orthographisches Materialbild über Muse, lässt OpenRouter tatsächliche Cropkoordinaten/Semantik bestimmen, validiert Bounds/Belege/Unsicherheit und rendert direkte Source-RGB-Pixel. Keine manuelle Cropauswahl im LIVE-Pfad. Die persistierte Stufe `sampling` baut zuerst eine eigene kleine 4–5 Zellen breite Materialtestgeographie mit allen verwendeten Materialien, Wandflächen und unveränderter Figur. Erst nach ihrem Sample-PASS wird die eingefrorene Zielszene gebaut und separat nativ bewertet. Sample-PASS ersetzt niemals das Finalgate.
7. Nur Scale/Repetition-FAILs werden als lokale Samplingkorrektur klassifiziert: strukturierter, Source- und Binding-hashgebundener Vorschlag, unveränderte Cropgrenzen, Integer-Sampling1..512/maxFaktor2 pro Schritt und begrenzter Crop-Offset. Default/max2 lokale Schritte pro Lauf (`max_local_corrections`,0 schaltet aus), eigene immutable Samples/Reviewrollen, No-op/Zyklus-Stopp. Jeder neue Review bleibt kostenpflichtig und zählt im selben Call-/Budgetledger. Klare Material-/Stil-/Lighting-FAILs können begrenzt neue Sourcebilder anfordern; Layout-/Clearancebefunde stoppen statt Geometrie still zu ändern. Uncertain, ungültige Belege, No-change, Budget-/Zeit-/Aufruflimit stoppen ehrlich. Best wird nur nach vollständigem Gate-PASS gesetzt; Latest bleibt separat. Keine automatische Nutzerabnahme.
8. Persistente Liste/Status/Events: `GET /api/hybrid-runs`, `GET .../{id}`, `GET .../{id}/events`. `POST .../resume` beansprucht keinen aktiven Worker; `POST .../cancel` speichert unabhängiges Abbruchsignal. Terminale Läufe werden nicht wieder geöffnet.
9. `GET .../{id}/download?mode=diagnostic|production`. Produktionsmodus prüft tatsächliche Request-/Receipt-/Input-/Outputbindungen beider Revieweraufrufe und Browser-/Rebuildbeweis; Diagnose bleibt deutlich ungeprüft.

## Frische Kostenfreigabe — nicht ausgeführt

Implementierungsauftrag ist keine Freigabe eines neuen Modellkaufs. Alte abgeschlossene Einmalfreigaben gelten nicht für einen neuen Hybridlauf. Der laufende Dienst besitzt **keine** neue Live-Laufautorisierung.

Nach einem ausdrücklich neu genehmigten Budget legt der Betreiber **einmalig** `data/hybrid-authorizations/<run-id>.json` an, gebunden an den vom Status gelieferten `config_sha256`:

```
{"config_sha256":"<exakter Hash des neuen Auftrags>",
 "budget_microusd":3279608,"max_images":3,"max_calls":12,
 "expires":<Unixzeit des ausdrücklich genehmigten Endes>}
```

Die Werte müssen exakt zu den gespeicherten Benutzerlimits passen. Danach Resume. Dies ist die noch erforderliche Betreiberfreigabe, kein versteckter automatischer Bypass und kein freies HTTP-Endpoint zum Erhöhen des Projektbudgets. Ein abgesicherter Mehrbenutzer-/Autorisierungsdienst ist NICHT enthalten.

Kostenbasis des tatsächlich abgefragten Katalogs: `google/gemini-3.8-flash`, konservativ vollständiger Context zum größeren Text/Bild-Tokenpreis plus8192 Ausgabetokens: **USD0,817152 Hold je Modellaufruf**. Muse `meta/muse-image/edit`: **USD0,011** Quote. Erste vollständige Kandidatenprüfung = Planner + Extraktion + Sample-Review + Final-Review + ein Bild: **USD3,279608 notwendiger konservativer Laufrahmen**, keine erwartete Rechnung. Default3 ist ein MAXIMUM, kein Versprechen dreier Versuche. Preise werden erneut geprüft; diese Rechnung autorisiert keinen Kauf.

Historische gemeinsame Holds: USD4,906712. Gemeinsamer Deckel USD10 einschließlich aller Althaftungen. Bildreserve prüft zusätzlich Headroom für Extraktion und beide Reviews. Jeder tatsächliche neue Call wird atomar in der existierenden Tabelle `reviews` als allgemeine Hybrid-Call-Verbindlichkeit gebucht; `hybrid_calls.role` unterscheidet Planner/Reviewer/Extraktion/Bild, `hybrid_runs.image_count` zählt Bilder. Kein doppeltes Buchen in `jobs`. Bestehende Legacy-Zähler/Policies werden nicht künstlich erhöht oder geöffnet. Holds werden nie geschätzt freigegeben.

**Aktueller Live-Blocker:** Das vorhandene OpenRouter-Umgebungscredential scheitert am kostenlosen Auth-Check. WaveSpeed-Auth/Schema/Quote funktionieren. OpenRouter-Modellmetadaten wurden separat aus dem öffentlichen Katalog geprüft. Zuerst ein gültiges dediziertes Service-Credential bereitstellen, dann frische Laufbudgetfreigabe; keinen Hermes-Pool stillschweigend als Runtimefallback verwenden.

## Dauerhaftigkeit/Sicherheitsgrenzen

Neue Migrationstabellen im vorhandenen `generation.sqlite3`: `hybrid_runs`, `hybrid_events`, `hybrid_calls`, `hybrid_migrations`. Atomare `BEGIN IMMEDIATE`-Claims, Fencingtoken und600s-Lease; Prozess-Flock über komplette lokale Stufen. Modelltimeout180s, Pollgrenze600s, Standardgesamtlauf1800s/max7200s. Default3/max15 Bilder nur gemäß neuem Run-Auth; max12/max64 gesamte Calls. Keine automatische Paid-Neuanalyse ungültiger JSON-Antworten. Lokales Rendern/Korrigieren kostet keinen Provideraufruf; maximal2 lokale Samplingkorrekturen pro Lauf. Die anschließende erneute Modellbewertung ist NICHT kostenlos und bleibt unter ursprünglichem Call-/Budgetlimit. UI zeigt Bild-/Call-/Localzähler.

Der exakte Request und Reserve werden in derselben Transaktion vor POST gespeichert. Receipt ist unveränderlich und bleibt auch nach Cancel/Fenceverlust aufzeichnungsfähig. Intent ohne Receipt blockiert weitere Hybridkäufe; kein Reroll. ProPhase+Run ist nur ein Request erlaubt, auch bei veränderter Prompt-/Bildreihenfolge. Bei Prozessabbruch wartet ein anderer Worker bis zum Leaseablauf, statt einen aktiven Claim zu stehlen.

## Verifikation / klare Grenzen

```
python3 tools/test_hybrid_isolated.py
BASE_URL=http://127.0.0.1:48765 EVIDENCE=evidence/<neuer-name> node tests/hybrid-browser.mjs
node tools/hybrid_artifact_probe.mjs <extrahiertes-diagnose-zip>
python3 <extrahiertes-diagnose-zip>/source/rebuild.py <neues-verzeichnis>
```

Nicht die gesamte Legacy-Suite direkt in der Produktionskopie starten: `app.py` initialisiert beim Import seine Default-DB. Der isolierte Runner kopiert Code plus erforderliche echte Read-only-Fixtures, nicht Live-Daten.

REPLAY lädt einen ausdrücklich bezeichneten historischen Layoutentwurf und echte erzeugte Sourcepixel mit historisch manuell ausgewählten Crops. Es demonstriert Worker/UI/Render/Export, **nicht Sprachübersetzung, automatische Cropentdeckung oder Live-Modellqualität**. Wasser ist im Geometrieschema unterstützt, aber die vorhandene Replay-Materialquelle enthält kein Wassermaterial; ein entsprechender Replayentwurf stoppt statt Material zu erfinden.

Begrenzungen gegenüber dem vollen Plan: Zellbasierte Rechtecke statt beliebiger Polygone; keine Gebäude/Props/Brücken. Lokale Korrekturen ändern ausschließlich Sampling/Offset innerhalb bereits akzeptierter Crops, keine semantische Neuzuordnung oder automatische Cropgrenzenrettung. Kein bewiesener allgemeiner Stiltransfer, keine frische autonome Liveabnahme, keine realen Paid-Crash-/Receipt-Restarttests. Quelle/XY/Face-Lighting sind reproduzierbar; das ist kein visueller PASS. Eigene kleine Probe, begrenzte lokale Korrektur und vollständiger Produktions-Rebuild sind jetzt transportgemockt bzw. offline geprüft; Details im Ergänzungsabschnitt des Berichts.

## Vollständiges reproduzierbares Produktionspaket

Enthält unveränderte Originalreferenzbytes (`reference-original.image`), normalisierte Reviewreferenz, beide Hashes/Style-only-Rolle, akzeptierten Guide, vollständige Sampleartefakte samt Sampleguide, Sourcepixel/XY/Depth/Figur, Finalszene, Gatebindungen und Offlinequellen. Keine Provider-Signed-URLs oder Servicecredentials; vollständige Providerrequests bleiben serverseitig, Request-/Receipthashes sind exportiert. Original-Uploadmetadaten bleiben als Teil der Originalbytes erhalten.

`python3 <extrahiertes-paket>/source/rebuild.py <neues-verzeichnis>` baut Terrain wirklich neu und rekonstruiert danach das ganze `production.zip` byteidentisch aus gebundenen Belegen. Offline-Rebuild erfindet keine neue Modellfreigabe; er reproduziert die gespeicherte. Worker prüft diesen Gesamt-Rebuild vor Erfolg. Alte sealed Runs bleiben unverändert; fehlende Originalbindungen werden nicht erfunden. Aktuelle Evidenz: `evidence/hybrid-completion/`, Mock-Browserbeweise ausdrücklich keine LIVE-Abnahme.
