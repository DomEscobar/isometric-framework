---
name: environment-contract-first
description: Trial workflow that fixes source contacts, world scale and footprint contracts before animating isometric environment assets.
---

# Variant B: shared contract first

Before composition, record tile projection, player height, each source frame's
pixel contact, render scale, world origin, rigid ground corners and occupied cells.
For each ground landmark compute `(source - anchor*frameSize)*scale + offset`
and compare it to the expected isometric projection. Do not infer a multi-tile
asset's contact from the bottom-center of its padded image.

All frames of a loop use one coordinate system and unchanged scale. Measure the
stationary structure once, then check its contacts in the remaining frames. Only
water/particles should move. Bind explicit runtime clips, then compose with
rectangular collision pieces and actual raised floor/link data where required.

Check one continuous river join, the fountain outline beside the actor, and the
bridge both on and below its deck. Separate visual, animation and traversal
verdicts. Use the runtime art guide for exact available APIs. Preserve source art;
do not change engine code or accept valid metadata as proof of visible alignment.
