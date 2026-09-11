# Neighbor-aware tile families

`src/autotiling.ts` is a renderer-independent module, exported from the package
root and `isometric-framework/core`. It resolves host-owned cells to named
variants. It does not load images, mutate scenes, or decide collision policy.

## Public API

```ts
import { autotileMasks, analyzeAutotiles, resolveAutotiles } from 'isometric-framework/core';

const cells = [
  { c: 2, r: 3, family: 'bed' },
  { c: 3, r: 3, family: 'bed' },
  { c: 3, r: 4, family: 'bed' },
];
// Catalog IDs must have matching host-owned art. This creates names, not sprites.
const variants = Object.fromEntries(autotileMasks('blob47').map(mask => [mask, `bed-${mask}`]));
const result = resolveAutotiles(cells, { mode: 'blob47', variants, seed: 'garden' });
if (result.diagnostics.length) throw new Error(result.diagnostics.map(d => d.message).join('\n'));
// Each result tile contains { cell, mask, variant } in input order.
// analyzeAutotiles(cells, { mode: 'blob47' }) returns just { cell, mask }.
```

`cardinal16` has 16 states. `blob47` has 47 canonical states, accounting for
diagonals only when both touching cardinal neighbors also connect. This preserves
inner corners around holes while keeping diagonal-only cells disconnected.

| Neighbor delta | Bit |
| --- | --- |
| c− | 1 |
| c+ | 2 |
| r− | 4 |
| r+ | 8 |
| c−, r− | 16 |
| c+, r− | 32 |
| c−, r+ | 64 |
| c+, r+ | 128 |

These are grid axes: c+ appears upper-right and r+ lower-right. The four low bits
retain Sunflower's existing planter convention. `autotileMasks(mode)` returns
sorted mask values; blob masks are **not** atlas indices 0..46.

Cells connect only on the same floor (`level` omitted means `ground`). By default
they also require equal `family` and equal local `elevation` (omitted means 0).
`connectFamilies: true` and `matchElevation: false` relax those respective rules;
neither allows cross-floor connections. Duplicate normalized cells and malformed
coordinates/options/catalog entries throw instead of producing ambiguous output.

A catalog value may be one variant ID or a list of equally weighted alternatives.
Selection uses the seed, normalized cell, family, elevation and mask; reordering
the input does not reshuffle art. Missing/empty entries produce `variant: null`
and `missing-variant` diagnostics. Missing images for otherwise valid IDs are
checked by the host/asset manifest, not by this topology module.

## Host integration

Keep the source cell set authoritative. After an edit, recompute the resolver and
derive visuals and colliders from that same state. This batch API uses O(n) work
for fixed-size catalogs and is adequate for small maps; it provides no incremental
cache or world editor. A bed may be a blocking sprite entity, while a path may be
a walkable textured terrain tile. Art selection must not silently change either
policy. Different elevation or floor families need their own geometry and scene
placement, not just different neighbor bits.

## Preparing compatible artwork

Use [consistent-tileset-authoring](../skills/consistent-tileset-authoring/SKILL.md)
for shared edges and rendered joins. Its optional raised-bed recipe produces
rigid borders from shared materials; it is not required for natural trails or
composed ground artwork. Test the chosen topology with a strip, bend and hollow
patch before expanding. The resolver itself remains headless.

## Scope and visible limits

This is binary neighbor connectivity within a family, not an arbitrary multi-
terrain Wang transition solver. Paths, walls and water can use the resolver but
still need compatible catalogs and their own geometry/collision choices. The
included assembler creates raised beds only; it cannot make a curved arch bridge.

Shared material samples can preserve edge continuity yet reveal mirrored motifs.
Inspect repetition and transitions at playing scale. More natural variants must
preserve the same edge contract; independently regenerating complete tiles can
reintroduce drift.
