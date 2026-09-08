# Sunflower art skill run reflection — 2026-09-08

The skill helped isolate rigid planter geometry from foliage and kept repairs in
the host pack. Its first real repair run also exposed a gap: measured consistency
was easier to demonstrate than independently justified visual quality.

## What went poorly and what changes

| Observation from this run | Consequence | Updated skill guidance |
| --- | --- | --- |
| The full 28-entry contract followed scene implementation. Furniture reference values closely reproduce the resulting measured heights (.524 seat → .52 reference; .742 table → .74). | A passing comparison describes the chosen result; it does not independently prove that the scale choice was right. | Preserve defect closeups and choose target proportion ranges before scaling a representative candidate. Label later measurements retrospective and keep targets separate from resulting dimensions. |
| Two generated foliage outputs were RGB with baked checkerboards, including a transparency repair attempt. A fresh simpler generation finally produced usable RGBA. | Repeating a transparency instruction did not fix the failing generation assumption and consumed an extra attempt. | Preflight one representative decoded output before a full pack. Inspect actual alpha, edges, and interior holes against contrasting backgrounds; change the approach after the same technical failure repeats. |
| The initial terrain diagnosis emphasized a 299×197 frame being fit to 80×40. | A padded frame ratio and a supported terrain warp alone cannot establish a bad ground projection. Later measured outer tips fit within tolerance. | Diagnose rendered ground edges and internal lines. Separate crop bounds, ground geometry, and vertical content. |
| Some support grid points were inverse-derived from observed contacts; planter corners came from authored geometry. | Treating all 98 correspondences as independent camera evidence would overstate the result. The measurement notes already disclosed these distinctions correctly. | Classify independent observations, authored envelopes, and inferred containment. Preserve that distinction when summarizing counts and passes. |
| Reducing the furniture composite improved seat/table proportions while canopy fringe clearance remained near/below the gardener's hat. | One global scale cannot independently tune all parts. Blocking the group does not resolve every visual proportion. | Check coupled seat/table/canopy constraints together; split or reauthor when needed, otherwise state the remaining visual limitation. |
| The temporary host comparison skipped terrain anchor assertions and did not bind the actual scene image bytes to the sidecar hash. | Its broad “scene definitions matched” claim exceeded the checks performed, although inspection did not establish wrong current values. | Compare image resolution/hash, frames, effective anchors for every kind, size, offsets, footprint, and sampling. Retain a reproducible host recipe and name omissions. |
| An actor source comment claimed actual jump contact alignment, while metadata covered only four idle facings. | Comments could imply acceptance of 12 unmeasured walk/jump frames. | Keep claims within tested asset/state coverage. The comment is corrected; metadata coverage remains four idle facings. |

## Execution lessons

The independent playtest was interrupted by the reflection request. Partial
desktop/mobile successes were correctly kept separate from final acceptance;
the outstanding run was resumed rather than marked green. Two preliminary browser
CLI artifacts also landed at the repository root before later captures were
scoped correctly. Set the ignored output directory before the first capture and
carry pending checks forward explicitly across interruptions.

Delegated tasks need the existing direct-edit authorization and exact ownership
in their handoff. Losing that context caused avoidable workflow clarification.
That is an orchestration lesson, not a reason to add an art-specific approval step.

## What worked and should remain

- Separating exact authored stone bases from decorative foliage addressed the
  demonstrated border defect without changing engine physics.
- The original failing planter contract remains available at the same 2 px
  ground / 4 px height tolerances; the tolerances were not widened to force a pass.
- The notes disclose uncertain landmarks, inferred contacts, unmeasured frames,
  excluded fences, and composite limitations. These disclosures are strengths.
- The portable checker and shared-scale board help find geometric problems, while
  actual host playtests remain responsible for joins, motion, depth, and controls.

## Result and limits

The existing skill entrypoint and its two references now encode these decisions.
No new schema, checker claim, or generic review framework was introduced. This
reflection changes guidance and corrects evidence wording; it does not establish
that all artwork or animation frames are calibrated. Current repair acceptance
and retained test evidence are recorded separately in
[Runtime verification](../../../VERIFICATION.md).

The temporary integration helper's image-binding and terrain-anchor gaps remain
limitations of that particular result. Do not cite it as a complete host binding
check. The metadata checker itself remains annotation-only.
