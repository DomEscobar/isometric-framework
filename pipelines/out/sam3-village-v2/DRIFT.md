# Village v2 drift check (numbered markers)

Spent: 0.062 USD (plate+deco+8xSAM). Cap ok.

Findings:
- Numbered diamonds rendered on plate-marked.png.
- Muse still drifts: pine/house/etc. not always on grid feet (see overlay-feet-v2.png).
- Objects are distinct and recoverable via candidates + AI assign (8/8).
- Grid-foot SAM alone still fails for some ids (empty_near_foot); class-mask + remap remains required.

Navigator: out/sam3-village-v2/index.html
