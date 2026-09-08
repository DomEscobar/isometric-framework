# Weidenkai — pre-generation contract

Small playable district, not a full town: two houses, canal, bridge, planted
edges and two connected shores. Original architecture inspired by cozy detailed
pixel towns; no copied game assets. Shared warm limestone, muted terracotta,
sage foliage, blue-green water, upper-left daylight, restrained contrast.

- World tiles 64×32, 2:1 projection; c+ northeast, r+ southeast.
- Player standing height 44 world pixels. Door height target 54–66px.
- Houses: ground foundation 3×3 tiles, 192×96 diamond. Roof overhang allowed
  up to 16px beyond foundation; walls must stay within measured foundation.
- House art is exterior only; no interior entry or simulated awning ceiling.
  Ground reservations cover the conservative full foundation. The sidewalk is
  outside it; inspect actor occlusion on exposed front and side edges.
- Canal: ground rows7–8, water unwalkable. Bridge deck at32px, columns6–8,
  rows6–9, central walking column7; side rows in c reserve rail cells.
  Explicit entrance links at both ends. Water underneath is not a walking route.
- Bed stone height12px; source generated materials and exact shared geometry.
- Ground joins use shared generated material sampling; no unrelated full tiles.
- Visual tolerances: rigid contact fit target <=3px at world scale; facade
  slopes measured before acceptance. Source dimensions and landmarks are facts
  to record after generation, not inferred from this prompt.
- Necessary checks: image alpha and scale, near/behind building traversal,
  shore-to-shore crossing, water/building blocked, mobile held input, rendered
  close view of bridge/bank joins. Separate visual and physical verdicts.
