# Complex multi-level terrain — ONE new live run (v2 after the v1 planner truncation)

Owner (Dom), Telegram 2026-09-22: „Ok jetzt mal komplexere terrain". Standing preferences:
image-to-image shall be used (also for multi-level/stairs scenes), short answers, it must
work and look good. V1 (`d275ba20…`) stopped honestly: the planner JSON truncated at the
historical 8192 default (`finish_reason: length`, 7861 reasoning tokens), no image bought.
Two known receipts were evidence-backed settled (actual billing, raw-hash bound; the 2
unknown legacy holds remain fully reserved). V2 uses the proven 32768/medium token policy
for planner, extraction AND review.

## Auftrag
Ein neuer Eigenlauf des Hybrid-Terrain-Services mit deutlich komplexerer Geometrie:
drei Höhenebenen (0/8/16), zwei echte Treppenübergänge, Wasser (kleiner See, nur auf
Ebene 0), geschwungene Dorfwege, ein gepflasterter Platz und ein erhöhtes Terrassenplateau.
Gleiche Stilreferenz und gleiche64px-Figur wie zuvor. Ablauf: Planner → Auto-Accept →
ein Material-Board-Edit (image-to-image, Muse) → Extraktion → Sample (mit funktionaler
Treppe) → Sample-Review → Final-Render → Final-Review → Produktionsbundle.

## Sampling-Repair-Nachtrag (laufend)
Der abschließende Local-Correction-Loop war in v3 mit max_local_corrections=0 hart
ausgeschaltet; das Final-Review scheiterte nur an `scale` und lieferte einen gültigen
hashgebundenen Sampling-Plan (Faktor 2, Crops unverändert). Autorisiert ist GENAU EIN
Child-Lauf dieses Planes: deterministische Neubemusterung, KEIN Bild, genau die zwei
Pflicht-Re-Reviews (max_calls geerbt+2, max_local_corrections genau1, followup 2).
Zuvor wurden zwei bekannte Planner-Receipts belegt abgerechnet (Roh-Billing-Hash
gebunden); die2 unbekannten Altverpflichtungen bleiben unberührt reserviert.

## Harte Grenzen
- max_images=1, max_calls=6, max_local_corrections=0 — kein Korrektur-Bild, kein Reroll.
  Ein FAIL stoppt ehrlich; caps werden nicht erhöht.
- Nachtrag Board-Varianten (Owner-Wahl „Beides: erst Board-Varianten, dann ein begrenzter
  Polish-Test"): GENAU EIN weiteres image-to-image Board-Edit auf Basis des bewährten
  source-0 der Produktion `bf0775b5…` — reichhaltigere, feinere flache Material-Swatches
  (alle7 Semantiken erhalten, keine Architektur in der Quelle), danach vollständige
  Neu-Extraktion + beide Pflicht-Reviews (4 Folge-Calls, max_images 1→2 genau einmal).
  Bekannte Receipts der Kette wurden belegt abgerechnet (9 Settlements, Roh-Hash gebunden).
- Token-Policy explizit: planner, extraction UND review jeweils 32768 max_tokens, reasoning
  medium (bewiesen; vermeidet den 8192-Length-Truncation-Bug, der v1 abgeschnitten hat).
- Budget: 3800000 microUSD Run-Rahmen; Projektdeckel USD 20 GESAMT inkl. aller Holds
  (aktuell effektiv 14539038 microUSD reserviert; nach voller Auslastung ~18.19M,
  Rest ~1.81M). Jeder Call wird vorher zentral reserviert; kein Blind-Retry.
- Die2 unbekannten Altverpflichtungen bleiben vollständig reserviert; die Anerkennung ist
  KEINE Abrechnung. Keine öffentliche Bereitstellung, keine Spiel-/Animationsänderungen,
  keine Secrets. Keine manuellen Crops/Kandidaten im Erfolgspfad.
