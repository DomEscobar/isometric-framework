# Seedream reference-guided pose recipe

Checked 2026-09-08: the linked
[Seedream Pro model](https://wavespeed.ai/models/bytedance/seedream-v5.0-pro)
is text-to-image. Its separate
[Edit endpoint](https://wavespeed.ai/models/bytedance/seedream-v5.0-pro/edit)
accepts reference images and an edit prompt. Reference support is useful for
character consistency; the provider does not establish exact sprite direction,
frame alignment, or animation quality for our game.

Use text-to-image to establish a master character when no approved source exists.
Then use an accepted master plus, when available, the accepted neutral view of the
requested direction. In the prompt assign each reference a clear purpose. Do not
include unapproved variants that contradict costume, equipment hand, or camera.

The bundled WaveSpeed client supports Edit using 1–10 public HTTPS reference URLs.
This wrapper deliberately does not embed base64 or upload local files; for those
paths use the official upload/API workflow in the generation skill. Publicly
accessible does not mean permanent: retain source files and hashes locally.

Example `test-results/poses/walk-ne-01.request.json` (replace URLs and design):

```json
{
  "prompt": "Create one walking pose of the SAME gardener. Image 1 fixes identity, clothing, palette and body proportions. Image 2 fixes the approved NE view and camera: the character travels toward the upper-right of the screen, showing its back and a rightward silhouette; torso, feet and head follow that direction. Preserve the backpack, hat, and tool in the character's original hand. Walking contact phase: left foot forward and planted, opposite arm forward, right foot trailing. Keep camera elevation, upper-left lighting, body scale, canvas composition and ground root consistent with image 2. Full silhouette with margins on a uniform contrasting backdrop. No labels, arrows, checkerboard, scenery or cast shadow. One pose only.",
  "images": ["https://your-image-host.example/gardener-master.png", "https://your-image-host.example/gardener-idle-ne.png"],
  "aspect_ratio": "1:1",
  "resolution": "1k",
  "output_format": "png",
  "prompt_optimization_mode": "standard"
}
```

The example defines a proposed pose, not an approved frame. For a turnaround,
start with only the master reference and ask for the named neutral direction.
For the other walk contact, swap the anatomical left/right limb phase while
preserving travel direction. Avoid ambiguous "face right" as the only instruction.

From the repository root, with the existing API key/authorization:

```sh
node skills/game-asset-generation/scripts/wavespeed.mjs submit bytedance/seedream-v5.0-pro/edit test-results/poses/walk-ne-01.request.json test-results/poses/walk-ne-01.job.json
# Recovery only, after polling timeout/interruption:
node skills/game-asset-generation/scripts/wavespeed.mjs resume test-results/poses/walk-ne-01.job.json
```

Create the parent directory and request file first. Download completed outputs
with the generation skill's examples, then remove backgrounds and normalize the
approved candidate. Do not assume a 1k request gives exact cell dimensions or
stable framing. If a pose changes apparent body size, reject it or correct it
against measured anatomical landmarks; never normalize by silhouette bounds.

## Phase plans

| Action | Small starting plan | What to inspect |
| --- | --- | --- |
| Idle | One neutral frame per direction | Identity, root, four distinct views |
| Walk | Contact A, passing A, contact B, passing B | Alternating limbs, consistent travel, loop seam and foot sliding |
| Jump | One airborne pose per direction initially | Raised feet without doubled flight offset, landing returns to idle/walk |
| Attack | Anticipation, strike, recovery | Same hand/weapon, readable aim and reach, host-driven effect timing |
| Interact/cast | Reach/preparation, effect pose, return | Target direction, silhouette clearance, explicit host action end |

Reuse or repeat an approved frame for timing holds instead of regenerating an
identical pose. Runtime clips use one FPS value; repeated frame IDs can lengthen
a hold. Do not add per-frame-duration fields to the current manifest.

Use a consistent character/world scale, not mandatory real-world anatomy. Inspect
body landmarks separately from moving limbs and equipment. Final direction,
temporal coherence, and root alignment require visual review plus actual playback;
prompt compliance or a successful API response cannot certify them.
