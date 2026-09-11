# Working on this game

`PROJECT_CONTRACT.md` is the single source of truth for human requirements. Update it only after the owner agrees to a changed requirement.

This is a neutral technical calibration, not a finished game and not an art direction. Keep maps, rules, UI, assets, and generated artwork in this host. Do not copy artwork, palettes, names, or layouts from framework examples.

Before adding a world or commissioning/generating art, read the installed framework guides in `node_modules/isometric-framework/docs/CREATE_GAME.md` and select the relevant workflows in `node_modules/isometric-framework/skills/`. For a substantial world, begin with `isometric-visual-loop/SKILL.md` and complete its acceptance evidence. Use the public `isometric-framework` package exports; do not import package internals.

Run `npm run build` for host type/build verification. Play the affected journey in a browser before describing an interactive change as verified.
