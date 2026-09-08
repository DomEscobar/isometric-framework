---
name: environment-topology-first
description: Trial workflow that establishes occupied cells, traversable surfaces and occlusion parts before binding isometric environment art and loops.
---

# Variant C: traversal and parts first

Sketch the assembly in `(c,r,level)`: solid cells, walkable surfaces, entrances,
passages, decoration and actor clearance. A bridge needs a deck floor, explicit
access links, ground-level supports, deck-level barriers, and open ground beneath.
Verify those routes using the public model before binding large artwork.

Split visuals at changes of floor or required front/behind ordering. Use unions of
rectangular blockers for irregular solids; a transparent opening in an image is
not a collision hole. Do not turn the whole bridge image into one solid rectangle.

Bind each part to one assembly origin using measured source contacts and a shared
pixel/world scale. Use the existing art-integration contract for the projection.
Then add decorative looping clips without changing physical footprints or using
wall-clock animation. Joined water pieces need compatible loop phase and edges.

Inspect the assembled fountain ground outline, animation while paused/resumed,
bridge access, and the underpass. Report real limits of the renderer rather than
inventing scene fields. Keep this task in host content; do not change the engine.
