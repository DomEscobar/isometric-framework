# Grounded environment workflow review

The September 10 review found an ownership gap rather than a missing tileset
algorithm. Ground transitions were already described, but production guidance
still encouraged isolated objects, independent materials and late decoration.
Correct contact metadata did not ensure that objects visually belonged to the land.

## Keep, change, remove

| Guidance | Decision and reason |
| --- | --- |
| Shared semantic layout, source provenance, public APIs | Keep: visible terrain and actual traversal need the same source of truth. |
| Actual reference/current inspection and post-repair captures | Keep: these found real defects that functional checks missed. |
| Ground-only inspection | Keep as one diagnostic view; retain root beds, wear and banks that belong to ground composition. Also inspect the dressed contact zone. |
| Isolated cutouts with no soil or shadows | Make conditional on asset role. Rooted scenery needs a planned ground connection; portable objects may need separate shadows. |
| Terrain topology before all other work | Choose only when producing a reusable tile family. A composed ground patch need not start with 47 masks. |
| Separate repeated contracts/checklists | Reuse the host brief and existing evidence; put contact treatment in it rather than creating another schema. |
| Generic visual-loop entrypoint containing specialist details and a numeric replica score | Shorten and route specialist details. Use located defects against the actual target, not arbitrary beauty-score thresholds. |
| Seedream-specific pose preference and unconditional provider-reference reading | Remove provider bias from general instructions; read only the selected provider's recipe. |
| Mandatory jump checks in directional work | Restrict to games/actions that support jumping. |
| Named trial/example references in skills | No such art dependency is needed. Keep this historical review outside skills; examples in skills remain illustrative and self-contained. |

## Production unit

Calibrate an object together with the ground it affects: for example a trunk,
root bed and grass edge; a threshold and worn approach; or a stream bank and its
water contact. Their visual layers may be separate runtime assets. Shared design
does not mean flattening foreground geometry, actors or collision into a picture.

Review physical support and visual connection separately. Grass cannot disguise a
gap under a building. A correct collider cannot make a pasted-on sprite look rooted.
Walkable surfaces need visible feet at near/middle/far positions. Interactions need
the actual arrival poses from relevant routes, including approaches from another
landmark, not only one favorable starting position.

## Application

Apply these criteria to focused repairs of ground-contact art, shared path/bank
contours, readable crossing surfaces and interaction arrival poses. Preserve any
earlier trial evidence separately from the repaired host. Record reused artwork,
new generation and deterministic composition explicitly, and keep the project's
approved style reference and provider decisions.
