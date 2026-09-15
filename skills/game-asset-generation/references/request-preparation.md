# Offline reference preparation

Use `scripts/prepare-request.py spec.json --out evidence/request-001` before a
reference-guided image or video job when the exact inputs need a reviewable handoff.
The helper performs no provider request and grants no spending authorization.

The version 2 specification contains only a description and references:

```json
{
  "version": 2,
  "description": "Preserve the approved character identity and facing.",
  "references": [
    {"id":"style","path":"style.png","role":"style","approval":null,"crop":null},
    {"id":"layout","path":"layout.png","role":"layout","approval":null,"crop":null},
    {"id":"hero-ne","path":"facing.png","role":"identity","approval":"approved","crop":{"x":12,"y":8,"width":32,"height":48}}
  ]
}
```

Paths are relative PNG files beside the specification. Roles are `style`, `layout`,
or `identity`. Identity inputs require the explicit value `approved`; style and
layout inputs use `null`. Whole images are copied byte-for-byte and crops preserve
the selected decoded pixels. `board` is reserved as an output identifier.

The new output directory contains the selected images, `board.png`, and
`request.json` with source, selected-pixel, output, specification, and board hashes.
Inspect the actual board before submission. The hashes prove local correspondence,
not visual quality, provider submission, budget approval, or successful generation.

For character I2V, the approved directional facing must be an actual identity
input. Keep this bundle beside the facing generation record and the later video
job. Direction matrices, calibration receipts, direct character-sheet requests,
and individually requested motion frames are retired; version 1 specifications or
extra legacy fields fail rather than being silently migrated.
