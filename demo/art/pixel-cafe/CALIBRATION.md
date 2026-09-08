# Sunflower courtyard calibration repair

The revised pack uses four local PNG sources. Original garden and gardener atlases are retained. `flowers-v2.png` contains new generated foliage only; `planter-bases.png` is original code-authored geometry from `build-planters.mjs`, not an edit of the generated atlas. Run that script with Node to reproduce its 16 adjacency variants.

Each rigid base follows an exact 80×40 ground footprint with ten world pixels of height. The atlas uses two source pixels per world pixel. Neighbor variants remove internal retaining walls and caps. Two small foliage clusters sit on each soil surface; only foliage may overhang. Physical blocking stays on the host flowerbed entity. The cafe furniture uses a 120px width calibrated against measured chair-seat and tabletop landmarks. Its grouped solid footprint remains 2×2; sitting, walking between chairs, and walking beneath the umbrella are not implemented.

## Accepted foliage

Built-in image generation mode; accepted output `exec-a6336d71-bfcd-4954-b13b-8b551cee21a7.png`, copied to `flowers-v2.png`. Actual decoded dimensions: 1774×887, RGBA, alpha range 0–255. The source frames and offsets are in `../../pixel-cafe.ts`.

Prompt:

A transparent PNG game sprite sheet: three separate dense flower clumps in a horizontal row. Left purple irises and lavender, center orange and yellow marigolds, right white daisies. Beautiful richly detailed isometric pixel art, lush leafy green bases, tiny highlighted petals, warm upper-left sunlight, dark green outlines, fixed 2:1 game camera. Each clump is compact and round, with equal spread along both isometric ground axes. Flowers and leaves only, isolated on transparent background. These will be placed into separately drawn flowerbeds in a game. Three nonoverlapping sprites, generous empty margins. No pots or stone edging, no soil, no shadows. Wide image. Transparent background.

## Rejected candidates

Two earlier outputs contained baked checkerboard pixels and were RGB, so neither is used by the project. A targeted alpha-removal generation attempt also failed; a fresh transparent generation produced the accepted RGBA asset. This is why decoded output was checked rather than accepting the prompt's transparency request as proof.

First prompt:

Use case: stylized-concept. Create a new transparent sprite atlas of THREE botanical flower clumps for a real isometric pixel-art garden game. The provided garden atlas is STYLE reference only. Match its richly detailed purple irises, orange/yellow marigolds and ivory-white daisies, lush green leaves, warm upper-left lighting, crisp clustered pixels and dark leafy outlines. IMPORTANT: only flowers, their stems and leaves. REMOVE ALL stone edging, planter walls, pots, soil, grass ground, platforms and drop shadows. The game draws exact geometric planter bases separately. Each clump should have a broad natural LOW base of leaves tapering to a small planted root/contact region, seen from a fixed 2:1 isometric camera. Do not depict a solid rectangular flowerbox. Make them compact enough to sit on a single square isometric tile. Purple clump a bit taller, orange and white compact domed bunches. Leafy base is an equal-axis 2:1 diamond footprint, not a long rectangle. Three separate isolated sprites arranged in one horizontal row, evenly separated by generous transparent gutters: purple left, orange center, white right. Every flower fully inside its third of the canvas; no clipping. Canvas 1536x512 or a wide3:1image. No labels, text, borders, checkerboard, grid or other objects. Real alpha transparency. Preserve fine individual petals and leafy richness like reference, not simplified vector/cartoon blobs. This is an asset sheet, not a scene.

Alpha repair prompt:

EDIT THIS EXACT IMAGE: remove the entire gray checkerboard background and every gray checkerboard pixel visible between petals, leaves and stems. Replace all background with REAL FULLY TRANSPARENT ALPHA (alpha=0). This must be an RGBA transparent PNG, NOT an RGB image with a drawn checkerboard. Preserve the three flowers, their positions, colors, pixel details, size and canvas exactly. Do not add shadows, soil, planters, walls or any other background. Only extract these three existing flower clumps into true transparency. The current checkerboard is accidentally baked into the RGB file and is the defect to fix.

## Verification records

`art-contract.before.json` records the original failing planter measurement. `art-contract.json` and `measurement-notes.md` describe measured coverage, uncertainty, shared scale, and limits. They are authoring sidecars; runtime JSON uses the existing art manifest. The selectable **07 — Art calibration** scene exposes borders, a corner, a bare base, and furniture for real movement/occlusion review. Visual/gameplay acceptance is recorded separately in `../../../VERIFICATION.md`.

