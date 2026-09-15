# Sunflower courtyard artwork

The current calibrated revision is documented in [CALIBRATION.md](CALIBRATION.md).
It retains the original sources below and adds separate foliage and exact
code-authored stone bases. Use the measured contract and playable calibration
scene when modifying the pack; the original planter sprite is a failure example.

Generated with the built-in image-generation tool for this playable demo. Original artwork inspired by the supplied garden reference; it is not a recreation of its exact assets. Two local PNG atlases provide the terrain, props, and gardener. No external image service is called at runtime.

Source outputs were copied from the Codex generated-images directory into this folder. Frame rectangles, anchors, and animation mappings live in ../../pixel-cafe.ts. The generated layout needs manually inspected metadata; do not assume the requested canvas dimensions or perfectly uniform gutters.

## Garden atlas prompt

Use case: stylized-concept. Asset type: transparent pixel-art sprite atlas for a real isometric game, NOT a screenshot.
Create ONE polished 2048 by 2048 pixel image. Uniform strict 4-column by 4-row grid of sixteen equally sized 512x512 cells. No grid lines, labels, letters or UI. Background truly transparent alpha. Every object isolated entirely inside its own cell with at least 24 pixels transparent margin. All art consistent cozy detailed 1990s/2000s isometric garden/cafe game pixel art, rich clustered pixels, crisp stepped contours, fine highlights, subtle dithering, dark warm outlines, no smooth vector shapes, no blur. Reference mood: intimate terracotta courtyard surrounded by dense purple, white and orange flowerbeds, wrought iron, wood furniture and golden parasols. Camera fixed 2:1 isometric top-down view, parallel orthographic, light from upper left. Preserve coherent relative prop scale.

Strict cell contents reading left to right, top to bottom:
Row 1: (1) inviting golden-yellow round fringed café parasol over a small square wooden table and two wooden café chairs, complete grouped furniture sprite, no ground tile; (2) separate elegant wooden slatted cafe chair facing toward lower right; (3) matching wooden slatted cafe chair facing lower left; (4) large terracotta planter full of tiny yellow-orange flowers and green leaves.
Row 2: (1) dense lavender/purple iris-and-violet flowerbed in a low sandstone edged rectangular isometric planter, blooms crowded and detailed; (2) matching flowerbed with marigold-orange and golden-yellow blooms; (3) matching flowerbed with creamy-white blooms and lush foliage; (4) lush rounded small green shrub in a ceramic pot.
Row 3: (1) low decorative brown wrought-iron railing segment aligned diagonally from lower-left to upper-right; (2) matching railing segment aligned diagonally upper-left to lower-right; (3) slender ornate amber/gold garden lamp post with round reddish lantern cap, entire tall post and footing visible; (4) leafy tropical palm in a rounded terracotta pot.
Row 4: (1) a single seamless 2:1 diamond top-face tile of small warm terracotta paving bricks, realistic isometric grout pattern, no side walls; (2) a 2:1 diamond tile of lush bright garden grass with tiny clover details, no side walls; (3) a 2:1 diamond of honey-colored timber deck planks, no side walls; (4) a 2:1 diamond tile of pale warm sandstone paving, no side walls.

All four terrain diamonds have tips at x=24 and x=488 and y=140 and y=372 within their cell, filled fully to their diamond boundary, transparent outside. All twelve prop sprites centered horizontally with ground contact near y=472 within their cells, soft tight pixel-art contact shadow only. No overlapping between cells. Produce usable beautifully detailed coherent sprite artwork. Transparent background, not a checkerboard drawn into pixels.

## Gardener fixture

The checked-in gardener atlas predates the version 4 character-production policy.
It remains only so this runtime demo can exercise directional clip selection and
playback. Its retired direct-sheet request is intentionally absent and must not be
used as a production recipe. New or replacement character motion must begin with
approved generated directional facings and follow the I2V extraction workflow.
