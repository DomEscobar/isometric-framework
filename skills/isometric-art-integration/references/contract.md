# Calibration contract, version 1

This is a host-owned authoring sidecar. It does not extend the runtime scene
schema. All image paths resolve relative to the contract file; the checker reads
local PNG files and never downloads art. Node 22.18+ is sufficient.

Start by copying [starter-contract.json](starter-contract.json) beside the real
artwork. Its three candidates illustrate tile, actor, and chair geometry in a
hypothetical 200×80 atlas. The zero hashes and missing `atlas.png` intentionally
prevent acceptance until real paths, hashes, frames, and landmarks are supplied.
Do not force artwork to match those example dimensions or proportions.

The checker accepts UTF-8 JSON with or without a leading BOM. Unknown fields are
rejected to catch spelling mistakes. Keep provisional assumptions, measurement
methods, and source-pixel uncertainty in an adjacent `measurement-notes.md`.

## Targets and evidence strength

In the notes, distinguish intended target ranges (chosen before scaling, with
their style/reference rationale) from resulting measured dimensions. Setting a
reference to the current measured seat height can detect later drift, but cannot
independently establish that this seat has the intended proportion to the actor.
The version 1 checker compares point heights, not target ranges; review those
ranges separately. Do not add unsupported fields to the JSON schema.

Classify correspondences in the notes:

- **Independent observation:** source landmarks paired with independently chosen
  world geometry. This can test projection agreement within stated uncertainty.
- **Authored geometry:** contacts established by the asset generator's geometry.
  This verifies that geometry's mapping; hidden envelope corners are not observed
  opaque pixels, and rendered joins still require inspection.
- **Inferred containment:** target grid points inverse-derived from the same
  rendered source contacts. These locate the base within its footprint, but their
  near-zero projection error is not independent evidence of the artist's camera.

Do not combine these categories into an undifferentiated count of projection
proofs. Preserve uncertainty and unmeasured portions of the pack.

## Coordinates and measurements

Source points use pixels **relative to the cropped frame**, not atlas coordinates.
An anchor is normalized within that frame. Render dimensions, offsets, errors,
and projection dimensions are world pixels before camera zoom or device scaling.
Ground grid coordinates are relative to the entity's origin cell:

```text
project(c, r) = ((c + r) × tileWidth / 2, (r - c) × tileHeight / 2)
sx = render.width / frame.width
sy = render.height / frame.height, or sx when height is omitted
actual(source) = (source - anchor × frameSize) × (sx, sy) + offset
```

This preserves this runtime's W northeast / D southeast / S southwest / A
northwest convention. A 1×1 tile centered on its cell has grid corners
`(-.5,-.5), (.5,-.5), (.5,.5), (-.5,.5)`. A C×R occupied rectangle spans
`c = -.5 .. C-.5`, `r = -.5 .. R-.5`. A prop's rigid base may occupy a smaller
area inside that rectangle. Do not measure the foliage silhouette as its base.

`groundPoints` pairs measured rigid source contacts/corners with intended grid
points. The checker compares their rendered locations, including offset, against
the declared projection. Props need at least three noncollinear points; actors
need at least one foot-contact point. Terrain needs exactly the four 1×1 corners.
Check animation frames individually if their crop, contact, or scale differs.

Use correspondences appropriate to the actual shape. A smaller rigid base need
not touch every canonical cell corner. A failed correspondence alone does not
prove overflow. The checker also inverse-projects measured rendered contacts
(`c = x/tileWidth - y/tileHeight`, `r = x/tileWidth + y/tileHeight`) and checks
their containment independently, allowing the declared ground-error tolerance.
Compare any reported error with measurement uncertainty before choosing a repair.

Height measurements use a vertical segment: `base` is the ground projection
directly beneath `top`, not an unrelated foot at another depth. Their horizontal
rendered positions must agree within tolerance. Their rendered vertical distance
must equal `heightReferences[reference] × projection.heightPixelsPerUnit`.
Choose landmarks such as bare-head standing height, chair seat, tabletop, or
door clearance. Include hat height separately if relevant. Actors require a
height measurement. For furniture, record the seat/tabletop measurements needed
to judge its relation to the player; the checker cannot infer missing semantics.

## Fields

| Field | Meaning |
| --- | --- |
| `version`, `pack` | Version `1` and a descriptive pack ID |
| `projection` | Positive `tileWidth`, `tileHeight`, `heightPixelsPerUnit` |
| `tolerances` | Nonnegative `groundErrorPx` and `heightErrorPx`, chosen before review; `groundErrorPx` must stay below half a tile width, because every contact, footprint and overhang measurement is judged against it |
| `heightReferences` | Named positive heights in the pack's shared world units |
| `assets` | Array of candidates with unique IDs |
| `assets[].kind` | `terrain`, `prop`, or `actor` |
| `image`, `sha256` | Local PNG path and its SHA-256 digest, binding measurements to the source |
| `frame` | Integer atlas `x`, `y`, `width`, `height`; must fit actual PNG dimensions |
| `anchor` | Normalized `x`, `y` in `[0,1]` |
| `render` | `width`, optional `height`, optional `offset: {x,y}` |
| `footprint` | Positive integer `columns`, `rows`; terrain must be 1×1 |
| `groundPoints` | Array of `{source: {x,y}, grid: {c,r}}` pairs |
| `heights` | Array of `{reference, base: {x,y}, top: {x,y}}` measurements |
| `overhangPx` | Optional per-side rendered-pixel budget for artwork that deliberately leaves the footprint's ground diamond; needs a nonempty `allowedOverhang` reason and a classified ruling |
| `allowedOverhang` | Description of intentional foliage/shadow extension; empty when none |

## Rule on measured overhang

Art that fits only because of its `overhangPx` budget needs a verdict on what
actually overhangs. Point the contract at one rulings file with the optional
top-level `overhangRulings` path, and keep that file among the acceptance check's
declared inputs so a verdict cannot be rewritten after acceptance.

The checker reports the spilling column band per side, how far its lowest material
stays above the nearest declared ground contact, and a `regionSha256` over that
whole question. A ruling must cite that hash and the image hash, so it expires as
soon as the artwork or its calibration moves.

```json
{
  "version": 1,
  "rulings": [
    {
      "asset": "clay-hall",
      "imageSha256": "<64 hex, the artwork judged>",
      "regionSha256": "<64 hex, reported by the checker>",
      "classification": { "left": "eave", "right": "eave" },
      "basis": "Both bands hold terracotta roof tiles ending +69 and +63 px above the nearest ground contact.",
      "classifier": { "model": "<who decided>", "promptSha256": "<64 hex over the question asked>", "decidedAt": "2026-09-17" }
    }
  ]
}
```

Every side the silhouette leaves must be classified, and a side that is not
measured may not be classified. `canopy`, `eave`, `attachment` and `shadow` may
overhang; `ground-contact`, `foundation` and `unclear` are findings. See
[the classification question](overhang-prompt.md), whose hash belongs in
`classifier.promptSha256`.

Only terrain may use a nonuniform render scale, matching this runtime's terrain
renderer. Its actual corners must still fit the canonical ground projection.
Props and actors preserve aspect ratio. A terrain frame's bounding-box ratio
alone does not prove its internal paving lines share the props' camera angle;
inspect those lines on the calibration board and in the host scene.

The checker verifies PNG signature/IHDR dimensions, file size bounds, hash, source
frame bounds, metadata shape, projected ground error, containment of declared
rigid ground points, and declared height measurements. It does not decode all PNG
pixels, locate physical landmarks automatically, check licenses, detect all alpha
fringes, or validate gameplay. Browser decoding and visual review remain required.

## Bind the contract to the host

A source hash binds the sidecar to a file, not the scene to that file. Keep a
`binding-plan.json` beside the host scene that says which calibrated asset renders
which scene definition, then run `check-scale-binding.mjs` on the delivered scene:

```json
{
  "version": 1,
  "pairings": [
    { "asset": "terrain", "tile": "grass" },
    { "asset": "actor-idle", "entityType": "traveler", "bodyHeightReference": "standing" },
    {
      "asset": "fountain",
      "entityType": "fountain",
      "bodyHeightReference": "basin",
      "deliberateBodyHeight": "full-height blocker so the player cannot jump through the centrepiece"
    }
  ],
  "images": { "atlas": "./art/atlas.png" },
  "exempt": { "entityTypes": { "sparkle": "decorative particle without ground contact" }, "tiles": {} }
}
```

Pair each asset with exactly one `entityType` or `tile`. `images` maps every scene
image ID a paired texture uses to its host file, whose bytes are hashed against the
measured source; `null` declares an unresolvable image and records it as unverified
instead of passing it. `bodyHeightReference` is required only when an asset names
several height references. `exempt` is the only way to leave art uncalibrated, and
every entry needs a stated reason, so omissions stay visible instead of silent.

This pairing weighs the host's `bodyHeight` against a height you declared in
`heightReferences`, so two agreeing declarations can both understate the artwork,
a prop naming no reference is only recorded as unverified, and
`deliberateBodyHeight` waives the comparison with prose. None of that reaches the
silhouette. The production flow's `art` check therefore measures each prop's body
height from decoded alpha and requires the exported binding's `bodyHeight` to fall
inside that band, with no prose exemption; see
[production flow](../../isometric-visual-loop/references/production-flow.md).
Use this pairing to prove which definition renders which asset, not to establish
how tall it is.

A collider may deviate from the measured art on purpose, for example a conservative
full-height blocker. Say so with `deliberateBodyHeight`: the pairing is then recorded
as a stated exception instead of a failure. A blocking entity still needs an explicit
`bodyHeight`; the exception covers the deviation, not the omission.

The check compares projection, crop, effective anchor, render scale, offset, grid
footprint and `bodyHeight` against the shared world scale, resolves every frame of
an animated clip rather than the first, and requires a blocking entity to declare a
physical height. It reads declared values only: sampling, terrain tile-fit and mask
behavior, and whether a landmark actually sits on the artwork it names remain
manual. State which of those you compared and report the rest as unverified.

A pass means the scene uses the numbers you calibrated. It is not a judgement that
those numbers suit the game: whether a stylized actor should be 1.8 units, and
whether the result reads correctly beside its props at playing zoom, stay visual
decisions. Read `exceptions` and `unverified` before the verdict, and take both to
the shared-scale board and the rendered scene. Keep the plan in maintained host
files and generated results in the ignored evidence directory so future agents can
repeat it after changes.

## Worked coordinates

For an 80×40 tile image, `anchor = (.5,.5)`, `render.width = 80` and a 1×1
footprint, the frame-local source/grid correspondences are:

| Source | Grid |
| --- | --- |
| `(0,20)` | `(-.5,-.5)` |
| `(40,0)` | `(.5,-.5)` |
| `(80,20)` | `(.5,.5)` |
| `(40,40)` | `(-.5,.5)` |

For a 40×80 actor frame rendered at width 40, `anchor = (.5,.9)`, the contact
`source = (20,72)` corresponds to `grid = (0,0)`. With height scale 40 pixels
per unit and standing reference 1.8 units, a top at `(20,0)` and base at `(20,72)`
match a 72-pixel standing height. These numbers illustrate the equations; they
are not mandatory proportions for another game.

Compute a real source digest without modifying the PNG:

```sh
node --input-type=module -e "import{readFileSync}from'node:fs';import{createHash}from'node:crypto';console.log(createHash('sha256').update(readFileSync(process.argv[1])).digest('hex'))" path/to/atlas.png
```

Complete executable examples are generated in temporary folders by
`tests/check-art.test.mjs`; they are geometry fixtures, not approved production art.
Keep palette, light direction, pixel density, source/prompt/license records, and
close-up evidence beside this JSON. These qualitative records need not be added
to the runtime's validated manifest.
