# Overhang classification question

This is the canonical question put to a classifier when measured artwork leaves the
ground diamond its footprint reserves. Its hash is recorded as `classifier.promptSha256`
in an overhang ruling, so a reviewer can tell which question produced the verdict.
Changing this file changes the hash and invalidates every ruling that cites the old one.

## Subject

You are judging one side of one asset: the contiguous band of source columns the
checker reports in `overhang.columns.<side>`, over the full frame height. You are not
judging the asset as a whole, its style, or its quality. Each side is judged separately,
because a roof may legitimately overhang one side while a wall base spills on the other.

## Evidence to view

1. The band rendered at magnification, in place, with the lowest declared ground
   contact drawn as a horizontal line.
2. `groundClearancePx`: rendered pixels between the lowest opaque row in the band and
   the nearest declared ground contact. Positive means the band's lowest material sits
   above that contact on screen; negative means it reaches below it.
3. The whole asset, so the band can be attributed to a part of the artwork.

`groundClearancePx` is evidence, not an answer. Screen y conflates height and depth in
an isometric projection, so a positive clearance does not prove the material is airborne
and a negative one does not prove it rests on ground. Attribute the material to a part of
the artwork and judge that part.

## Question

Does the material in this band rest on ground the footprint does not reserve?

Answer with exactly one class.

| Class | Meaning | Permitted to overhang |
| --- | --- | --- |
| `canopy` | Foliage, fronds or branches held clear of the ground | yes |
| `eave` | Roof, gable, cornice, dormer or chimney projecting past the walls below | yes |
| `attachment` | Sign, lantern, banner or bracket mounted above ground | yes |
| `shadow` | Cast shadow or soft ground glow carrying no solid form | yes |
| `ground-contact` | Solid form meeting the ground: root flare, wall base, steps, plinth | no |
| `foundation` | Masonry or terrain the asset stands on | no |
| `unclear` | The evidence does not settle the question | no |

Record the reasoning in `basis`, naming the part of the artwork the band contains and
the clearance figure it was weighed against. `unclear` is a legitimate answer and fails
the gate: resolve it by widening the footprint or recalibrating, not by guessing.
