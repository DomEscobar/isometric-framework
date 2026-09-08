# Water & stone assembly

The default host now uses real generated PNGs through `generated-scene.ts`.
Its raw/registered/layered stages and measured collision/placement differences
are documented in [the generated trial](../../docs/GENERATED_ENVIRONMENT_TRIAL.md).
Exact prompts and original outputs are in `art/generated/`. The notes and static
`assembly-plan.json` below concern the preserved earlier SVG fixture only.

This is a standalone host using public runtime exports. The original three skill
outputs are frozen in `variants/a.json`, `b.json`, `c.json`; `accepted.json` adds a
separate center stone blocker to C. See the
[comparison](../../docs/ENVIRONMENT_SKILL_COMPARISON.md) before copying a trial.

Use `assembly-plan.json` with `variants/accepted.json` and the bundled assembly
checker. The plan includes contacts on all fountain frames, open/blocked cells,
exact bidirectional bridge crossing, lower passage, slab clearance and stone
height. It is host authoring metadata, not additional runtime scene fields.

All source graphics are authored SVG at one source pixel per world pixel, with
64x32 tiles and a 48px traveler. The 3x3 fountain occupies `(1..3,8..10)`:
256x224 frames, width 256, contact `(48,160)`, anchor `(48/256,160/224)`.
The basin's height is 12; a transparent center proxy at `(2,9)` is 86 high.
Its full cell conservatively covers the narrow stone column and bowl. Water is
decorative. Rigid geometry is identical across the four 4fps frames.

River cells `(5..6,0..12)` are unwalkable terrain with nonblocking water sprites.
Column 4 stays dry. The river loop is shimmer, not directional current simulation.

Bridge origin is `(3,4,bridge)`, height 72. The sparse deck spans columns 3..8,
rows 4..6; the center lane is row 5. Whole edge rows reserve rails, height 24.
Ground piers occupy `(3,4),(3,6),(8,4),(8,6)`, height 72, leaving column 4 open.
Access steps rise by 18 through ground `(0..2,5)` and descend at `(9..11,5)`.
Bidirectional links connect ground `(2,5)` to bridge `(3,5)` and bridge `(8,5)`
to ground `(9,5)`. Deck underside is 64 here, exceeding the actor's 48px height.

Deck, piers and near/far rails render as separate parts on their actual floors.
Upper floors occlude ground containers; use Ground view to inspect below. This
is a pier bridge, not curved arch art. The fountain remains one visual sorted
at its origin, so its physics contract does not certify every possible occlusion.

`main.ts` loads a deep copy of the chosen JSON and resolves the local atlas URL.
Buttons use public routing/pause/debug APIs. No engine code, global test hook,
save slot, provider key or service is required. The demo's jump uses the normal
two-cell range; the comparison harness separately uses a four-cell stress jump.
