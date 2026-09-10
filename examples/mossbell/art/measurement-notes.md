# Art and motion measurements

Targets were recorded in ../BRIEF.md before composition: 64x32 projection,
44px traveler, approximately 52-64px doors, conservative 3x3 building bodies.
These annotations were refined after observing the live calibration and are
retrospective measurements, not independent proof of a generated camera.

The apothecary's visible base was observed near source (210,990), (1122,990),
and (650,1178). At width266 its lateral span is about193.5px. The front corner
is about40px below the side contacts, less than the canonical48px diamond.
The anchor uses(.524,.79), plus the host's64px footprint-center offset.
The footprint conservatively encloses the shallower base; the art has not been
sheared to force a perfect diamond. Doors and stairs are exterior dressing;
none of the buildings claims an accessible interior.

The greenhouse uses width258, anchor(.51,.723), and the same center offset.
Its visual footprint is conservatively enclosed by3x3 cells. Its source was
visually inspected, but it is not included in the narrow PNG checker contract.
The reused bakery and bookshop keep Weidenkai's measured source anchors/scales.

The bell tree's trunk contacts, rather than its spreading roots or leaf outline,
are the collision reference. Trunk correspondences are inferred containment.
Root and canopy overhang is intentional. Large trees remain static source sprites;
additional authored pendulum bells move, while the bells painted in the source
remain static. Ferns and falling leaves supply independent foliage motion.
This is not a fully articulated tree-canopy simulation.

Fern source is1254x1254 with four627x627 cells. Visible root centers are around
(310,548) relative to each cell; shared anchors and width46/53 keep the bases
stable to approximately1 game pixel. Two clips vary cadence and frame order.
The source poses have some leaflet shape variation: they are generated poses,
not physically simulated interpolation. Final frame returns to first in each loop.

Water uses12 authored transparent64x32 sprite frames at5fps (2.4 seconds).
All modules load together, share phase and move highlights along c+. Water
walkability belongs to terrain; the overlay bodies are1px and depth sorted.
Bridge rails/banks use their full80px source width: using64 incorrectly reduced
their measured geometry and left gaps. Rails are24px high; bridge deck32px;
16px stairs and blocked24px abutments prevent an unsupported underpass.

Smoke uses five particles with sinusoidal opacity and expanding radii; no chimney
pixels move. Bells pivot at fixed attachments. Spring rings use continuous phase.
All elapsed motion freezes with the runtime. Source alpha includes near-opaque
interior pixels and faint edge noise; source PNGs are preserved unchanged.

Actor artwork reuses the calibrated four directional idle/walk clips from the
garden. Combined inputs intentionally reuse their nearest authored facing. No new
dedicated picking/casting or jumping artwork is claimed; interaction timing uses
the public controller and a grounded facing pose.
