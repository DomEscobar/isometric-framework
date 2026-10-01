# Quellbrunn traveler: replacement character brief

Replaces the procedural `drawPerson` hero (`color === 0` in
[`render.ts`](../../render.ts)) with a packed, I2V-animated walk sheet. Villagers
(`color > 0`) are unaffected and keep the existing procedural draw.

## Identity (original character, not a licensed IP)

A young forest adventurer, ambiguous age (teens), slim build. Belted green tunic
over a cream undershirt, soft brown boots, a pointed forest-green cap over
shoulder-length blond hair, light leather satchel strap across the chest. No
weapons, no emblem, no crest, no named-character likeness. Palette stays inside
Quellbrunn's warm/earthy village range (see `art/provenance.json` cottage tones)
so the traveler reads as part of this village, not an import.

Camera: same fixed 2:1 isometric elevation as the existing village sprites
(cottage/oak/pine/shrub), full body, feet at the bottom edge of the crop, flat
contrasting background for clean extraction, generous margin, no ground shadow
baked into the art (the host draws its own contact shadow).

## Required facings

Only two independently generated facings, per
[directions.md](../../../../skills/directional-sprite-authoring/references/directions.md):

- **SE** (`D` key / `(c,r+1)`) — front, rightward silhouette. This is the
  runtime's default facing (`hero.facing === 2`).
- **NW** (`A` key / `(c,r-1)`) — back, leftward silhouette.

Screen `NE` and `SW` are **derived by horizontal flip** of `NW` and `SE`
respectively (documented compromise in directions.md); they are not
independently generated and are not counted as separate generated views.

## Action coverage

Walk only, one loopable cycle per facing (contact / pass / opposite contact /
pass). Idle is one already-approved walk frame of the current facing held
static (the most feet-together, weight-centered frame in the cycle, not
necessarily frame 0) — no separate idle generation, matching the "static idle"
allowance in
[asset-policy.md](../../../../skills/isometric-visual-loop/references/asset-policy.md)
only insofar as no animated-idle was promised for this host.

## Scale

Match the existing villager sprite's rendered footprint in `render.ts`
(`drawPerson`, roughly 20px wide by 46px tall at zoom 1) so the traveler reads
at the same scale as villagers and next to the cottages/trees already placed.

## Production route

Approved generated SE/NW stills -> image-to-video walk per facing -> review ->
alpha/cutout -> `extract-video.py` -> `pack-sprites.py` -> wired into
`render.ts`. No hand-authored gait frames. Provenance (source images, job IDs,
video hashes, extraction/pack manifests) is recorded alongside the produced
files in this folder.
