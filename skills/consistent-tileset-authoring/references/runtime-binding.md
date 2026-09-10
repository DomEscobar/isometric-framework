# Bind a neutral tile family

This L-shaped three-cell example creates catalog names, not artwork. The current
host must supply compatible named textures for every used mask.

```ts
import { autotileMasks, resolveAutotiles } from 'isometric-framework/core';

const cells = [
  { c: 1, r: 1, family: 'surface' },
  { c: 2, r: 1, family: 'surface' },
  { c: 2, r: 2, family: 'surface' },
];
const variants = Object.fromEntries(
  autotileMasks('blob47').map(mask => [mask, `surface-${mask}`]),
);
const result = resolveAutotiles(cells, { mode: 'blob47', variants, seed: 'layout' });
if (result.diagnostics.length) {
  throw new Error(result.diagnostics.map(d => d.message).join('\n'));
}
// result.tiles contains { cell, mask, variant } in input order.
// Bind each variant to the host's tile or entity art and its collision policy.
```

`cardinal16` distinguishes four-neighbor connections; `blob47` also distinguishes
concave corners. A diagonal connects only when both adjoining cardinal neighbors
connect. Mask values are not sequential atlas positions.

| Grid neighbor | Bit |
| --- | --- |
| c- | 1 |
| c+ | 2 |
| r- | 4 |
| r+ | 8 |
| c-, r- | 16 |
| c+, r- | 32 |
| c-, r+ | 64 |
| c+, r+ | 128 |

`c+` projects upper-right; `r+` projects lower-right. Cells connect on the same
floor and, by default, with equal family and local elevation. Omitted floor is
`ground`; omitted elevation is 0. `connectFamilies: true` or
`matchElevation: false` relax those respective checks, never floor identity.

Missing catalog entries produce `variant: null` and diagnostics. The resolver
does not load images or decide whether cells block walking. Derive both visuals
and colliders from the authoritative host cell set after edits. A valid mask does
not prove that its artwork joins: inspect a strip, L and hollow patch at game scale.
