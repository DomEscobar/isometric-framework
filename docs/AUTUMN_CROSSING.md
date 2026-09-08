# Autumn crossing: world-production trial

`examples/autumn-crossing/` is a standalone, original autumn bridge scene named
**Goldlaub**. The target is the user's Witchbrook-like autumn reference: coherent
ground, raised natural banks, a readable traveler and layered foliage. This is a
bounded user-requested visual trial, not a claim of reference parity or achieved
production quality.

The trial informed our [Isometric World Production workflow](../skills/isometric-visual-loop/SKILL.md):
intent, calibration, complete construction, animation and independent review.
Its original image comparisons used an independent similarity score of at least
8/10 and acceptable observed frame timing as acceptance criteria. Neither was
achieved. Those historical results are retained below; the current workflow
distinguishes original art direction from exact layout replication.

## Run and inspect

From the repository root, run `npm run dev`, then open
`http://127.0.0.1:4175/examples/autumn-crossing/`. The host provides click routes,
tile-axis WASD, jump, pause, camera pan/zoom, named walks and mobile controls.
`Inspizieren` exposes the runtime's scene and actor diagnostics.

The map is 24 by 24 cells with 64 by 32 pixel projection. Real terrain and bridge
surfaces determine movement. The bridge has a raised deck, separately sorted arch
and parapets, explicit blocking rails and shore supports. Vegetation is placed as
individual entities. No flattened concept image is used as the playable world.

## Generated art and assembly

See [asset provenance](../examples/autumn-crossing/art/PROVENANCE.md) for sources,
rejected material and repeatable preparation steps.

- A generated material sheet supplies grass, dirt, paving and water RGB. The
  terrain assembler samples a continuous world phase and applies cardinal
  neighbor transition masks; it does not generate every tile independently.
- Generated trees, rocks, shrubs and a bench are cut out and registered at common
  pixel density using measured ground contacts.
- The first generated bridge had unsuitable proportions and was rejected. The
  replacement is split into arch, near rail and far rail. Each visible vertical
  face is fitted separately, keeping posts vertical. The generated floor is
  replaced by actual runtime paving cells.
- The existing pixel-cafe gardener supplies directional traveler frames.

## Review and repair record

The first independent critic scored the scene **3/10**, blocked at the shape
gate: oversized stairs, missing cliff banks, a foreground tree obscuring the
bridge and visible tile outlines. A playable route or attractive asset sheet
does not clear those composition failures.

The structural revision raises banks to 32 pixels, uses one 48-pixel access step
at each end and retains the deck at 64 pixels. Solid end supports fill 48..56
pixels below the deck; the central underside remains open over blocked water.
Foreground foliage was pruned, the bench moved and the camera shifted 5% right
and 7% upward. The terrain preparation now clips diamonds only once in the
renderer and samples water in screen space to avoid projecting already drawn
stones twice. Generated cliff material now supplies four phased bank facings.
Water and shore families use an eight-cell phase, reducing short visible repeats.
The second independent critic still scored the scene **3/10**, blocked at shape.
The final independent verdict is recorded in the result section below.

Local evidence lives under `.world-build/autumn-crossing/` (ignored working files).
Its numbered screenshots include builder captures; filenames alone do not imply
independent judging rounds. `host-playtest-pre-follow.json` records desktop
crossings, cardinal routing and W input. `host-playtest-results.json` records
the successful mobile journey with camera follow. `mobile-final-results.json`
records blocked water at ground cell 8,11 and the rail at bridge cell 9,11;
the final mobile check also exercised touch W movement toward +c and release.
The actor is fully visible after foliage pruning. These runs report no browser
errors. Earlier mobile pointer interception was repaired; it is not the current
verdict. Build and final review results must be recorded separately; no release
pass is claimed here.

## Frame timing: unresolved

The current evidence is `test-results/depth-performance/clean-performance.json`:
a fresh native Chromium run at 1536 by 1024 on AMD Radeon RX 9070 XT / D3D11,
after identified stale QA browser processes were closed. Times below are
**milliseconds per frame**, not FPS.

| Current diagnostic | Median | p95 |
| --- | ---: | ---: |
| Blank page before scene | 93.3 ms | 94.1 ms |
| Scene idle | 93.2 ms | 94.1 ms |
| Scene walking | 93.2 ms | 93.8 ms |
| Blank page after scene | 93.2 ms | 93.8 ms |

The browser is globally paced at roughly 93 ms in this run. The scene adds no
observable requestAnimationFrame slowdown relative to the adjacent blank-page
controls, but this environment cannot certify 60 FPS or fluid gameplay.

Earlier measurements below are retained as historical, contention-confounded
diagnostics. They do not establish current scene performance or a controlled
before/after speedup.

| Diagnostic | Median frame time | Evidence |
| --- | ---: | --- |
| Earlier renderer | 416.6 ms | `before.json` (renderer reported only WebKit WebGL) |
| Revised rendering without per-tile stencil masks, SwiftShader | 216.7 ms | `compositing.json` |
| Native Chromium, AMD Radeon RX 9070 XT / D3D11 | 83.3 ms | `cache-chromium.json`, `before` |
| Same native run with per-tile bitmap caches | 100.0 ms | `cache-chromium.json`, `cached`; rejected |
| Native blank-page baseline | 16.7 ms | `native-blank.json` |

The bitmap cache experiment was rejected. Reassess the accepted visual candidate
in a browser with a normal blank-page baseline before accepting a frame-rate
target.

## Current limits and next gate

Water is static. The arch opening is visual; no actor underpass is implemented,
and water remains blocked. Collision uses declared cells, footprints and body
heights, not transparent sprite outlines. Repeated material motifs, cardinal-only
transitions and cropped outer tree canopies remain art limitations.

Three independent reviews scored **3/10, 3/10, 3/10**. The final reviewer accepted
reduced cliff striping and broader water variation, but flagged reflected,
oversized water boulders. Shape still blocks progress: bridge width, river layout,
missing left stairs/fence and natural bank contours remain wrong against the
concept. The experiment found actionable defects; it did not demonstrate a
score gain or establish Witchbrook-like quality. More material variation alone
does not solve the remaining geometry/asset-design mismatch.

`npm run build` passed, including boundaries, strict TypeScript, library and all
five HTML hosts. Ten art-contract tests passed, including named side-material
validation. Three focused art-browser checks, `bridge-occlusion.mjs` and
`footprint-depth.mjs` passed. Vite reports the
large shared Pixi and autumn catalog chunks; the 7.59 MB terrain atlas is also
an authoring prototype cost, not an optimized production asset budget.

The requested bounded workflow experiment is complete. Its visual acceptance
criteria remain unmet; 60 FPS has not been certified. Continue with a
physically narrower bridge and an irregular river/bank assembly, then review
against the unchanged target before adding further decoration.

Durable review evidence: [target](evidence/autumn-crossing/concept.png),
[first candidate](evidence/autumn-crossing/initial.png),
[final live capture](evidence/autumn-crossing/final.png),
[final critic](evidence/autumn-crossing/critic-3.md),
[mobile checks](evidence/autumn-crossing/mobile-final-results.json) and
[same-run frame measurements](evidence/autumn-crossing/clean-performance.json).
The portable [visual loop skill](../skills/isometric-visual-loop/SKILL.md) records
the useful invariants and explicitly distinguishes a trial from convergence.

## Prompt-to-world workflow revision (2026-09-08)

Following the task reflection, the existing visual-loop skill now covers ordinary
prompts for complete environments. Runtime/AGENTS.md and CREATE_GAME.md distinguish
internal calibration from the final requested scope. The workflow retains one
production brief, coordinates existing assembly/material/animation skills, and
separates style references from exact layout replication. Full-world requests
have no automatic three-round trial cap. No runtime API was changed by this revision.

Two independent agents performed read-only forward-tests with the revised skill,
actual Runtime instructions and realistic prompts. They received the prompts and
task constraints, without expected answers. Their outputs were production plans,
not generated environments or executed gameplay tests:

| Prompt | Observed planning behavior |
| --- | --- |
| Lively autumn witch village, shops, curved river, stone bridge, large fountain, desktop/mobile | Planned the complete village beyond calibration; included supported sprite-overlay water/flow, fixed structures, traversal and mobile evidence; identified collider/phase limitations |
| Tiny, richly finished Japanese courtyard; style reference only; explicitly no animation | Retained small area and high finishing effort; used the reference for style, preserved static scope and avoided replica-position scoring |
| Quick bridge collision test with simple shapes, no generated assets | Kept a functional fixture, omitted art generation/world expansion, selected focused traversal/blocking checks |
| Animate only the existing fountain | Preserved unrelated scene content and colliders; planned stable water layers and loop/wrap/pause/occlusion checks |

The scope reviewer found generic wording that could overrule these cases. The
follow-up patch explicitly permits final diagnostic shapes for a requested
fixture, conditions loop checks on actual motion scope, limits benchmarks for
local repairs and distinguishes a bridge's visible opening from a required
walkable underpass. Skill frontmatter validation and local-link checks passed.

This is evidence of improved intent interpretation and planning, not proof that
an agent can now render a finished high-quality world from every prompt. The
earlier three image scores remain unchanged. A subsequent real production run
must still demonstrate full content, temporal quality, collision and performance.
