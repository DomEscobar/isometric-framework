# Retro Diffusion MCP option

Use when the project chooses Retro Diffusion for an asset family. Provider
capabilities below were checked on 2026-09-10 in the official
[MCP documentation](https://github.com/Retro-Diffusion/retro-diffusion-mcp).
This framework has not benchmarked its generated outputs.

## Connection and discovery

The hosted server uses Streamable HTTP at `https://mcp.retrodiffusion.ai/mcp`
with bearer API-key authentication. Configure credentials through the client's
secret mechanism, outside game files. The server chooses its upstream API version;
clients retain the same endpoint. See the provider's
[compatibility contract](https://github.com/Retro-Diffusion/retro-diffusion-mcp/blob/master/API_COMPATIBILITY.md).

Check that the MCP tools are actually callable before planning production around
them. Listing this option does not install or authenticate the service. If it is
unavailable, report the connection gap and follow the project's fallback decision.

## Select, estimate, generate

1. Discover current capabilities with `list_available_styles` and
   `get_style_usage`; inspect supported sizes and reference/animation constraints.
2. Estimate with `estimate_inference_cost`. For edits, inspect `list_edit_tools`
   and use `estimate_edit_tool_cost`. Stay within existing spending authorization.
3. Use `create_inference`, or `start_inference_job` plus `get_inference_job` for
   asynchronous work. The documented outputs include sprites, animation and tilesets.
4. Preserve request/task IDs. Recover synchronous outputs with
   `get_inference_result`; recover lost async job IDs through `list_inference_jobs`.
   Do not automatically resubmit a paid generation after a timeout.
5. Download outputs into the host's own asset directory and retain source hashes.

Discover current input schemas rather than inventing parameters. Record the
chosen model/style identifier, output dimensions, references, request, processing
and cost estimate with the asset. Provider presets describe generation settings;
the project still owns the intended appearance and pixel scale.

## Calibrate the result

Start with one representative asset in the actual host. An animation or tileset
endpoint does not prove compatibility with this runtime's projection, facings,
anchors or neighbor-mask conventions. Convert outputs to explicit host manifests,
preserve originals, and inspect every used crop and clip.

Apply the [directional workflow](../../directional-sprite-authoring/SKILL.md) for
actors and the [tileset workflow](../../consistent-tileset-authoring/SKILL.md) for
connected geometry. Decode transparency using [alpha review](backgrounds.md),
then run the [packed-art and acceptance checks](../../isometric-visual-loop/references/acceptance.md).
Provider success leaves visual and motion acceptance open until observed.
