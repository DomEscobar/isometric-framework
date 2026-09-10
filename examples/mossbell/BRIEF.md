# Mossbell / Bellshade

## Intent
Two connected, complete explorable isometric worlds: a little inhabited town and
a lively forest. Pokemon-like discovery and Witchbrook-inspired atmosphere are
style references, not replica layouts. User selected twilight with a stronger
mysterious glow. All content belongs to this host; use public framework APIs.

## Art direction and scale
2:1 projection, 64 x 32 tiles. Detailed clustered pixel art, nearest sampling.
Reference traveler feet-to-head 44 world pixels; doors approximately 52-64px.
Amber lamps and peach stone in town; muted violet and deep teal in the forest,
with concentrated cyan spring light. Keep traversable paths lighter than foliage.
Buildings have conservative 3 x 3 solid exterior footprints; no interiors.
Tree trunks block one cell, crowns deliberately overhang. Reserve clear routes.

## User refinement: animation and sound are core requirements
Before further asset production, design convincing environmental motion and an
atmospheric soundscape. Realistic motion means plausible local movement within
the pixel-art style, not photorealistic rendering. Existing tree/cottage PNGs are
static source candidates, not completed animated assets. The bell tree's painted
bells, canopy and lights need layered or authored-frame treatment where animated.

Motion priorities: directional stream flow with bank-local ripples; spring rings
and soft light pulses; rising/dissipating chimney smoke; bell pendulums with fixed
attachments; branch-tip/leaf movement with fixed trunks and roots. Vary local
timing and leave resting intervals. Never stretch or slide an entire rigid prop
to claim foliage animation. Fireflies move independently and cannot stand in for
water or tree motion. Creature motions use readable idle/action beats.

Sound priorities: soft town evening bed, forest wind/insects/distant owl, positional
stream/spring/bell layers, surface-dependent footsteps and restrained interaction
sounds. Smooth town/forest crossfades, distance attenuation relative to the player,
no abrupt loop seams or identical simultaneous accents. Sound starts on an
explicit user gesture; visible mute and separate ambience/effects levels. Pause
freezes simulation and suspends its sound; tab hiding silences audio. Own and
dispose all audio nodes/listeners in the host. Record audio origins and licenses;
do not describe synthesized tones as recorded natural ambience.

Calibrate one integrated scene with traveler, moving water, fixed tree roots and
moving bough/bell accents, plus corresponding sound. Review an actual full loop
and its audio before expanding those families to both worlds. This is a milestone,
not a reduction of the full two-world deliverable.

## Full layout
Mossbell: five buildings, cobbled square, bell tree, flower/herb gardens, stream,
walkable stone bridge, a few inhabitants and cat, woodland exit.
Bellshade: winding paths with two loops, same stream, log crossing, herbalist
shelter, moss/ferns/mushrooms, woodland creatures, ancient tree and glowing spring.
Transitions work both ways, preserve the seed/story state and use a short fade.
Proposed supporting play: investigate spring, receive seed, return and plant it.
The final bloom provides a visible ending; exploration remains available.

## Assemblies and motion
Stone bridge: raised surface, explicit cardinal access links, blocked water,
solid abutments and rails. No walkable underpass. Log crossing uses supported
walkable terrain and matching authored contact geometry.
Water shimmer and directional highlights, smoke, bell accents, foliage accents,
fireflies and spring pulse use simulation elapsed time and freeze on pause.
Creature movement is bounded host behavior. No combat/capture system.

## Production sequence
Calibrate representative house/tree, traveler and bridge in game; expand both
maps, implement transition and short interaction, add environmental motion,
inspect full views and routes on desktop/mobile, fix visible defects.

| Outcome | Evidence | Status |
| --- | --- | --- |
| Complete village and forest composition | v4 desktop/mobile captures; independent static review | Complete |
| Bridge, log and paths | Town 15/15 and forest 12/12 assembly assertions; played routes | Complete |
| Two-way connection and persistent story | Desktop/mobile town-forest-town journey and reload | Complete |
| Water, ambient life and spring motion | Advancing pixels, named clips and pause equality | Complete |
| Convincing local motion with stationary structures | Water/fern clips plus host smoke, bells, leaves and fireflies | Complete with static source canopies |
| Atmospheric sound and scene crossfades | Captured non-silent town/forest WebM mixes and spatial signal checks | Functional; human listening pending |
| Audio controls and lifecycle | Gesture enable, mute, independent levels, pause and owned teardown | Complete |
| Consistent art and readable traveler | Alpha reports, art contract and independent static review | Complete with documented path/repetition limits |
| Production load, types, browser errors | Final build and focused browser report | Complete |
| Performance | Four browser/renderer comparisons against blank baseline | Complete; emulated mobile hardware |
