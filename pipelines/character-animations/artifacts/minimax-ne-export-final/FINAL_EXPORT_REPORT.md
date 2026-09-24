# Final MiniMax NE export report

Status: real transparent export created; visual inspection remains evidence-bound, not a perfection claim.

## Source and selection

- Source: artifacts/minimax-ne-source-01/provider-original.mp4
- Source SHA-256: cd02ae6369794274e49df2253ee8c5b100d7192ba9a5c5c94d98fe59a41e42dd
- Candidate: candidate-01-66-98, native [66,98), 1.333333333 s.
- Source label: human-reviewed exact 160px source preview; not automatic gate certification.
- Selected original frames (24): 66, 67, 69, 70, 71, 73, 74, 75, 77, 78, 79, 81, 82, 84, 85, 86, 88, 89, 90, 92, 93, 94, 96, 97.
- Playback: 18.000000000 FPS, preserving the reviewed interval duration.

## Processing

- Actual WaveSpeed image-background-remover outputs downloaded for every selected original frame.
- Full-resolution RGBA cutout masters preserved in master-cutouts/.
- 80px and 160px variants each derive directly from the full-resolution master with one premultiplied-alpha Lanczos downsample.
- Shared source root/scale per resolution; no per-frame recentering or scale changes.
- Only alpha 1..7 resampling fringe is cleared; no connected components/anatomy are deleted.
- Runtime: native 160px recommended for retained detail; 80px is a compact variant. Display uses nearest-neighbour at integer scales only.

## Deliverables

- 80px atlas: atlas-80.png (d32a012e8035ccbef7279f1baa682bdc187ef8383d5fda400fa21c645a9529ea)
- 80px manifest: atlas-80-manifest.json (8b88ba63ea30731b4c349fe24dbe6959236ab676379f08d0306c1e9a5fe9366c)
- 80px 3-loop petrol preview: preview-80-native-petrol-3loops.mp4 (8e8b33730b50eca22e19bd546afe2900993e848115819472b81d22c03ac75833)
- 160px atlas: atlas-160.png (fed19c063cadf9a917c4c0d9713ff216491908ec88023ca3d36622be758483f1)
- 160px manifest: atlas-160-manifest.json (23ad16426a707b1affbe070af50d275d0e7c37fd91f3e018871b911ac13c0662)
- 160px 3-loop petrol preview: preview-160-native-petrol-3loops.mp4 (420784415b22840ef62f898180f6af10f0458c6caddb376681a002314bfe7605)
- Multi-background exact final contact: FINAL_MULTI_BACKGROUND_CONTACT.png (28450e22d6ee72b254f0b2f0924fba55d939c5acacfaf6fdc4396903d245d656)
- Manifest player: preview.html (62e206dd6f91311251e1009b24ba9a0298e9b3da234f94ec078471965df954fe)
- ZIP: minimax-ne-transparent-export.zip (6146931fa367af5a20b8e274aab737c1f2fac8e776914f9459cea55e6411737e)

## Cost

- Fresh quote: USD 0.004/image; 24-image maximum reserved before first submission: USD 0.096.
- Provider IDs: 24; actual charge not authoritatively returned, so full USD 0.096 remains accounted.
- Cumulative maximum accounted: USD 1.566462750 of USD 22.9200.

## Honest limits

- One NE walk direction only.
- No VLM review, source regeneration, frame synthesis, ping-pong, or public/game change.
- Human review covered the source preview; transparent final export requires independent visual review of the retained evidence.
- MP4 previews are opaque composites for playback convenience; atlas PNGs and frame PNGs contain true alpha.

## Exact final inspection

- Inspected all 24 delivered 160px atlas cells on light, dark, and petrol backgrounds. Hair, cloak, hand, lantern, legs, and feet remain present in every frame; no clipping, deleted body chunks, gray matte, obvious halo, or detached garbage was observed.
- Inspected all 24 delivered 80px cells on light and petrol at native 1:1. The compact variant remains readable and coherent, but fine hair, cloak-fold, lantern, and boot detail is necessarily reduced. It is secondary; 160px is the intended primary native display size.
- Inspected the exact transparent 160px atlas: 24 nonblank row-major cells, consistent placement, and clear cell margins.
- Decoded the exact final 160px MP4 around two loop boundaries. No blank/corrupt frame, scale jump, root jump, or missing-part discontinuity was observed; the end-to-start pose change is plausible in the retained static boundary evidence. Static strips do not replace continuous human playback review.
- Technical verification: FINAL_VERIFICATION.json. All 24 provider prediction IDs are unique/completed, all downloaded outputs hash-match, every manifest rectangle is in bounds and nonblank, alpha 1..7 cleanup survivors are zero, both previews decode as 72 frames / 4.0 seconds / 18 FPS, and ZIP CRC validation passed.
- Final visual assessment is evidence-bound and not a perfection or automatic-selector certification claim.
