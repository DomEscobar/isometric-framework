# Witchhollow Tactics — Project Contract

Status: AGREED 2026-09-10 (user: "go with reco"; no style image attached).

## Concept
A Final Fantasy Tactics–style tactical battle demo in original cozy witch-academy
pixel art inspired by the *vibe* of Witchbrook (cottagecore academy, warm light,
rounded expressive characters). Not a copy of Witchbrook or any bundled example
artwork; every asset is newly authored for this game.

## Scope (agreed selections)
- Q1 = A: one polished battle on one compact battlefield (~8×7 grid), 4 vs 4.
- Q2 = A: core tactics slice — grid movement with move ranges, facing, turn
  order, one melee + one ranged spell, height advantage, guard, win/lose/reset.
- Q3 = A: fully authored pixel art at $0 budget. No paid generation.
- The earlier catching-loop is preserved as *familiars*: creature companions
  with leaf/ember/dew affinities.

## Host
- New self-contained game at `examples/witchhollow-tactics/` in the framework
  checkout (own scene, rules, art, HTML/Vite entry).
- No engine changes unless a real capability gap appears.
- No example art, names, palettes or content reused; provenance recorded per asset.

## Art contract
- 2:1 isometric, 72×36 world tiles, nearest sampling.
- Warm upper-left light; cream academy stone, moss greens, soft teal water,
  warm amber accents.
- Continuous landscape: composed ground canvas (courtyard paving → worn grass
  path → stream bank) sliced into aligned tiles; ground approved with props
  hidden before decoration.
- Units ~48–56 px tall, feet anchored at (0.5,1); directional frames
  (ne/se/sw/nw) for idle and walk; equal canvas; consistent cluster size and
  shading across materials.

## World
- One battle map: courtyard paving by the academy door, worn grass paths, a
  stream edge with animated water, a crumbled fountain, raised dais for height
  advantage.

## Gameplay
- Turn order banner; per-unit commands Move / Attack / Guard / Wait.
- Move: reachable-tile highlight; Attack: melee (adjacent) + one ranged spell
  (ember spark / leaf bolt) with damage numbers and hit effects; Guard halves
  incoming damage; height advantage +25%; win/lose/reset/replay.
- 4 player units (2 apprentices + 2 familiars) vs 4 enemy units with leaf/ember/
  dew affinities and type effectiveness.

## Production order
1. Host skeleton + contract + acceptance plan (this file).
2. Calibration: our own actor, one terrain patch, one prop, one animation loop.
3. Full ground + map.
4. Units, sprites, battle rules.
5. Polish, browser playtest (desktop + mobile), screenshot compare/repair,
   acceptance gate, honest report of unverified requirements.
