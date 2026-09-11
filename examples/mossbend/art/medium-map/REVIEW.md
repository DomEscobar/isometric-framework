# Medium map image review

Actual output: **1536 x 1024**, one built-in ImageGen call, original output retained
unchanged as `scene.png`. The full submitted prompt is `prompt.txt`.

A fresh independent image reviewer inspected both the generated image and the
user's forest style reference. This review covers image composition only.

| Criterion | Verdict | Observation |
| --- | --- | --- |
| Medium-sized, differentiated environment | Pass | Three cottages, market, garden, well, stream, forest and raised clearing provide distinct areas. |
| Terrain/object integration | Pass | Irregular path edges, reeds, embedded rocks, flowers and layered vegetation join the materials. |
| Clear two-crossing route loop | Fail | The wooden bridge connects the hamlet to the right bank. The stone bridge appears to cross a right-side channel; a return crossing to the hamlet is not established. Foreground crowns obscure some route continuity. |
| Pixel treatment against reference | Fail | Overall treatment is coherent but finer, softer and more illustration-like than the reference's coarser crisp clusters. |
| Visible planting and stairs | Qualified | Visible trunks generally occupy planted areas; stairs are readable. Hidden ground cannot be certified from the image. |
| Collision, occlusion, motion, gameplay | Unverified | No game binding or animation has been produced for this new image. |

Decision: retain as a substantially richer candidate, not an accepted playable
map. Before gameplay binding, resolve route topology and the intended pixel scale.
Increasing raster dimensions alone has not solved either issue.

Provider checks performed for this decision: Retro Diffusion MCP
`get_style_usage` returned maximum 256 x 256 for `rd_pro__isometric` and
`rd_pro__edit`, and 384 x 384 for `rd_plus__default` on 2026-09-11.
The selected RD Plus style does not support per-inference reference images.
These are limits of those styles, not a claim that all Retro Diffusion tools share
one resolution cap. The previous map's weak composition also came from its narrow
authoring brief, not just the provider.
