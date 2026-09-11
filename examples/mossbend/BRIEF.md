# Mossbend: image-to-image environment experiment

Authorized experiment: make one complete small playable forest image from an
engine-rendered layout and the user's forest style reference, then preserve its
pixels while separating game layers. This is a technique experiment, not the
previous town/forest game or a claim to have finished a full game.

- New host and original artwork; no existing example art or names reused.
- Provider: Retro Diffusion MCP, RD Pro Edit for the scene. Estimate every paid
  operation. Internal spending ceiling $2 for this initial experiment; report
  actual charges, generation count, elapsed time and manual corrections.
- 256 x 224 native scene pixels, 20 x 10 projection, fixed camera. Enlarge with
  nearest-neighbor sampling. User reference owns style/material relationships;
  engine guide owns map geometry, crossing and root locations.
- One forest clearing, winding stream, one low wooden crossing, connected dirt
  route, six trees, a small stump/flower destination. No buildings or combat.
- Generate scenery together. Separate existing pixels into foreground objects;
  inpaint hidden ground only. Retain originals outside exact edit masks.
- Ground owns roots/soil/contact shadows. Water motion stays within a fixed
  water mask. One original small controllable traveler tests routes and occlusion.
- Pass criteria: coherent clusters and material transitions; crossing and routes
  match guide; actor visible on deck and depth-sorted at trees; blocked water;
  observed stable water cycle and pause; usable desktop/mobile view.
- Preserve failures. Do not silently move gameplay geometry to excuse generation
  drift. Focused version-2 comparison records this bounded technique test; it is
  not full-world version-3 production certification.

Executed limitations: the initial author-made guide erroneously planted oak-mid
on a water cell. The corrected current layout moves it to (1,3); original guide
evidence remains frozen. Four generated source trees are manually extracted and
reused for six placements after whole-image generation omitted two. The traveler
is a neutral built-in diagnostic actor. Water is authored surface shimmer. These
are explicit experimental limitations, not a retrospective visual acceptance.
