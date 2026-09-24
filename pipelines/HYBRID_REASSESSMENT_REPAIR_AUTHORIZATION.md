# Bounded image-to-image material repair after reassessment — ONE child run

Owner (Dom), Telegram 2026-09-22, explicit wish quoted verbatim:
„ich will das es jetzt funkruiniert und gut aussieht und das image to image immer
verwendet wird. auch bei merstufigem." (= it must work and look good; image-to-image
shall always be used, also for multi-level/stairs scenes.)

This authorizes EXACTLY ONE image-to-image material-board edit as a new immutable child
of sealed reassessment run `b9a94348e6404358b353d3b3c5fd5f24`, then automatic
re-extraction, sample scene (now with a FUNCTIONAL stair transition), sample review,
final render, final review and the production bundle.

## Harte Grenzen
- Genau EIN neues Bild (Amendment: max_images 3->4, max_calls 12->15, genau 4 Folge-Calls:
  image-2, extraction-2, review_sample-2, review_final-2). Keine stillen Cap-Erhöhungen.
- Der Edit folgt ausschließlich zitierten, handlungsrelevanten Review-Befunden
  (`review-material-actionable/1`): feinere Pflasterplatten (scale, crop-square).
  Rollenkonflikt-Befunde (Steigungen/Treppen aus flachem Stein verlangen) sind
  ausgeschlossen, Geometrie-Befunde bleiben renderer-seitig deferred. Zusätzlich die
  ausdrückliche Owner-Style-Directive: strukturierterer, aber weiterhin FLACHER
  face-on Stein für die Treppen-Textur (keine Steigungen/Treppenobjekte in der Quelle).
- Alle passenden Materialien (land/path/stairs/wall) werden explizit erhalten; jedes
  Material wird danach vollständig neu extrahiert und bewertet. Keine manuellen Crops.
- Originalurteile/Receipts aller Eltern bleiben unverändert; ein FAIL stoppt ehrlich.
- Budget: 3000000 microUSD Run-Rahmen; Projektdeckel USD20 GESAMT inkl. aller Holds
  (aktuell 12754880 microUSD reserviert). Jeder Call wird vorher zentral reserviert.
- Kein Blind-Retry, keine Freigabe unbekannter Altverpflichtungen, kein Deployment,
  keine Spiel-/Animationsänderungen, keine Secrets in Logs/UI/ZIP.
