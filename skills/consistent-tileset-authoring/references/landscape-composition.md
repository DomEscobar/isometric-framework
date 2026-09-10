# Compose connected ground before cutting tiles

Use for natural paths, grass transitions and stream banks. The examples below
describe methods and illustrative dimensions; they supply no artwork or theme.
Keep deliberate paving grids and formal canals when the user's brief calls for
them. Natural edges are not a universal requirement for every material.

## Establish the landscape contract

Put these decisions in the host's existing production brief, alongside its style
reference. Do not create a second competing project contract.
Protect the relevant acceptance requirements before implementation, including
the ground-only views below. Calibration comes next; it is not permission to
postpone defining acceptance until the completed world is ready for review.

| Decision | What to describe or measure |
| --- | --- |
| Connected shapes | Path/channel route, width changes, bends, junctions, clearings and walkable clearance |
| Material adjacency | Which pairs actually touch: path/grass, soil/grass, water/wet bank, bank/grass |
| Transition treatment | Worn earth, interlocking grass clusters, exposed bank, stone edge; breadth and contrast at game scale |
| Pixel treatment | Shared pixel density, cluster size, palette ramps, outlines, shading and lighting |
| Variation | Broad patches spanning cells, edge variation and sparse landmarks; keep traversable surfaces readable |

For pixel art, a soft material transition can use crisp, interlocking clusters
and intermediate palette colors. It does not require blur, translucent noise or
antialiasing that conflicts with the selected style. Reject a different cluster
scale or rendering style at the boundary even if both assets use similar greens.

## Author regions and shared boundaries

1. Compose the route and surrounding ground at the scale of the whole patch.
   A natural path can widen at a junction and narrow beside a bank. A channel's
   two banks follow the same course; avoid stamping identical diamonds end to end.
2. Define each material boundary once in host-owned world coordinates. Neighboring
   pieces share its position, transition width and edge samples. Do not independently
   randomize the two sides or restart the pattern at every tile origin.
3. Separate connectivity from surface variation. A neighbor mask selects a shape;
   compatible alternate artwork varies its interior without changing required edge
   contacts. Large color/texture patches should continue across several cells.
4. Place distinctive pebbles, tufts and worn spots sparsely according to the region.
   Uniform per-cell noise or a mirrored feature on every tile still reveals the grid.
   A deterministic seed makes output repeatable; it does not make it well composed.
5. Derive the visible ground and navigation from the same host layout. Decorative
   fringe can overlap a boundary, but it must not imply a walkable route through
   blocked water or obscure the usable path. Validate crossings with the actor.

These are authoring responsibilities, not additional runtime scene fields. Select
an implementation that fits the host:

- **Compatible transition tiles:** author the needed material-pair edges, bends,
  ends and junctions with shared contacts, plus compatible interior alternatives.
  A binary occupancy mask does not identify which other material lies outside it.
- **Composed ground patches:** assemble or paint the host's material regions first,
  then export measured tile crops or bounded ground pieces. Preserve shared world
  origins through extraction. Keep raised surfaces, foreground props and occluding
  structures separate so their depth and collisions remain correct.

Both approaches can use generated material sources if that is the agreed technique.
Do not generate every whole tile independently and expect matching edges. The
raised-bed helper supplies rigid rims and walls; it does not implement natural
path fringes, bank transitions or a general terrain compositor. If the host lacks
the chosen assembler/catalog, implement that scoped authoring work or report the
gap. Producing its existing bed tiles is not completion of an organic-ground brief.

## Neutral calibration patch

For example, use a 12×8-cell patch with a path bend, a widening junction, open
grass and a stream bend alongside the path. The dimensions are illustrative;
fit a useful camera view and the current game's player proportions. Include only
material pairs required by the real scene; do not invent a water feature for a
path-only repair. A generic strip/L/hollow test remains useful for topology, but
cannot replace this mixed-material composition.

Inspect the ground with optional props hidden. A worn path edge should interrupt
its contour with coherent grass/earth clusters, while the interior stays readable.
The stream should have a continuous water-to-bank boundary through its bend and
a separate bank-to-grass transition where required. A dry ledge or bridge approach
must meet that same bank geometry; overlapping decorations cannot hide a gap.

For a sampled boundary shared by two exported pieces, compare the same world-space
contact points at the final scale. Then inspect the visible result: exact endpoint
agreement does not prove matching transition width, palette or texture rhythm.

When the patch passes, carry its edge rules and material family into the full
environment. Recheck the overview: one acceptable bend does not certify an entire
map of repeating banks.

## Terrain acceptance evidence

Keep these as explicit requirements in the existing acceptance plan when the brief
requests natural ground. Give each a `pass`, `fail` or `unverified` verdict and a
specific observation. Do not bury terrain inside a generic "cohesive style" score.

| Requirement | Required observation | Fails when |
| --- | --- | --- |
| Ground composition | Ground-only capture at playing zoom and wider overview | Identical diamonds, mirrored motifs, alternating color cells or evenly spaced tufts dominate a surface intended to look continuous |
| Material transitions | Close view of a bend/junction and each relevant material pair | Natural path ends in a uniform hard rim; boundary widths or contacts jump at cell edges; style or pixel density changes across materials |
| Integrated readability | Restore props; inspect the actor on the path, bank and crossing | Decoration hides defects, obscures the route or suggests traversal through blocked geometry |
| Flow and bank continuity, if animated | Playback through bends and joins, wrap and pause | Foam/ripples restart per tile, bank pixels wobble, exposed gaps appear in motion or flow crosses the bank |

Supply the reviewer with the reference's intended role, ground-only and dressed
views at matching zoom, and complete motion evidence where applicable. Ask it to
identify the most visible repetition and worst transition, even when the overall
scene looks pleasing. A landmark, palette match, asset count or valid atlas cannot
override a failed terrain requirement. Preserve failed views and recapture after
repair. The existing acceptance tool checks declared coverage and freshness; it
does not automatically recognize these visual defects.
