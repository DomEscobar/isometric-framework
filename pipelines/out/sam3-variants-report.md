# SAM3 Deco-Varianten - Ergebnis

**Gesamtausgaben:** 0.226 USD (Cap 0.20 USD / Run-Dir)

| Variante | Objekt | Status | Hinweis |
|---|---|---|---|
| simple | tree | PASS | Eichenartiger Laubbaum, sauber |
| simple | bush | PASS | Runder Busch |
| simple | house | PASS | Holzhuette inkl. Schornstein |
| simple | rock | PASS | Grauer Steinhaufen |
| village | oak | PASS | Laubbaum |
| village | pine | PASS | Nadelbaum (nach Candidate-Remap) |
| village | bush-a | PASS | Gruener Busch |
| village | bush-b | PASS | Bluehender Busch mit Rosa |
| village | house | PASS | Holzhuette mit Fensterlicht |
| village | well | PASS | Steinbrunnen mit Holzdach |
| village | crate | PASS | Holzkiste |
| village | boulder | PASS | Grauer Fels |
| grove | oak-a | PASS | Laubbaum |
| grove | oak-b | PASS | Laubbaum |
| grove | pine-a | PASS | Nadelbaum (manueller Punkt) |
| grove | pine-b | PASS | Nadelbaum |
| grove | bush-a | PASS | Busch (manueller Punkt+Text) |
| grove | bush-b | PASS | Busch (manueller Punkt+Text) |
| grove | stump | PASS | Baumstumpf |
| grove | boulder | PASS | Felsbrocken (manueller Punkt) |

## Ausgaben

- `simple`: 0.042 USD
- `village`: 0.072 USD
- `grove`: 0.112 USD
- `total`: 0.226 USD

## Erkenntnisse

- Text-SAM liefert oft Klassenmasken (alle Baeume zusammen).
- Resplit nur mit eigener Maske + Box um Grid-Fuss reicht nicht, wenn Muse Objekte verschiebt.
- Loesung: Unique Components aus allen Masken + AI-Zuordnung auf Labels; fehlende Instanzen per manuellem Punkt+Text-SAM.
- Kein stilles Zusammenlegen von Instanzen: Claim-Blanking + 1 Sprite pro Objekt-ID.

Contact Sheets: `out/sam3-deco-1/contact-sheet.jpg`, `out/sam3-village/contact-sheet.jpg`, `out/sam3-grove/contact-sheet.jpg`
