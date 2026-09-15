# Untitled isometric game

Install dependencies with `npm install`, then run `npm run dev`. Use `npm run check` for TypeScript and `npm run build` for the production bundle. The framework is vendored under `vendor/` so this project does not depend on a published package version.

Read `PROJECT_CONTRACT.md` before changing the game.

Production uses the version 4 workflow in
`node_modules/isometric-framework/skills/isometric-visual-loop/`. Follow its asset
policy and six stages. From this host, with Python/Pillow installed:

```sh
python node_modules/isometric-framework/skills/isometric-visual-loop/scripts/verify-world.py production next review/baseline.json --receipts review/receipts
python node_modules/isometric-framework/skills/isometric-visual-loop/scripts/verify-world.py accept review/baseline.json review/candidate.json review/final/review.json --production-receipts review/receipts
```

Create those files through the documented freeze, stage and comparison commands;
they are project-specific, not supplied completion records. Build success only
establishes technical validity. Production acceptance additionally needs generated
asset provenance, image-to-video character animation evidence and actual visual,
motion and gameplay review. Video preparation also requires ffmpeg/ffprobe.
