# Witchhollow Tactics — Production Brief

Authoring data only (not scene JSON). Recording follows the framework's
production-brief outline.

## Intent and scope
A finished playable demo: one polished tactical battle, 4v4, core slice
(move/attack/guard/wait, height advantage, win/lose/reset). Fully authored
pixel art, $0 budget. Cozy witch-academy identity, original assets only.

## Art direction
- Reference: none attached; style chosen jointly (cozy Witchbrook-inspired,
  original). Reference role: style vibes only, not a layout to copy.
- Projection: 2:1 isometric, 72×36 tiles, nearest sampling.
- Working pixel scale: 1 source pixel = 1 tile pixel (tiles authored at 72×36).
- Palette: cream academy stone (#e8d9b0 family), moss greens (#7fa06a family),
  soft teal water (#6ec2c9/#2f7f8a), warm amber accents, dark slate outlines.
- Lighting: warm upper-left; consistent shaded faces on every prop/unit.
- Player scale: witches ~44-56px tall; familiars ~28-38px.
- Visual hierarchy: units pop above calm terrain; fountain and dais are the
  strongest landmarks.

## World layout (single battle map, 8 columns × 7 rows)
- Academy door + courtyard paving: south-west corner (team "Bramble team" start).
- Worn grass paths across the middle (main lanes, widening at junctions).
- Crumbled fountain at map center (water flows, animated).
- Stream at the north-east edge with wet banks (blocked water; crossing via
  stepping stones visual, no crossing needed).
- Raised dais (elevation +30) at the north-west with steps; height advantage.
- Enemy "Ember team" starts north-east.
- Regions: yard (paving), meadow (grass), bank (wet), dais (stone).
- Ground only required pairs: paving/grass, path/grass, grass/bank, bank/water,
  stone/grass. Variation must span cells; no tile stamps.

## Assemblies
- Dais = 2×2 raised area with side textures and 2-step approach; walkable top.
- Fountain = multi-tile assembly (basin base + animated water overlay) with a
  blocking collider matching the basin.
- All props: separate colliders; decorative sprites nonblocking.

## Motion
- Stream: flowing water overlay along the channel (2-4 frames, stable loop).
- Fountain: splash loop on the basin.
- Foliage: sway frames at varied cadence (few props, not every tuft).
- Units: idle/walk cycles all 4 axis facings; hit flinch; cast wind-up/release.
- Pause must freeze all scenery.
- Static scope note: no weather particles outside battle effects.

## Production order
1. Contract + brief + acceptance plan (now).
2. Calibration: witch actor (idle+walk NE/SE/SW/NW), terrain patch (path into
   grass + stream edge), one prop (fountain basin + water loop).
3. Full ground (continuous canvas → 56 aligned tiles + dais + variations).
4. Remaining props, all unit models (2 witches + 2 familiars, team palettes).
5. Battle rules + UI overlay (turn banner, command menu, move/attack ranges,
   damage numbers, win/lose).
6. Accept: browser playtest desktop + mobile, screenshot compare/repair,
   acceptance gate (visual/motion/gameplay/performance), report unverified.

## Completion table (updated as evidence arrives)
| Required outcome | Owner | Evidence | Status |
| --- | --- | --- | --- |
| Continuous ground, no stamps | terrain.py + scene.ts | ground-only capture | planned |
| Stream + fountain animation | anim frames + overlay | motion capture, pause | planned |
| Units readable, 4 facings walk/idle | sprites.py + manifest | packed-art inspect + capture | planned |
| Move/attack/guard/wait + height | battle.ts | playthrough captures | planned |
| Win/lose/reset | battle.ts + UI | playthrough captures | planned |
| Desktop + mobile playable | main.ts + CSS | both viewports | planned |
| Acceptance gate | verify-world.py | receipts | planned |
