# Complete sprite report

Run: live-e2e-20260920T223050Z-91b811
Status: completed_technical_gates_passed_visual_review_pending
Source SHA-256: 2ca54f300087f790fbc02f1e938ff979700a9e52077da07eff96c33fb6e4e18e
Reviewer: google/gemini-3.8-flash through OpenRouter, one real call, no fallback
Decision: approve candidate-01

## Concrete output

- Transparent atlas PNG: /root/services/animation-pipeline/artifacts/live-e2e-20260920T223050Z-91b811/atlas.png
- Manifest: /root/services/animation-pipeline/artifacts/live-e2e-20260920T223050Z-91b811/atlas-manifest.json
- Native GIF: /root/services/animation-pipeline/artifacts/live-e2e-20260920T223050Z-91b811/preview-native.gif
- Native MP4: /root/services/animation-pipeline/artifacts/live-e2e-20260920T223050Z-91b811/preview-native.mp4
- Manifest-driven preview: /root/services/animation-pipeline/artifacts/live-e2e-20260920T223050Z-91b811/animated-preview.html
- ZIP: /root/services/animation-pipeline/artifacts/live-e2e-20260920T223050Z-91b811/sprite-export.zip

## Exact animation geometry and timing

- Frames: 10
- Native source indices: 28, 33, 37, 42, 47, 52, 56, 61, 66, 70
- Normalized frame: 80x80 pixels
- Atlas: 658x166 pixels, RGBA with true transparency
- Playback: 6.382978723404255 FPS
- Cycle duration: 1.566666667 seconds
- Anchor: {"x": 0.5, "y": 0.9}
- Sparse sampling preserves the approved source interval duration; it does not replay at native 30 FPS.
- GIF delay is 157 ms/frame; HTML manifest playback is authoritative for the exact fractional FPS.

## Quality result

- Reviewer approved candidate-01 with no reported issues.
- Extraction provenance, cutout alpha/geometry, and atlas integrity/timing gates passed.
- Static atlas inspection found consistent identity/facing, no visible clipping, and no obvious matte halo at native scale.
- Visual quality remains explicitly uncertified: the static atlas cannot fully prove temporal jitter/seam quality, and edge behavior can vary by background.

## Cost and liability

- This reviewer call: USD 0.011538 known billed.
- Ten removals: USD 0.040 quoted; completed, charge not authoritatively returned, retained as open liability.
- Cumulative known billed in this ledger: USD 0.03742275.
- Cumulative open/ambiguous liability: USD 0.830032.
- Maximum accounted total: USD 0.86745475 of USD 1.00.

## Exact limits

- One northeast direction and one walk-like cycle only; no multi-direction aggregate.
- Existing WAN video was reused; no facing or video generation occurred.
- Reviewer evidence was a bounded 12-image sequence, not native video.
- MP4 is a convenience preview and does not retain alpha; atlas PNG and GIF retain transparency.
- The old USD 0.790032 ambiguous reviewer liability remains preserved.
- Public service policy, UI, game, global configuration, and deployment were not changed.

Trace: /root/services/animation-pipeline/artifacts/live-e2e-20260920T223050Z-91b811/TRACE.md
Ledger: /root/services/animation-pipeline/artifacts/live-e2e-20260920T223050Z-91b811/cost-ledger.json
