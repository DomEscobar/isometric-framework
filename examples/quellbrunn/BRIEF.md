# Quellbrunn — geometry first, full village

User instruction: build the village directly, following the agreed geometry-first approach. This authorizes implementation now; the earlier planning discussion supplies the concept and style. Do not ask for a second contract approval.

Deliver five cottages around a broad village square, gardens, tree groups and two bridges across a winding stream. Original pixel-art direction follows the user's forest reference: coherent grass/earth connections, readable outlines and warm materials. New generated cottage/foliage artwork is local to this host; no example artwork is reused. Built-in ImageGen is the already selected provider, with no new chargeable third-party calls.

The same world-space terrain and footprint definitions govern drawing, clicks and movement. All dry ground is traversable except actual occupied building/root/garden/rail footprints. The visible paths are decoration on that traversable ground, not narrow invisible navigation tubes. Bridges have explicit deck surfaces and rails. There are no claimed interiors, underpasses, stacked floors or combat.

Flowing water must be obvious at default playing scale: the colored water surface itself moves down the channel, with substantial traveling wave/foam structures. Add a turning mill wheel, chimney smoke, anchored foliage motion and three walking villagers. Pause freezes these along with the controlled traveler. Preserve four isometric keyboard axes and pointer/touch path selection, pan/zoom and overview.

Geometry: world 48x40 coarse cells; projection32x16px; navigation sampled at quarter-cell resolution. Actor height34–38 world pixels, feet radius0.22cell; cottage rigid base nominal5x5cells, doors at least42px high. Source contact measurements must establish compatible cottage projection before expansion. Foliage may overhang paths but roots cannot occupy circulation. Target rigid reprojection error<=4px at game scale; do not silently stretch assets.

Acceptance: test arbitrary points across the full visible path width, many independent dry-ground samples, both complete bridge crossings and all house approaches. Tests may not rely solely on the host's own canStand predicate or a curated tour. Independently inspect actual images and timed motion at default zoom; a changed frame counter or tiny glint does not prove flowing water. Formal acceptance remains distinct from the user's evaluation.
