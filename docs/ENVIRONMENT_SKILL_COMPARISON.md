# Environment skill comparison — 2026-09-08

This records the earlier SVG-only exercise. The user correctly required a real
generated-asset follow-up; see [the executed generated trial](GENERATED_ENVIRONMENT_TRIAL.md).
The lab now defaults to generated art and retains these older fixtures separately.

## Scope and method

The requested three variants were implemented as three authoring workflows,
each applied by an independent agent to the same river + fountain + bridge brief.
Each received the [raw challenge](../skills/animated-environments/references/challenge.md),
the same authored atlas/source measurements, public runtime documentation and
only its assigned experimental skill. Agents had separate outputs and did not
read sibling results. Existing art-integration guidance was available to all.
No engine edits or image-provider calls were part of the trial.

| Variant | Instruction emphasis | Observed result |
| --- | --- | --- |
| [A: animation first](../skills/animated-environments/references/variants/environment-animation-first/SKILL.md) | Play a loop, then compose | First validation rejected explicit `bodyHeight: 0` on water; agent corrected it. Final scene aligned. Conservative 86px body covers the whole basin. Agent did not perform the requested early browser playback. |
| [B: contract first](../skills/animated-environments/references/variants/environment-contract-first/SKILL.md) | Source contacts, scale and footprint | First submitted scene valid; exact fountain contacts and correct bridge layout. Models only the 12px basin body. |
| [C: topology first](../skills/animated-environments/references/variants/environment-topology-first/SKILL.md) | Solid cells, surfaces, openings and parts | First submitted scene valid; independent bridge/underpass and exact contacts. Also models only the 12px basin body. |

Original final scenes remain in `examples/environment-lab/variants/a.json`,
`b.json`, `c.json`, selectable in the lab. The refined `accepted.json` derives
from C and adds a transparent 1x1, 86px stone proxy at `(2,9)`. The basin remains
3x3 and 12px high. This is a conservative grid approximation of the narrow
column/bowl, not a silhouette collider.

## Common evaluation and reflection

The coordinator applied the same independently declared contact/path expectations
to all three scenes, then rendered and stepped the actual runtime:

| Observation | A | B | C | Refined |
| --- | --- | --- | --- | --- |
| Basin contacts in every frame, occupancy, exact bridge routes and lower passage | Pass | Pass | Pass | Pass |
| Water pixels change, pause freezes, one-second loop returns to initial pixels/frame | Pass | Pass | Pass | Pass |
| Actor actually crosses raised bridge and uses dry underpass | Pass | Pass | Pass | Pass |
| Deliberately wrong fountain anchor / monolithic solid bridge detected | Both | Both | Both | Both |
| Extra long-jump probe avoids passing through central stone | Pass | Fails | Fails | Pass |

The extra jump uses rise 84, duration 0.8, distance 4, from `(0,9)` toward `(4,9)`.
It exposes vertical volume omitted by walking-only checks. B/C reach the far side
through the stone; A/refined fall back to an in-place hop. This is an added stress
condition, not a claim about every default two-cell jump.

There was also a **brief/source ambiguity**: metadata called the rigid center
“decorative” while describing stone geometry and asking the author to choose its
collision height. B/C explicitly used that interpretation. Their omission cannot
be attributed solely to skill ordering. The final assembly skill requires
reconciling physical parts with intended gameplay and recording low and tall
solids. Decorative animation should not silently make stone passable. The source
note is retained so the original comparison inputs remain reproducible.

An early evaluator watched `arrive` for intermediate floor changes, although that
event fires at the destination. The corrected evaluator observes `move`; all
actual crossings pass. This was a harness error, not three broken bridges.

## Selected guidance and follow-up

Use two complementary portable skills:

- [multi-tile-asset-assembly](../skills/multi-tile-asset-assembly/SKILL.md): C's
  surfaces/openings/part ownership plus B's measured projection, with explicit
  solid heights and relevant jump/ceiling verification.
- [animated-environments](../skills/animated-environments/SKILL.md): fixed rigid
  structure, constrained moving regions, source/alpha handling, coherent edges,
  simulation timing and actual loop playback. Large structures route to assembly.

A fresh fourth agent applied the final instructions to the same raw challenge
without seeing trial scenes or the refined solution. Its first scene included
the separate 12px basin and 86px center, deck/links and open towpath. Scene validation
and its assembly plan passed. That agent made no browser or jump claim; rendered
evidence above belongs to the coordinator's refined scene. It also identified
the source wording and the need to distinguish the PNG art checker from this SVG
fixture. The final skills explain these limits.

This is one trial per variant and one follow-up, with no no-skill baseline or
statistical ranking. It supports these specific instruction changes, not a
universal workflow winner or successful production image generation.

## Reproduce and inspect

From the source checkout, start `npm run dev`, then:

```sh
node --experimental-strip-types tests/environment-skills.mjs
node --experimental-strip-types tests/environment-skills.mjs accepted
node tests/environment-lab-browser.mjs
```

The first command is a comparison report: known B/C stress failures are findings,
not a passing acceptance gate. The `accepted` command fails for acceptance
failures. Reports, common plan and loop/underpass screenshots go to
`test-results/environment-skill-comparison/`; desktop/mobile journeys go to
`test-results/environment-lab/`. Original agent notes and the final independent
trial remain under `test-results/` (ignored local evidence). The frozen scene
inputs and playable host remain in `examples/environment-lab/`.

Main skills, three variants, references, generator/atlas and assembly checker
travel with copied Runtime folders and the package's `skills` directory. The lab
and tests require the source checkout; npm consumers use their own host. The
checker resolves public source core or packaged `dist/core.js`.

Source SHA-256:

- Atlas: `e9b794dd4611430071ee9a5d5fa8b6fa2cd910ab9179f815ecc52a0be6e35e0f`
- Measurements: `f45ff4aa6e54b9791de6f2f1e1606ea99a8db073b863c19679524bbb2dec6bc2`

## Visual and engine limits

These are authored SVG calibration graphics. Rendered views show stable base
contacts, continuous shimmer tiles and a usable deck. They do not establish the
reference images' illustration quality, directional river flow, or a detailed
arched bridge. Waterfall, vegetation and building recipes are guidance, not extra
completed scenes. No raster generation/background removal was needed here.

Upper floors draw over ground; cutaway reveals the underpass. A flattened fountain
cannot interleave with every player position. A curved arch underside cannot be
expressed exactly by current rectangular bodies/slabs. The assembly skill explains
layered art, conservative approximations and where an engine extension is needed.
Metadata checks never certify those visual or physical cases automatically.
