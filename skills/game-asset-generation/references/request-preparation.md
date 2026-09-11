# Offline reference preparation

Use `scripts/prepare-request.py spec.json --out evidence/request-001` before a
reference-guided provider job when the exact inputs need a reviewable handoff.
It has no provider integration and makes no generation request.

The version 1 spec selects only relative PNG files beside the spec. Each reference
has an `id`, `path`, `role` (`style`, `layout`, or `identity`), `approval`, and a
`crop` that is either `null` or `{x,y,width,height}`. Whole sources are copied byte-for-byte; crops
preserve the selected pixels. The output directory must be new and contains the
selected PNGs, a labeled `board.png`, and `request.json` with source/spec/board
hashes, roles and crop coordinates. `board` is reserved as a reference id.

```json
{
  "version": 1,
  "description": "Keep the character identity; use layout only for placement.",
  "matrix": null,
  "references": [
    {"id":"style","path":"style.png","role":"style","approval":null,"crop":null},
    {"id":"layout","path":"layout.png","role":"layout","approval":null,"crop":null},
    {"id":"hero-ne","path":"sheet.png","role":"identity","approval":"approved","crop":{"x":12,"y":8,"width":32,"height":48}}
  ]
}
```

An identity reference must be explicitly `approved`; rejected identity crops are
refused rather than carried forward. This is an operator declaration, not visual
approval by the tool.

For a multi-direction action matrix, create and review one direction/action
first, then place a nearby version 2 receipt such as:

```json
{"version":2,"kind":"directional-calibration","action":"attack","direction":"ne","identitySelections":[{"sourceSha256":"<source sha256>","crop":{"x":12,"y":8,"width":32,"height":48},"pixelsSha256":"<selected pixels sha256>"}],"judgement":"self-reported-approved"}
```

Set `matrix` to the action, requested directions, and receipt filename. The
helper requires the receipt action/direction and every source hash, crop coordinate,
and selected-pixel hash to match the currently selected approved identity sources.
Matrix directions use the eight compass directions. The receipt remains self-reported:
it does not prove authenticity, facing, quality, authorization, a budget, or that
a provider cannot be called outside this helper. A single-direction probe is a
directional-animation safeguard, not a restriction on ordinary multiasset work.
