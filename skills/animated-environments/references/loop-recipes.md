# Loop recipes and limits

| Environment | Stationary contract | Moving region and seam |
| --- | --- | --- |
| River | Banks, grid contacts, water coverage | Ripples/foam follow the projected flow vector. Compare adjacent edge pixels at matching phases; a repeated shimmer does not prove downstream flow. Bend and junction modules need their own compatible edges. |
| Large fountain | Basin corners, rim, stem and bowls | Animate water inside the basin and approved spray silhouette. Use identical stone pixels or separate overlays. Model low basin and tall central stone as separate solids. |
| Waterfall | Cliff lip, pool and drop height | Vertical ribbon plus downstream foam. Match ribbon end/start, keep cliff collision independent. A tall image is not a walkable slope. |
| Wind in plants | Trunk/root and rigid planter | Move leaves around the fixed root; preserve nearby path clearance. Random phases suit separate plants, coherent phase suits connected geometry. |
| Steam or lanterns | Pot/lamp contact and body | Loop wisps or glow without shifting the fixture. Local alpha blending is visual; no built-in lighting simulation is implied. |

For one calibrated pixel-art loop, four or eight intentionally authored frames
can be sufficient. Select rate/count for the requested look, not from a universal
preset. The challenge uses four frames at four FPS merely for fast comparison.
Its river is surface shimmer, not a tested directional-flow field.

A final frame need not duplicate the first: that often creates a pause. Inspect
last-to-first at playback speed and in a contact sheet. If a large fountain must
occlude an actor differently across its front/back, split rigid and effect layers
at useful depth anchors. This runtime sorts entities by grid origin within each
floor, so arbitrarily overlapping transparent overlays are not a depth solution.

Minimal current binding (image and named frames must also exist in the manifest):

```ts
assets.animations.ripple = {
  frames: ['water-0', 'water-1', 'water-2', 'water-3'], fps: 4, loop: true,
};
entityTypes.waterEffect = {
  blocking: false,
  visual: { kind: 'sprite', animation: 'ripple', width: 64 },
};
```

Use each frame's calibrated anchor. Here `width: 64` is only appropriate for the
64-pixel fixture; never copy that number onto unrelated source art. Omit an
irrelevant body height for decoration instead of specifying zero: explicit
`bodyHeight` values must be positive.
