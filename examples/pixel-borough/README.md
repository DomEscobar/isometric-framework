# Pixel Borough

Open `/examples/pixel-borough/` on the checkout's Vite server. Click terrain to walk, use W/D/S/A (the framework's four tile axes), or use the mobile D-pad. Click a creature or its name to approach and greet it. Overview, Follow, Pause and Restart are available. Restart preserves camera mode and zoom.

This host uses the framework's public runtime, interaction and control APIs. No framework API changes. Five buildings, forest, meadow, fountain, markets, three original creatures and a bank-to-bank bridge form one playable town. There are no interiors or underpass.

All raster originals are in `art/originals/`, with exact generation requests beside them. The two checkerboard shop attempts remain as failed originals. `prepare-art.py` performs documented alpha extraction, cropping, nearest sampling and packing; `art/processing.json` records source/output hashes. Water movement is derived from the complete generated material using cyclic sampling; fountain frames retain fixed generated masonry. These are derived animations, not independently generated frames. No demo artwork is used. Two residents intentionally share this host's explorer art.

The initial 28–36 pixel actor calibration was visibly too small. Review repairs render the same packed explorer at width 72 (about 45–48 visible pixels tall), and creatures at width 67. New generated grass clumps and calmer ground replace the noisy materials. Original target and rejected sources remain unchanged.

The bridge has six authoritative stone deck cells at height 2, with generated rear/deck and front rail imagery at separate depth origins. It presents an arch but uses a shallow physical deck, not a curved collision surface. Water uses a thin full-map carrier with alpha only over the channel; this is a host workaround for a broad joined overlay's depth ordering.

Evidence and outstanding review live under `test-results/real-visual-session/`. Comparison-2 is a review checkpoint, not final acceptance. Static image comparisons do not certify motion or gameplay. The generated source still has finer foliage texture and a narrower foreground bank than the target; inspect the fresh captures before approving these tradeoffs.
