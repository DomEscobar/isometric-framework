---
title: Scene masks with SAM 3
emoji: 🌳
colorFrom: green
colorTo: blue
sdk: gradio
sdk_version: 6.27.0
python_version: 3.12
app_file: app.py
suggested_hardware: zero-a10g
---

# Scene masks with SAM 3

Select an object with text and optional positive/negative boxes. Download separate
native-resolution binary masks, unchanged source-pixel cutouts, and a provenance
record. Outputs are candidates for visual inspection, not accepted game assets.

Use ZeroGPU hardware and a `HF_TOKEN` Space secret with read access to the gated
[`facebook/sam3`](https://huggingface.co/facebook/sam3) model. Model use remains
subject to its [license](https://huggingface.co/facebook/sam3/blob/main/LICENSE).
No example game images or credentials are bundled. Gradio's cached files are
cleaned on its hourly sweep after one hour of age. Generated export directories
remain in temporary container storage until the Space container is replaced.

The `/segment` API accepts an image, text, labeled boxes JSON, confidence threshold
and mask threshold. Boxes use original-image coordinates: `[x1,y1,x2,y2,label]`,
where label 1 includes and 0 excludes. Example geometry is illustrative:
`[[10,20,80,120,1]]`. Boxes prompt the model; they do not crop the returned masks.

All candidates are exported individually. Never use their union as the collision
footprint. A cutout remains in the original canvas; no resizing, edge smoothing,
island removal, hidden-ground reconstruction or manual mask repair is applied.

Implementation follows the official [SAM 3 model card](https://huggingface.co/facebook/sam3)
and [ZeroGPU guide](https://huggingface.co/docs/hub/spaces-zerogpu).
