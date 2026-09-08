# Local removal and alpha review

Local inference is a practical fallback, not a guarantee of good masks on tiny
pixel-art details. Start with one representative asset. The official
[rembg v2.0.75 instructions](https://github.com/danielgatis/rembg/tree/v2.0.75)
provide a CPU backend and explicit model selection. Pin the version and model:
upstream defaults can change. Python 3.12 is suitable for this release.

## CPU removal

With `uv`, run without adding dependencies to the game package:

```sh
uv tool run --python 3.12 --from "rembg[cpu,cli]==2.0.75" rembg i -m u2netp source.png cutout.png
```

Or use a dedicated Python environment:

```sh
python -m pip install "rembg[cpu,cli]==2.0.75"
rembg i -m u2netp source.png cutout.png
```

Use a new output filename; do not overwrite the original. `u2netp` is the small
starting model. If it loses fine detail, try the larger `u2net` on one sample or
the WaveSpeed remover and compare masks before choosing. The installation brings
Python/ONNX dependencies; the first inference downloads model weights. For this
pinned release, the default weight cache is `~/.u2net`, configurable with
`U2NET_HOME`. Keep checksum verification enabled. With dependencies and weights
cached, CPU inference runs locally without uploading the image. First setup is
not offline. Record the actual package/model version in provenance.

Do not assume all bundled models have the same licensing as the rembg wrapper;
keep the selected model's upstream attribution with the host pack. See
[rembg](https://github.com/danielgatis/rembg/tree/v2.0.75) and
[U2-Net](https://github.com/xuebinqin/U-2-Net).

For exact authored flat backgrounds, deterministic color-key masking can preserve
crisp pixels, but only when the key is known and absent from subject pixels.
Global white/green deletion will destroy white petals/green foliage. A border
flood fill alone leaves enclosed holes; gradients, antialiasing, and baked
checkerboards need a different mask or a cleaner source. Do not apply a generic
threshold to every generated asset. Neither automatic remover repairs wrong
ground geometry or mismatched scale.

## Decode and inspect

The read-only source inspector needs Pillow, independently of rembg. From the
Runtime folder, use a new inspection directory for each candidate:

```sh
uv run --python 3.12 --with "Pillow==11.3.0" python -B skills/game-asset-generation/scripts/inspect-alpha.py cutout.png test-results/assets/cutout-inspection --require-cutout --expect-size 1024 1024
```

Replace expected dimensions with the original image's decoded dimensions, or omit
`--expect-size` when testing an intentionally new canvas. Without uv, install
Pillow in your tool environment and invoke the same script with Python.

Outputs are `alpha.json` and `backgrounds.png`. The board shows the same unscaled
pixels over light, dark, and magenta backgrounds. The report includes decoded
mode/dimensions, transparent/partial/opaque pixel counts, nonzero-alpha bounds,
edge contact, and a source hash. It refuses an existing output directory.

`--require-cutout` exits 1 for fully opaque or fully transparent images; a size
mismatch also exits 1. The diagnostic board is still written for those failures.
A pass only establishes both transparent and foreground pixels, not a correctly
segmented subject. One cleared corner can pass while the rest remains wrong.

Inspect the original and board for checkerboard remnants, fine petals, holes,
shadows, edge contamination, and altered ground contacts. Check actual game zoom
as well as source scale. A partial-alpha edge may be intentional; do not globally
binarize it merely because the game uses nearest sampling. If trimming is needed,
record crop offsets and recompute anchors; keep animation canvases consistent.

Choose the host's intended frame and `visual.width` before judging pixel density:
for example, a 512-pixel source crop at width 64 is displayed at 1/8 source scale
before camera zoom. The native-size alpha board does not show that reduction.
After recording those values and contacts, use the sibling calibration board:

```sh
node skills/isometric-art-integration/scripts/preview-art.mjs path/to/art-contract.json test-results/assets/calibration.html
```

Open it at shared zoom and then inspect the actual host scene at intended camera
zoom with its sampling mode. Do not resize each comparison independently or
assume a 1k generation already has the game's final pixel density.

Keep a small `generation-record.json` beside accepted artwork. For example:

```json
{
  "generation": {"provider": "wavespeed", "model": "bytedance/seedream-v5.0-pro", "predictionId": "REPLACE", "requestFile": "flower.request.json"},
  "source": {"file": "flower-source.png", "sha256": "REPLACE_WITH_SOURCE_HASH"},
  "processing": {"tool": "rembg", "version": "2.0.75", "model": "u2netp", "canvasChanged": false},
  "result": {"file": "flower.png", "sha256": "REPLACE_WITH_RESULT_HASH"},
  "acceptance": {"alpha": "unverified", "mask": "unverified", "inGame": "unverified"}
}
```

Replace placeholders from the job/inspection records, retain the actual request
file, and update verdicts only after their checks. For remote removal, replace the
processing entry with its provider/model/prediction ID. This is host provenance,
not a runtime manifest extension; no provider URLs or keys are needed in it.

## Courtyard precedent

The first Sunflower repair did not successfully remove its checkerboard with a
tool. Two generated RGB candidates were rejected, including an attempted
regeneration edit asking for alpha; a fresh generation finally returned valid
RGBA foliage. No rembg or WaveSpeed removal produced the shipped courtyard PNG.
This skill adds an explicit removal path so future agents need not depend on that
particular generator succeeding at transparency.
