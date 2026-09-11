# SAM 3 ZeroGPU: first tree-mask trial

The private authoring service is deployed at
[neridonk/sam3-scene-masks](https://huggingface.co/spaces/neridonk/sam3-scene-masks).
It requires the owner's Hugging Face login. Reusable setup and API instructions
are in [authoring/sam3-space](../authoring/sam3-space/README.md).

## Result

One real API request segmented the existing 256 x 224 generated scene into four
tree candidates. Total client wall time was **15.67 seconds**, including connection,
upload and returned files; reported model inference was **1.84 seconds**. These
numbers exclude Space setup, build, initial model loading and subsequent human
inspection. They are one observation, not a latency guarantee or GPU billing meter.

The author selected candidate 01 as the western tree. Its binary mask contains
4,470 pixels. No manual mask correction, resizing, smoothing or second inference
was used. The original image was generated earlier through Retro Diffusion; SAM 3
only segments it. This test requested ZeroGPU, with no dedicated paid hardware.

The masked cutout and contrasting-background board were visually inspected. The
selected mask separates the tree from the surrounding grass/water without the
large disconnected remnants of the previous manual extraction. Fine leaf-edge
accuracy is not quantified against a human-labeled ground truth. Other returned
trees include existing scene occlusions and are not certified reusable assets.

## Playable check

Run the existing Mossbend host and open `/one-tree.html?sam3`, or build/preview its
`vite.one-tree.config.ts`. The SAM variant keeps the **entire original scene** as
the background and redraws the masked tree over the actor at the rear pose.
It does not reconstruct or expose hidden ground. The original manual extraction
test remains available without the query parameter.

Desktop and mobile browser checks passed:

- Actor visible in front, fully occluded at the rear pose, and able to return.
- Trunk collision, keyboard movement, touch route buttons and stable pause.
- Pixel-identical original/assembled canvas with the actor disabled.
- No browser errors in the tested journey.

Host TypeScript and Vite production build passed; Vite's existing large-chunk
warning remains. The production preview loaded all tested resources and completed
the rear route without browser errors. The author inspected actual front/rear
screenshots; there was no independent review in this trial. These checks cover
one fixed-camera tree and the tested route, not every silhouette edge, the engine's
Pixi depth ordering, movable trees or whole-world acceptance.

## Space UI and API

The private Space ran on `zero-a10g`, the Hub's API identifier for ZeroGPU. Its
actual `/segment` API returned mask PNGs, cutouts and provenance. The Space UI was
browser-tested at desktop/mobile sizes for image upload, text, clearing boxes and
two-corner image selection in original-pixel coordinates.

An initial automated-browser error came from Gradio's standalone Space footer
fetching private Hub metadata without authentication. The browser fixture was
corrected to authenticate both the app and that exact metadata request. The final
UI checks had no page errors. UI checks did not submit a second GPU job; inference
was exercised separately through the real API.

## Evidence

Ignored evidence: `test-results/sam3-space/` contains deployment/status receipts,
`tree-attempt-1/` request and result records, all candidate masks and the inspection
board, `browser/` journey screenshots/videos, `ui/` desktop/mobile captures and
`production.json`. Candidate 01 and its source/request provenance are retained in
`examples/mossbend/art/sam3-tree/`.

This demonstrates a usable first automatic mask for the bounded layering approach.
It does not establish that a whole world can be produced accurately in one turn.
