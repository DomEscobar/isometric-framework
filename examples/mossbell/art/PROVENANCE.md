# Mossbell artwork and sound

New original PNG candidates were created with the built-in image-generation tool
on 2026-09-10: bell-tree.png, apothecary.png, spruce.png, greenhouse.png,
fern-sheet.png and forest-materials.png.
Exact prompts are in PROMPTS.md; hashes and output identities in provenance.json.
Original files are retained without background edits or resampling. Alpha reports
and comparison boards are authoring evidence under test-results/mossbell/.

bakery.png is a copy of ../willow-quay/art/apothecary-source.png; bookshop.png is a
copy of that example's bookbinder-cutout.png. Their original prompts, generation,
and background-removal records remain in ../willow-quay/art/. They are credited
reuses, not new generated outputs. Relative paths here are from examples/.

The host imports Weidenkai's generated-material ground atlas/catalog and the
autotile lab's bed atlas/catalog, the autumn-crossing prop atlas (rocks, shrubs,
bench), and the demo pixel-cafe's gardener, flowers and garden atlases. Their source
records remain beside those packs. See the repository PROVENANCE.md and the
individual packs' notices. This example is portable with the repository or its
built browser output; copying this directory alone omits those shared assets.

forest-atlas.png and forest-frames.json are deterministic derivatives assembled
from forest-materials.png by prepare-forest.mjs; the source image itself is unchanged.
Water clips, small animals, mushrooms, signs, moonflower, light effects and
particles are original code-authored graphics. The main trees,
buildings, fern and shared decorative plants are generated raster art. No claim
is made that the generator produced the assembled maps, modular edges or all frames.

Sound is original Web Audio synthesis in audio.ts: filtered noise wind/water,
soft harmonics, owl/bird/insect tones, bell partials, and surface-dependent impact
tones/noise. No third-party recordings, music samples, remote audio downloads or
audio-generation provider are used. It is stylized procedural ambience, not field
recorded nature or a composed soundtrack.
