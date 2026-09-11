# One production brief from the user's prompt

Use this outline to fill gaps in PROJECT_CONTRACT.md or the existing approved
brief. The agent drafts it for discussion; the user need not complete a technical
form. Preserve prior decisions and do not create another contract.

- **Intent and scope:** requested experience, explicit constraints, intended
  completeness and effort. Separate a finished environment from a technical trial.
- **Art direction:** original reference and its role (style/layout/both), projection,
  working pixel scale, palette/light, player-relative scale and visual hierarchy.
- **World layout:** regions, landmarks, connecting routes and views. Note which
  buildings need only exteriors and which require traversable interiors/passages.
- **Ground composition:** material adjacencies, path and bank contours, transition
  treatment, shared pixel density and variation across cells. For natural terrain,
  use the [landscape contract](../../consistent-tileset-authoring/references/landscape-composition.md)
  and record ground-only acceptance before optional props hide the surface.
- **Assemblies:** common origins, surfaces, solids, openings, joins and access.
  Include how roots, foundations and thresholds meet their surrounding material.
  Identify API gaps before generating detailed parts; link existing assembly plans.
- **Motion:** fitting moving regions, fixed landmarks, flow direction, shared or
  deliberately varied timing, pause behavior. Explain static-only scope if requested.
- **Production order:** risky calibration first, then full content, motion and
  integrated review. Name the work remaining after calibration explicitly.

Keep approved outcomes here, with stable requirement IDs where helpful. The
acceptance plan translates those outcomes into checks and reference/view coverage;
it is technical execution data, not a separately negotiated artistic brief.
Do not put frequently changing task status, attempts or review verdicts in this
contract. Use production receipts and the acceptance report for current status.
The plan's optional `contract` path binds this document at freeze time. Changing
approved scope requires reconciling the plan and creating a new baseline; a
build failure or an inconvenient asset does not authorize narrowing it.

Keep measured layout, contact/anchor bindings and packed manifests as their
authoritative technical data. Link them rather than copying their values here.
Inferred supporting details may evolve; explicit user requirements must remain
covered. Evidence, not a completion table, establishes the observed result.

## Effort and interpretation examples

- "A lively village with a river, bridge and small shops":
  plan the complete village composition, shared terrain, distinct shop exteriors,
  traversable crossing and fitting environmental motion. Select reasonable sizes
  and defaults. A one-bridge calibration is a milestone, not the delivered village.
- "A richly finished tiny courtyard": spend effort on composition, meaningful
  detail, materials and appropriate motion inside the small space. More map area
  is not a proxy for effort. Do not add unrelated districts or game systems.
- "Quickly test bridge collision with basic shapes, no generated assets": keep
  the deliverable a functional fixture. Do not force a production-art pipeline.
- "Make only the existing fountain flow; keep the rest unchanged": integrate a
  stable animated region, use existing assets where suitable and check its adjacent
  actor/join views. Do not redesign the entire scene.

These examples guide interpretation; they are not fixed scene recipes or a
keyword classifier. Follow the actual prompt and prior user preferences.
