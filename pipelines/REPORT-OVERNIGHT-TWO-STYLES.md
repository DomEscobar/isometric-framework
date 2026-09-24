# Zwei neue Terrain-Stile — echter Overnight-Lauf

## Ergebnis

Die begrenzte Phase wurde ausgeführt, nicht nur vorbereitet: **zwei echte neue Muse-Generierungen auf derselben neuen Layoutrevision**, danach automatische Registrierung und – soweit sicher möglich – finales echtes Review. **Ein nutzbarer, technisch verifizierter Warm-Kandidat mit automatischem Produktionsgate-PASS; der Fantasy-Kandidat bleibt sicher gesperrt. Nicht beide Stile sind fertig.** Doms ästhetische Abnahme bleibt separat offen.

- **Warm / Cream–Mint:** automatisch registriert, maximales Residuum **0.9312501280px** unter der unveränderten 2.5px-Grenze. Echtes finales Gemini-3.8-Flash-Review: Layout, Materialien, Pixelstil und Freiräume jeweils PASS; applicable `final`-/`guide`-/Referenzzitate wurden vom bestehenden Gate akzeptiert. Tatsächlicher Browser-Produktionsdownload und direkter Source-Pixelreplay bestanden.
- **Fantasy / Cobble–Olive:** echte Quelle erhalten, maximale Eckabweichung **2.8620662442px > 2.5px**. Automatischer Registrierungsstopp. Kein finales Review gekauft, keine Warp-/Maskenreparatur, kein spielbarer After behauptet, kein Produktions-ZIP.
- **Alte Urban-Reparatur:** neue kostenlose Langkontur-/Holdout-Diagnose selbst ausgeführt und geprüft. Die Evidenz rechtfertigt **keinen** Ersatz des Produktionsschätzers und kein Wiederöffnen des alten terminalen Laufs.
- Genau **2 neue Images, 1 neues Review, 0 Repairs**. Warm braucht nach dem strikten Gate keine Reparatur. Fantasy hat keine sicher lokalisierte reine Materialkorrektur und keine gültige Finaldichte; ein weiterer Bildversuch wäre hier spekulativ. Deshalb kein Blindreroll und keine Ausschöpfung der maximal erlaubten vier neuen Images.

## Bilder zuerst

Alle folgenden Pfade relativ zu `/root/services/layout-terrain-pipeline`:

![Native Werkbank-Navigation, kein vollständiges Spiel](evidence/overnight-two-styles/browser/warm-gameplay-native.png)

- `evidence/overnight-two-styles/browser/warm-gameplay-native.png`: echter Canvas-Screenshot, **720×384**, logische Tiles **48×24**, DPR1, CSS1:1. Der helle Akteur ist ein technischer Testmarker, keine generierte Figur.
- `evidence/overnight-two-styles/before-after-native.png`: neuer kanonischer Guide vor Generation neben echtem registrierten Warm-Terrain, beide native Größe. Kein Vorher/Nachher des alten Urban-Laufs.
- `evidence/overnight-two-styles/warm/reference-vs-source.png`: Warm-Referenz neben tatsächlicher Providerquelle, ausdrücklich Quellenvergleich, nicht Gameplay.
- `evidence/overnight-two-styles/fantasy/reference-vs-source.png`: Fantasy-Referenz neben tatsächlicher unregistrierter Providerquelle, **NOT GAMEPLAY**.
- `evidence/overnight-two-styles/two-styles-source-comparison.png`: beide Originalquellen mit exakt demselben 3:1-NEAREST-Sampling. Diagnosevergleich, keine Registrierung des Fantasybilds.
- `evidence/overnight-two-styles/browser/warm-strict-gate.png`: vollständige lesbare echte vier Einzelurteile.
- `evidence/overnight-two-styles/registration-replay/overlay-native.png`: kostenlose alte Urban-Langkonturdiagnose, nicht registriert/nicht Gameplay.

### Eigene Astra-Bildsicht

Beide Benutzerbilder, Materialcrops, neuer Guide, Diagnoseoverlay und tatsächlicher Warm-Gameplay-Screenshot wurden in der Hauptsession mit eigenem Bildsehen geprüft. Keine zusätzliche externe Zweitmeinung gekauft. Warm zeigt ruhige helle Platten, mintgrünen Boden und vier ockerfarbene Bodenflächen; Wege bleiben lesbar. Die kleinen wiederholten Grasbüschel und Platten machen daraus noch keine fertige Spielszene. Der technische, isolierte Platz ist keine Reproduktion der Referenzstadt. Fantasy zeigt erdigere Pflastersteine, olivgrünes Gras und dunklere Umrisse, ist aber geometrisch nicht sicher freigegeben. Schönheit wurde nicht als Registrierungsbeweis benutzt.

Hashgebundene Hauptsessionnotizen: `evidence/overnight-two-styles/astra-visual-audit.json`. Kein Anspruch auf Doms Zustimmung; der automatische PASS ist nicht Nutzerabnahme.

## Neue gemeinsame Geometrie und Referenztreue

Neue Revision: `92d93124f60c421c96bcc4108b6bf7907438409ad112bf7000124bfbeeb4d9fb`.

Parameter: `width=14`, `height=14`, `seed=2026092101`, `kind=plaza`, `path=cross`, `trees=0`, `houses=0`, `actor_width=0.8`, `tile_width=48`, `density=1`, leerer Brief. Flaches Wegekreuz mit gut sichtbaren Gras-/Weg-/Bodenmaterialflächen, ohne Höhen, Gebäude, Brücken oder Objekte. Beide Generationen verwenden identische Guidebytes, Projektion, Maßstab und Kollision. Zweiter Seed `2026092102` ausschließlich kostenloser technischer Layouttest. Ohne Objektreservierungen variiert dieser Seed nicht die Grundform; er wird nicht als zweite kreative Layoutlösung ausgegeben.

Beide JPEGs sind exakt unter `{warm,fantasy}/reference-original.jpg` erhalten; PNG enthält dieselben einmal dekodierten RGB-Pixel, keine Wiederherstellung verlorener JPEG-Information:

| Referenz | JPEG SHA256 | PNG SHA256 |
|---|---|---|
| Warm | `5571307da9aec0cd9b5f896fadfe8dbc58eb939d9ba76aa42861b3f6c8232ab7` | `8f3d98c58057eb1f515b54c07a8c51016eea1f9c49e3e5f5eba3e5f579da9426` |
| Fantasy | `66e973c79ad7a0cc93e5b41aa8719a7647ec9a243b07d1c1bdb14257a3439d0c` | `b1f0eee92e2f87694d7e360c31b92c01e066a09d99c421ec35887c31e710495e` |

Materialcrops wurden vor Submission selbst angesehen. Unpassende Gras-/Soil-Crops wurden **nicht** eingereicht: Mintpflaster ist kein fotografischer Grasbeleg, Blattbüschel kein flacher Boden. Tatsächlich verwendet: voller STYLE-ONLY-PNG plus genau ein geeigneter Pflastercrop je Stil. Gras und Boden sind explizite passende Farb-/Materialinterpretationen in den immutable Specs, keine erfundenen Cropbeweise. Kein Asphalt erzwungen. Abgelehnte erste Cropboards bleiben als Diagnosen erhalten; `reference-review.json` benennt die Entscheidung.

Stilversionen:

- Warm: `e1c87ad072c43282f73c27cd8ee1abfc5b2e73b0bc9eed6c0d975f15a1d3c5c2`; Preset `overnight-warm`.
- Fantasy: `490f4fd4ceb0ed91e7e1666f6210a5e5401e198621b44b477e547dbce2066e27`; Preset `overnight-fantasy`.

`style-spec-request.json`, `style-spec.json`, `reference-lineage.json` pro Stil dokumentieren exakte Prompts, avoids, Materialzuordnung, Cropkoordinaten und Pixelgleichheit.

## Kostenlose Registrierungsdiagnose

Die vorhandenen `registration_diagnostic.py`, Tests und CLI wurden gelesen; die fertig vorhandenen Methoden-/Vergleichsartefakte wurden nicht überschrieben. Eigener CLI-Replay schreibt ausschließlich `evidence/overnight-two-styles/registration-replay/`. Der erste eigene CLI-Aufruf traf einen falschen Layoutdateipfad und schrieb keine Diagnose; der korrekte Wiederaufruf wurde erfolgreich ausgeführt.

Unabhängige lange Außenkonturen werden robust gefittet; mittlere Konturabschnitte sind vom Fit ausgeschlossen. Innenkonturen dienen nur als Holdouts. Ein positiver gemeinsamer Skalar plus Translation, keine Achsendehnung. Synthetische Negativtests prüfen u.a. Anisotropie, Ausreißer, verschobene Innenkanten, fehlende Evidenz und gehaltene Außenkonturen. Der bisherige Eckschätzer bleibt unverändert.

Am alten Source bleibt die Legacyabweichung **3.0098141700px**. Der robuste äußere Schnittpunktfit liefert etwa **2.3985222721px**, ist allein aber keine Freigabe: unabhängige lange Curb-Proxys haben p95 **3.1162464396px oben / 4.1647961417px unten**, Maximum unten **4.5081185273px**. Farbproxies können Fugen/Grasfransen missverstehen; diese Zahlen sind kein zertifiziertes Ground-Truth-Labelling. Sie liefern erst recht keinen unabhängigen Sicherheitsbeweis. Daher **UNCERTAIN, keine Produktionsintegration der neuen Messmethode**, keine Grenzlockerung.

Alter Run `8e96cc6e6289256aead3f64d8ea86bfc132d7c47dee27898749bf43428cc1577` wurde vor/nach der Phase vollständig verglichen: unverändert `needs_attention`, eine historische Iteration. Sein Best `f3bdc310f809cf7a6b95015cc16af343e337a192e1865432ac530eb2b02fa96a` wurde nicht ersetzt.

## Tatsächlicher autonomer Serviceweg

`overnight_batch.py` ergänzt eine separate dauerhafte Tabelle `overnight_batches` **in derselben generation.sqlite3**. Keine zweite Budgetquelle, kein Reset/Bypass der alten `auto_runs`-Sperre. Installation über `create_app`; vorhandene Generation-, Import-, Registrierungs- und Evaluationsservices werden verwendet.

Start bindet exakt zwei unterschiedliche autorisierte JPEG-Pixelreferenzen, dieselbe neue gültige Revision, Dichte, Stil-/Guide-/Layout-/Authorization-/Gate-/Registrierungshashes. Projektweit einmal gebunden; geänderte Neustarts werden abgelehnt. Die engere reale Implementierungsgrenze lautet **ein Initialbild je Stil, null Repairs**. Das ist kein allgemeiner bis-zu-vier-Bilder-Repairdienst. Freeze, Locks, Intent vor POST, Receipt-Recovery und Unbekanntheitsstopps schützen Budget und Lineage. Registration FAIL überspringt das Review. Ein Review FAIL/UNCERTAIN würde terminal stoppen, nicht heimlich repariert.

Batch: `7d3054b365677a9c6f8ef5617d8e10b91c1b6303e93d022b127289c2d4aec2d8`.

API:

- `POST /api/overnight-batch/start`: `{revision,style_spec_ids:[id1,id2],density:1,confirm_paid:true}`.
- `GET /api/overnight-batch/{id}`.
- `POST /api/overnight-batch/{id}/resume`.

Nach Prozessneustart ist Resume ausdrücklich; kein ungeprüfter automatischer neuer POST. Der terminale aktuelle Batch bleibt bei Resume/identischem Start byteinhaltlich unverändert und kauft nichts. `completed` bedeutet hier **beide Experimente terminal**, nicht beide Produktion PASS. `summary.json` setzt daher ehrlich `komplett:false`.

Vor echten Calls: aktuelle WaveSpeed-Felder/Schema, kostenlose Preisabfrage, echte Reviewer-Auth/Metadaten und Review-Headroom geprüft. Genau die unterstützten Felder `prompt`, `image_urls`, `output_format`, jeweils drei Bilder: Guide, voller Stil, Pflastercrop. Exakte hochgeladene Inputs vor dem einzigen Image-POST erneut gequotet und zentral reserviert. Kein MCP-/Direktkauf außerhalb des Ledgers. Eine echte gebuchte finale Reviewanfrage ist kein ungebuchter externer Astra-Audit.

## IDs und exportierte Nachweise

| | Warm | Fantasy |
|---|---|---|
| Job = Quote | `5365413b4717e654ff2c058c08e941ea8d1c3ae0d4867cbf92bb9427a98fe752` | `0c00ad0eb73f91d6fce9acb0a0133eee3b15c7926d1ee418071314a1a7f6fdfd` |
| Providerprediction | `23296cf7bf5747c1af5743275fff9389` | `97478eb9bf7a415cb23f33336f6ad43b` |
| Originalkandidat | `c778fc8470902bb809163c27b499eaf07a8a4cf090e1e3c7bb44230fe6baed40` | `cbdacea39ea772210861825804d6dec854268ce56b780de83c2611c9072254cc` |
| Registrierter Kandidat | `39825bb50932fcdee92483a142bfbf29645133209bd96b012a3f7a14c02925bd` | keiner |
| Evaluation | `9e4f015de9b90183c8485c4392eced94c37f03169605e21fb6781f8ac2b2b64c` | keine, bewusst nicht gekauft |

Beide Originalquellen **2160×1152**. Je Stil unter `evidence/overnight-two-styles/{warm,fantasy}/`: `iteration.json` mit Journal/Stopgrund; `quote.json`, `exact-quote.json`, `receipt.json`, `source.png`, `source-record.json`, `registration.json`, Requesthash/-Binding und lesbarer Request mit entfernten temporären Providerlinks. Exakter unveränderter Request verbleibt in `data/generation.sqlite3`; redigierte Kopie behauptet keinen Originalhash. Warm zusätzlich `evaluation.json`, `review-receipt.json`, `review-metadata.json`, `review-intent.json` und Review-Requestbinding; Originalrequest unter `data/reviews/<evaluation>/request.json`.

Tatsächlich im Browser heruntergeladene neue ZIPs:

- **Warm Produktion:** `evidence/overnight-two-styles/browser/production-candidate.zip`, 49 Mitglieder, SHA256 `36cfb24b28ace229308921d9cf9b18e87abe964d7cab20e193235ec329d9a762`.
- Warm Diagnose: `evidence/overnight-two-styles/browser/diagnostic-candidate-39825bb50932-d1.zip`, SHA256 `df84613483bb3606cacd3543ce4204e9fbcc1e216088af9ca8f08a6b20760bd1`.
- Gemeinsames Layout: `evidence/overnight-two-styles/browser/layout-92d93124f60c.zip`, SHA256 `824157464523fb2efda36490750123399d6f198be8b05971948b5b8f2428be35`.

ZIP-CRC und vollständige Checksumlisten geprüft. Direct-source-Replay exakt gleich `terrain.png`, Kollision bytegleich kanonischer Collision. Native Browserscreenshot: **0 abweichende Pixel außerhalb des separat gezeichneten technischen Akteurs**. Keine verschobene Kollision, keine Kettenresizes, keine Terrainmaske. Produktions-ZIP bedeutet bestehendes Servicegate bestanden, nicht Engineadapter oder vollständiges Spiel.

## Tests: wirklich ausgeführt, nicht als Live-Mocks verkauft

**117 pytest PASS**, 57 vorhandene Bibliotheks-Deprecation-Warnings, keine Testfehler. Log `evidence/overnight-two-styles/pytest-final.txt`. RED→GREEN-Belege für Batch, App-Installation und korrekte geschlossene Budgetanzeige unter `tdd-batch/`.

Neue Fehlerszenarien mit isolierten Mocks: fremde/gleiche Referenzen, Scope-/Policy-/Hashdrift, Duplicate/Concurrent workers, unbekannte Submit-/Reviewausgänge, Receipt-Recovery, keine Reviewkosten nach unsicherer Registrierung, Budget-Headroom, stop ohne Reroll. Mocks sind nicht die Beweise der echten beiden Provideraufrufe.

**Sieben Browserharnesses PASS:** Layout, Kandidatenfixtures, alter AutoRun, strikter Stil, Waldpilot, Urbanpilot und neuer Zwei-Stil-Harness. Nullbudgetfixtures ausschließlich separater temporärer Server, echte Projektpolicy niemals für Fixtures zurückgesetzt. **Neun tatsächliche ZIP-Downloads** vollständig CRC-/Checksum-/Collision-geprüft, alle Terrain-ZIPs zusätzlich Source-Pixelreplay: `all-zip-verification.json`.

Neuer echter Browsernachweis: alle drei Warm-Ziele per Tastatur, Weltgrenzenblock, integerpositionierter native Canvas, Stil/Evaluation laden, Diagnostik- und Produktionsdownload; Fantasy-Source anzeigen/erhalten, ungeeigneter Export HTTP422 und Produktion HTTP409, stale Warm-Dichte HTTP409, Mobile ohne horizontalen Überlauf, keine Pageerrors. Nach Abschluss direkte Generation/Review HTTP403; Terminal-Resume/Duplikatstart/bekannte Generation-Resume kaufen nichts.

## Budget und Abschaltung

Ein unveränderter zentraler **USD10**-Rahmen unter der neuen **EUR15 inklusive aller alten Holds**-Autorisierung:

- Vorher Held **USD3.217128**.
- Zwei Images, jeweils Quote/Hold **USD0.011**; keine Rechnungsbehauptung.
- Neues striktes Review Hold **USD0.801792**, tatsächlich gemeldete Usage **USD0.01323975**.
- Neu zusätzlich Held **USD0.823792**; nachher gesamt **USD4.040920**: Images **USD0.055**, Reviews **USD3.985920**.
- Alle bislang gemeldeten Review-Usagekosten zusammen **USD0.04041600**, bereits in Holds enthalten, niemals zusätzlich addiert.
- Alter unbekannter `paid-pilot-01`-Hold **USD0.794112** unverändert erhalten. Keine willkürliche Freigabe.
- Konservativ verbleibend unter USD10: **USD5.959080**. Geld ist kein Qualitätsbeweis und kein Anlass für Rerolls.

Gratis FX-Check: ECB-Suchresultat nennt für 21.09.2026 USD1.1490/EUR; die extrahierte Kalenderseite zeigt als jüngsten belegten Wert 15.09.2026 USD1.1539/EUR. Diese zeitliche Diskrepanz ist dokumentiert, kein garantierter Ausführungskurs behauptet. Beide liegen deutlich innerhalb der konservativen Reserve **EUR1.25 je USD plus EUR2.50 Gebührenpuffer**. Der gesamte USD10-Deckel entspricht damit höchstens EUR15 in dieser Reserveannahme. Details/Quelle: `fx-budget.json`.

Projektpolicy nach Ende `approved:false`, weiterhin `total_usd:10.00`, Cap5/5; Reviewer disabled. Frischer Loopbackprozess neu gestartet und Readbacks/HTTP403 geprüft. Historische fremde/stale Prozesse wurden nicht umkonfiguriert. Keine offenen neuen Calls, keine Credentials in Bericht/Browser.

## Selbst öffnen / sicher wieder prüfen

Lokale Werkbank: `http://127.0.0.1:59661/`, kein öffentliches Deployment. Bei Prozessende neu starten:

```sh
cd /root/services/layout-terrain-pipeline
python3 -m uvicorn app:app --host 127.0.0.1 --port 59661 --no-access-log
```

Zum Warm-Ergebnis: Formular exakt mit den oben genannten Layoutparametern erzeugen; gespeicherte registrierte Kandidaten-ID laden; Preset `overnight-warm` wählen und laden; „Aktuelle Evaluationsbindung / Reviewstatus laden“ ist kostenlos. 1:1-Ansicht und Pfeiltasten testen, Produktions-Export klicken. Die gespeicherten Exporte/Bilder sind ohne Server direkt nutzbar. Fantasy über seine Originalkandidaten-ID nur im Quellenvergleich ansehen; Ablehnung nicht umgehen.

Nur lesende/retained-result-Prüfungen:

```sh
python3 -m pytest tests -q
BASE_URL=http://127.0.0.1:59661 node tests/overnight-browser.mjs
python3 tools/collect_overnight.py
python3 tools/verify_overnight.py
python3 tools/verify_overnight_zips.py
```

Die historischen bezahlten Pilottools nicht als Regression starten. `setup_overnight_api.py` macht lokale Anlage/Gratispreflight, aber keinen Kauf; der Batchstart ist ausdrücklich ein bezahlter Workflow und im aktuellen abgeschlossenen Scope nicht erneut ausführbar.

Keine Spiele, kein Animation-Service, kein fremdes Hermes-Profil verändert; keine öffentlichen Deployments. Kodierung und eigener Astra-Audit über die bestehende Subscription, keine separaten Codinganbieter. Begrenzte Phase beendet, statt unsichere Geometrie zum PASS zu erklären.
