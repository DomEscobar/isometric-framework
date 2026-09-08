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
| `tolerances` | Nonnegative `groundErrorPx` and `heightErrorPx`, chosen before review |
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
| `allowedOverhang` | Description of intentional foliage/shadow extension; empty when none |

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

For integrated art, retain a reproducible comparison command or recipe with the
host pack. A source hash binds the sidecar to a file, not the scene to that file.
Compare each covered entry against the actual host definition:

- Resolve texture to image to the bytes actually served, and compare their hash
  with the measured source. Do not rely only on matching texture or image IDs.
- Compare crop and effective anchor for every kind, including terrain. Record
  renderer defaults or overrides explicitly instead of silently skipping them.
- Compare effective render size, offsets, occupied footprint, and sampling.
  For terrain include the tile-fit/mask behavior; for animation resolve the
  actual selected frames, and state which frames the comparison covers.

Report omissions as unverified. A standalone preview or copied manifest is not
this comparison. Keep the recipe in maintained host files and generated results
in its ignored evidence directory so future agents can repeat it after changes.

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
