# First SAM 3 tree mask

Source image: `../scene-second.png`, originally generated for this host through
Retro Diffusion. SAM 3 segmented the existing pixels; it did not generate new art.

`tree.png` and `mask.png` are unchanged candidate 01 from the first API response.
The author selected it visually as the western tree. There was no mask editing,
cropping, scaling, smoothing or second model request. `request.json` records the
source file hash, API event and total elapsed time. `result.json` records model
revision, native dimensions and all four returned candidates; only candidate 01's
mask/cutout are copied here. Model confidence is not a visual acceptance verdict.

Open `/one-tree.html?sam3` in the host. This variant retains the complete original
background and overlays the masked source tree when the actor is behind it.
It does not use the generated clean plate. The original hand-mask experiment
remains available without the query parameter.

Model: [facebook/sam3](https://huggingface.co/facebook/sam3), subject to its
[SAM license](https://huggingface.co/facebook/sam3/blob/main/LICENSE).
