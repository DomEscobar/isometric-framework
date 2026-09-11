# SAM 3 ZeroGPU authoring service

An isolated image segmentation service for a coding agent. The game never needs
Hugging Face credentials or a live connection to this service. It exports masks
at source resolution and preserves source RGB in the corresponding cutouts.
No example artwork is bundled or used by default.

## Setup

Install `uv`, approve access to [facebook/sam3](https://huggingface.co/facebook/sam3),
and authenticate locally with `uvx hf auth login`. The token needs permission to
create/manage your Space and read the gated model. Do not put credentials in files
under version control or in chat.

From the framework repository root:

```powershell
./authoring/sam3-space/setup.ps1 -CheckOnly
./authoring/sam3-space/setup.ps1
```

The setup creates `<your-account>/sam3-scene-masks` as a **private** Gradio Space,
requests only `zero-a10g` (the Hub API name for ZeroGPU), and stores the authenticated
token in the Space's `HF_TOKEN` secret. It uploads only the four allowlisted source
files in `space/`. It never falls back to paid dedicated GPU hardware. A token
dedicated to this Space can replace that secret later with narrower read access.
Existing Spaces are not modified unless `-Update` is explicitly supplied.
Account eligibility and daily usage quotas still apply; see the
[ZeroGPU documentation](https://huggingface.co/docs/hub/spaces-zerogpu).

The ignored receipt at `test-results/sam3-space/deploy.json` records the Space,
commit and requested hardware. A successful upload is not a successful build or
GPU inference. Wait for `RUNNING`, then run one representative mask request.

## API client

The following coordinates and filenames are illustrative; substitute the current
project's image and measured object bounds:

```powershell
uv run --script authoring/sam3-space/segment.py --space YOUR_ACCOUNT/sam3-scene-masks --image path/to/scene.png --text tree --boxes '[[10,20,80,120,1]]' --out test-results/scene-mask-attempt-1
```

The output directory must be new. The client saves source hash, prompts, server
event ID when available, wall time and outputs. It does not automatically resubmit
failed requests. A timeout requests cancellation; inspect the saved state before
trying again. GPU quota includes account-wide usage, not just this service.

The Space UI supports text plus positive/negative boxes. Two image clicks append
a box. This version does not implement point-prompt tracker refinement. Box prompts
can return several similar objects; inspect candidates separately before selecting
the desired object. Scores are model confidence, not visual acceptance.

## Verification boundary

Check masks over contrasting colors and with an actor crossing the actual scene's
occlusion boundary. Preserve the original image and keep collision geometry
separate. Native dimensions, binary alpha and exact recomposition do not certify
silhouette accuracy. This service neither reconstructs hidden ground nor modifies
the framework renderer.

The model revision and direct dependencies are pinned. Source syntax, box parsing,
separate candidate export, original RGB preservation and binary alpha were checked
locally with synthetic data. Live build, inference and visual results are recorded
separately in ignored evidence; they must not be inferred from those local checks.
