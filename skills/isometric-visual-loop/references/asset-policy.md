# Production asset policy

This is the mandatory policy for new version 4 worlds. It applies to production
art, not UI, collision geometry, masks, blockout shapes or test diagnostics.
Legacy plans remain readable; their acceptance does not certify this policy.

## Sources and animation

- Generate new visible world, environment and character artwork. Static assets
  may use text-to-image or image-to-image. Reuse accepted generated artwork with
  its source evidence; a new request is not required merely because it is reused.
- Character animation must use an approved generated image in the required facing,
  actually supplied to image-to-video generation, followed by reviewed extraction,
  deterministic packing and in-game playback inspection. Direct sheets, generated
  individual motion poses and authored character animation are not fallback routes.
- Preserve usable source alpha. Otherwise make one controlled chroma-key candidate
  and inspect it over contrasting backgrounds and in motion. Halos, holes, erased
  subject colors, flickering contours, or an uncertain verdict require the approved
  background remover on the selected unkeyed source frames before packing. Missing
  access or budget leaves character cutout acceptance blocked; local removal must
  not be presented as the required remote fallback.
- A static idle may use a single approved generated facing. It does not satisfy
  promised animated idle or movement, and a one-frame walk is not a static-idle exception.
- Scenery and other objects may use image-to-video, deterministic animation of
  generated materials or another suitable technique. The agent chooses based on
  stable bases, motion, joins, masks and the intended result. This freedom does not
  replace the character route or waive visual/motion acceptance.
- Masking, cropping, compositing, registering and packing may process generated
  pixels. They do not authorize replacing required art with handmade substitutes
  or inventing character movement poses outside the video route.

Honor approved access, upload permissions and budgets. Missing access or budget
is a blocker. Do not automatically retry an ambiguous billable request; retain its
job identity and resume it. The framework does not perform generation while checking
provenance and does not choose a provider merely because a tool is installed.

## Make the actual runtime inventory authoritative

Export the runtime asset manifest and use classifications from the same host
definitions that render the world. Include every image, texture and animation;
do not hand-select only convenient assets for the checker. Classify world,
character, environment, UI and debug uses explicitly. UI/debug exemptions must
describe actual use, not provide a way to label a player or building as a diagnostic.

Keep the export, exporter/host bindings and source artwork in protected input
roots. Inspect their correspondence to the running game. Local tools cannot prove
that a handwritten export reflects an unrelated renderer or authenticate a
remote provider; matching hashes alone do not establish those facts.

Use one provenance ledger for the declared runtime inventory. For static imagery,
retain local generation records, raw outputs and the transformations ending at
the used runtime image. For character clips, retain the generated facing record,
actual video request/receipt, local video, extraction preparation/recipe and packed
bindings. Every animated direction needs its own approved facing and I2V chain.
Record files and their hashes, not only provider names or intended prompts.

The [video extraction workflow](../../directional-sprite-authoring/references/video-to-sprites.md)
records source frames and timestamps. The gate verifies the chain through the
pixels and timing used by the runtime; direction and good movement still need
visual review. Preserve originals and repair receipts. A changed recipe, image,
video or binding needs fresh affected evidence.

## Use the existing production stages

Prepare policy paths before freezing; future full-world files need not exist at
that point. The blockout may contain neutral shapes. It needs actual image review
alongside spatial checks. The connected-area stage reviews generated production
art in its real setting. By static-world acceptance, the complete runtime inventory
must have valid provenance. Motion and final acceptance retain that requirement.

Use `verify-world.py production next BASELINE --receipts RECEIPTS` to see the next
stage, its missing inputs, pending checks and required evidence. This read-only
command does not advance a stage or approve any asset. Open evidence tickets only
after the candidate is ready, then capture and inspect it. A technical build is
separate from `verify-world.py accept` with production receipts.

All commands, including version 4 setup and compatibility, are described in
[production stages](production-flow.md). Keep visual quality, movement, gameplay
and performance verdicts separate from provenance validity.

## File formats

These are local evidence formats, not provider API payloads. Replace illustrative
IDs, paths and `SHA256` markers with actual values. Never invent a request ID.

The acceptance plan has `version: 4` and this policy:

```json
{
  "assetPolicy": {
    "version": 1,
    "sources": {"world": "generated", "character": "generated", "environment": "generated"},
    "characterAnimation": {"animated": "image-to-video-extract-pack", "staticIdle": "generated-facing"},
    "coverageLedger": "host/art/provenance-ledger.json",
    "runtime": {"manifest": "host/art/runtime.json", "binding": "host/art/used-assets.json"}
  }
}
```

`runtime.json` contains the public `assets.images`, `assets.textures` and
`assets.animations` maps (or those three maps at the top level). Image URLs resolve
relative to that manifest and must stay inside protected project inputs. The
binding classifies every manifest ID exactly once; texture/image and
animation/texture references stay in the same category:

```json
{
  "version": 1,
  "used": {
    "world": {"images": [], "textures": [], "animations": []},
    "character": {"images": ["actor"], "textures": ["actor.walk.ne.0000", "actor.walk.ne.0001"], "animations": ["actor.walk.ne"]},
    "environment": {"images": [], "textures": [], "animations": []},
    "ui": {"images": [], "textures": [], "animations": []},
    "debug": {"images": [], "textures": [], "animations": []}
  }
}
```

The ledger covers each nonexempt runtime image and each character clip:

```json
{
  "version": 1,
  "images": {
    "actor": {
      "origin": {
        "kind": "generated",
        "record": {"path": "host/art/actor/generation.json", "sha256": "SHA256"},
        "output": {"path": "host/art/actor/facing.png", "sha256": "SHA256"}
      },
      "transforms": [{"path": "host/art/sheet.png", "sha256": "SHA256"}]
    }
  },
  "clips": {
    "actor.walk.ne": {
      "mode": "image-to-video-extract-pack",
      "selectedImage": {
        "kind": "generated",
        "record": {"path": "host/art/actor/generation.json", "sha256": "SHA256"},
        "output": {"path": "host/art/actor/facing.png", "sha256": "SHA256"}
      },
      "videoJob": {"path": "host/art/actor/video-job.json", "sha256": "SHA256"},
      "recipe": {"path": "host/art/actor/review/extraction.json", "sha256": "SHA256"}
    }
  }
}
```

A generation record binds `outputSha256` to a real `requestId`, `jobId` or
`localJobId`. Retain provider/model, submitted prompt and references, returned
output and approval evidence there. A video job record includes provider, model,
job identity, `selectedImageSha256` and `videoSha256`; retain the actual submitted
input and returned receipt alongside those fields. No credentials belong in these
records. Hashes establish local correspondence, not provider authenticity.

An origin may also include `prepared` for a masked/cropped facing. Its `image`
and `mask` are ordinary `path`/`sha256` evidence; `crop` contains integer `x`, `y`,
`width`, `height`. Retain an `L` grayscale mask at the original image size. The
checker multiplies the original alpha by this mask (255 keeps, 0 removes), then
crops without rescaling or repainting and compares exact RGBA pixels to `image`.
When present, this prepared image is the selected facing supplied to video or
static-idle packing; `output` and the generation record still preserve the raw
generated original. Hash the prepared image in `selectedImageSha256`. Inspect
mask quality separately: reproducible masking does not establish a good cutout.

Every `path`/`sha256` entry references an existing protected file. Transforms list
retained processing evidence and must end with the actual runtime image and its
hash; when unchanged, the endpoint may be the original output. Retain mask,
registration and animation method recipes here as appropriate. Scenery does not
need an entry in `clips`; its actual processing evidence and motion review remain
required, whether it uses video or another method.

For a static idle named `<imageId>.idle.<direction>`, use `mode: "generated-facing"`
and `selectedImage`, without `videoJob` or `recipe`. The gate compares its single
runtime texture to the selected facing pixels. This exception cannot satisfy an
animated action. Animated clips retain the extractor's frame IDs, FPS, loop flag,
canvas and anchor. Atlas positions may change; the bound per-frame pixels must
still match the replayed extraction. Keep the preparation, source video and
decoded frames under `inputRoots`, not only the recipe that refers to them.
