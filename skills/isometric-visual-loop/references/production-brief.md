# One production brief from the user's prompt

Use this outline in the host's existing plan or art directory. Keep it short;
it is an execution aid, not a form the user must complete. No runtime schema or
particular filename is required.

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

Maintain one current completion contract, updating it with observed evidence.
Receipt and review files keep the attempt history; do not duplicate that history
or a second manual status ledger in the brief:

| Required outcome / inferred supporting detail | Host owner or resource | Evidence to collect | Status / remaining gap |
| --- | --- | --- | --- |
| Each requested landmark and its connecting route | Scene/assembly data | Overview plus traversal | Planned / built / verified / blocked |
| Each relevant moving family | Clip/overlay binding | Motion, wrap, joins and pause | Same status vocabulary |
| Shared style and readable player | Art manifest/captures | Actual scene at intended zoom | Same status vocabulary |

Replace these example rows with the real prompt's current contract. A built asset
is not verified until the relevant observation exists. Inferred supporting details
can change for a better result; explicit user requirements cannot silently disappear.
The contract preserves scope across turns and workers; it does not prove beauty.

For world production, turn the approved outcomes into the protected requirements
in the [acceptance plan](acceptance.md). Keep separate visual, motion, gameplay and
performance verdicts, with the exact required views and actor direction/action
coverage. Track the full defect list across rounds; a small repair list does not
replace the completion table. Changed art or code requires fresh candidate evidence.

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
