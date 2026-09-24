# Local layout / terrain milestone

## Neueste Implementierungserweiterung: autonomer Hybrid-Service

Der aktuelle Nutzerauftrag nach „ok umsetzten“ autorisiert eigenständige lokale API/UI und systemd-Worker einschließlich freier Beschreibung→validiertem Layout, Höhen/Treppen, referenzgetriebenen Materialadaptern, automatischen Crop-/Reviewverträgen und begrenzter Korrektur. Er ersetzt entsprechende historische Implementierungsausschlüsse für diese neue Route, nicht für alte unveränderliche Läufe. Keine öffentliche Veröffentlichung/Spiel-/Animationänderung. Gemeinsamer USD10-Deckel/Althaftungen bleiben. Es wurde **keine neue Paid-Laufautorisierung** angenommen; Runtime benötigt neue konkrete Freigabe. Voller Plan vs begrenzter implementierter Prototyp: `HYBRID_SERVICE.md`, `REPORT-AUTONOMOUS-HYBRID.md`.


Approved implementation scope: the delegated user request authorizes this first standalone local milestone. This file records that scope, not a new game/art-production contract.

- LT-01: Standalone workspace `/root/services/layout-terrain-pipeline`; local HTTP UI/API only.
- LT-02: One flat, bounded 2:1 semantic map. Dimensions 10–28 cells per axis; logical tiles 32×16, 48×24, 64×32; texture density 1 or 2 independently.
- LT-03: Deterministic seeds, explicit parameters, exact constrained German clauses. Reject unsupported clauses/parameters and conflicts; no arbitrary natural-language claims.
- LT-04: Material partition, nonwalkable water, solid object reservations, house access approach; required-goal connectivity with actual square actor width and exact swept cardinal edges. No diagonals.
- LT-05: Canonical immutable SHA-256 layout revisions; clean guide, per-region/material masks, route corridor and reservation masks, coordinate authority, validation and provenance, downloadable ZIP.
- LT-06: Actual browser workflow, keyboard movement and negative collision probes, PNG/mask views, downloaded ZIP verification; three different tested examples.
- LT-07: Local PNG import boundary preserves original bytes and binds a separate import record to layout revision. Declared frame/dimensions are checked; actual painted image alignment, local semantic compliance and visual quality remain unverified.

## Milestone 2 local extension

- LT-08: Explicit style-only reference; immutable guide/source/request/prediction bindings.
- LT-09: Server-side WaveSpeed adapter, live schema/quote, durable project-total reservations, attempt cap, single submission per semantic request, no automatic paid retry. Unknown submissions require reconciliation, never guessed reattachment.
- LT-10: Imported PNG candidate preview over canonical navigation; raw-vs-guide diagnostics, source-retaining deterministic density export and honest unreviewed status.
- LT-11: Local alpha coverage and RGB region statistics are measurements, not material identity or visual PASS. No automatic artwork promotion.

## Explicit externally controlled style / review amendment

- LT-12: Strict versioned style specifications, bounded avoids, material prompts, role-tagged references/crop lineage, immutable old versions and editable named preset pointers. Canonical geometry remains untouched; changed style invalidates the selected quote/evaluation.
- LT-13: Mandatory separate layout/material/pixel-style/clearance production gates; pass/fail/uncertain plus visible cited evidence. Actual final-density image, guide, references and crops; exact hashes and local blockers enforced. Diagnostic export stays UNAPPROVED and separate. Final user acceptance is not implied by an automated gate.
- LT-14: Interchangeable explicitly configured capability-validated reviewer, free auth/metadata checks, actual response/usage, same transactional USD10 ceiling. Exactly one additional existing-urban strict review executed; no new generation; global generation cap remains exhausted at 2.
- LT-15: Correction default OFF, explicit opt-in and bounded 1–3 steps, same canonical geometry and shared budget, durable records, no-op/unknown-outcome/attempt-cap guards, no blind paid retry or silent source/collision change. Current proof is labelled mocks, not a claimed live corrected terrain. See REPORT-STRICT-STYLE.md.

## Explicit automatic repair amendment (latest authority)

`AUTO_REPAIR_AUTHORIZATION.md` supersedes the historical per-step confirmation / exhausted-two-image restriction for ONE bounded development run. Default3, explicitly configurable up to15 repair iterations across restarts, same USD10 inclusive of previous holds. One explicit start covers bounded image/review steps. Geometry, collision, style intent, final density and gate rules remain fixed. No unknown paid retry, no liability reset, no silent regression promotion. The executed run stopped after one generated correction because conservative registration failed its frozen threshold; see `REPORT-AUTO-REPAIR.md`. No successful repair or owner acceptance is implied. Paid controls were closed again after the terminal stop.

- LT-16: Durable Auto-Run/UI/API, deduplizierter Start, persistentes Iterationskonto, aktive Backgroundworker, Resume/Cancel ohne Liability-Verlust; eingefrorene Geometrie/Collision/Stil/Dichte/Gates.
- LT-17: Findings-basierte dokumentierte Korrekturen mit tatsächlich aktueller Quelle plus rollengetrennten Referenzen; gratis globaler Transformfix bevorzugt; konservativer Registrierungsstopp statt manueller heimlicher Handoffs oder Achsenwarp.
- LT-18: Best/Latest getrennt, keine Regressionspromotion, fail-closed Finalreview, Stop bei Erfolg/Cap/Budget/Ambiguität/Stagnation. Bericht `REPORT-AUTO-REPAIR.md` trennt genuine live Ausführung von gemockten Fehlerpfaden. Genau ein echter Repair endet an der Registrierung, nicht mit einem erfundenen PASS.

## Latest bounded two-style authorization

`OVERNIGHT_TWO_STYLE_AUTHORIZATION.md` is newer than the historical milestone scopes below. It authorizes the bounded two-reference phase on one fresh flat layout, at most two initial images plus one justified repair per style, at most seven all-time image jobs; EUR15 TOTAL including historical liabilities, while retaining the stricter single USD10 ledger ceiling. The implemented experiment service deliberately uses a narrower two-initial-images/zero-repair limit. It binds its own durable authorization without resetting the old AutoRun. No geometry/collision/gate relaxation. Executed outcome and closed controls: `REPORT-OVERNIGHT-TWO-STYLES.md`; warm automated gate passed, fantasy registration blocked, user acceptance pending.

## Explizite Ausschlüsse
Current paid pilot authorization: `PAID_AUTHORIZATION.md`, USD 10.00 PROJECT TOTAL including generation, external image review and conservative outstanding liabilities, not separate stage budgets. Initial generation max_attempts=1; explicitly authorized second urban style pilot minimally raises total generation cap to 2, now exhausted. USD10 shared ceiling unchanged. See REPORT-URBAN-PILOT.md. Accepted Waldlicht terrain may be read/uploaded as STYLE ONLY; new immutable guide is geometry authority. Pilot includes explicit uniform original-to-canonical registration, real playable browser/export and grounded review, never automatic production acceptance. Earlier zero-budget milestone reports are historical.

No public deployment, nginx/DNS/service-manager changes, animation-service edits, existing-game edits, old layout reuse, height/bridges, autotiling, prop generation, engine adapter, authentication service or performance work. No collision edits to excuse painted-image drift; no procedural substitute terrain. Final visual review remains with the parent Astra session/user. See `REPORT-PAID-PILOT.md`.
