#!/usr/bin/env python3
"""Finalize previews/report for a completed paid run without new provider calls."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.live_e2e_trace import Trace, atomic_json, create_previews, sha256, utc, write_report

RUN_ID = "live-e2e-20260920T223050Z-91b811"
JOB_ID = "e0f2fc10ee3949ce89b31dd5d4444c86"


def main() -> int:
    run_dir = ROOT / "artifacts" / RUN_ID
    workdir = run_dir / "private-service-data" / "jobs" / JOB_ID
    report_path = run_dir / "LIVE_E2E_REPORT.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    manifest = json.loads((workdir / "atlas-manifest.json").read_text(encoding="utf-8"))
    atlas_gate = json.loads((run_dir / "atlas-quality-gate.json").read_text(encoding="utf-8"))
    if sha256(workdir / "atlas.png") != atlas_gate["atlas_sha256"]:
        raise RuntimeError("atlas hash changed before free finalization")
    if sha256(workdir / "atlas-manifest.json") != atlas_gate["manifest_sha256"]:
        raise RuntimeError("manifest hash changed before free finalization")
    outputs = create_previews(workdir, run_dir, manifest)
    report.update({
        "status": "completed_technical_gates_passed_visual_review_pending",
        "summary": (
            "The one authorized real reviewer approved candidate-01. Ten sparse native source frames were extracted, "
            "removed, packed, and passed the existing extraction, alpha/geometry, and atlas integrity/timing gates. "
            "The retained atlas was visually inspected as coherent and unclipped at native scale, but this is not a "
            "multi-direction or human art-direction certificate."
        ),
        "outputs": outputs,
        "ended_at_utc": utc(),
        "error": None,
        "visual_inspection": {
            "artifact": "atlas.png",
            "assessment": "usable_one_direction_sprite",
            "observed": [
                "all ten cells show the same character and northeast-facing identity",
                "no visible body or prop clipping in the atlas cells",
                "scale and foot placement appear consistent in the static atlas",
                "no obvious bright matte halo at the inspected native scale",
            ],
            "not_proven": [
                "a static atlas inspection cannot fully certify temporal jitter or the end-to-start seam",
                "semi-transparent edge quality can still reveal halos on backgrounds unlike the preview",
            ],
            "visual_quality_certified": False,
        },
    })
    atomic_json(report_path, report)
    write_report(run_dir, report)
    trace = Trace(run_dir, RUN_ID)
    if not any(item.get("event") == "free_existing_run_finalized" for item in trace.events):
        trace.add(
            "free_existing_run_finalized",
            provider_calls=0,
            source_response_reprocessed=False,
            atlas_sha256=outputs["atlas"]["sha256"],
            manifest_sha256=outputs["manifest"]["sha256"],
            outputs=outputs,
            status=report["status"],
        )
    complete = ROOT / "COMPLETE_SPRITE_REPORT.md"
    clip = manifest["clip"]
    frame = manifest["frames"][0]["rect"]
    atlas = manifest["image"]
    complete.write_text(
        "\n".join([
            "# Complete sprite report",
            "",
            f"Run: {RUN_ID}",
            f"Status: {report['status']}",
            f"Source SHA-256: {report['source']['sha256']}",
            "Reviewer: google/gemini-3.8-flash through OpenRouter, one real call, no fallback",
            "Decision: approve candidate-01",
            "",
            "## Concrete output",
            "",
            f"- Transparent atlas PNG: {outputs['atlas']['path']}",
            f"- Manifest: {outputs['manifest']['path']}",
            f"- Native GIF: {outputs['native_gif']['path']}",
            f"- Native MP4: {outputs['native_video']['path']}",
            f"- Manifest-driven preview: {outputs['html']['path']}",
            f"- ZIP: {outputs['zip']['path']}",
            "",
            "## Exact animation geometry and timing",
            "",
            f"- Frames: {len(manifest['frames'])}",
            "- Native source indices: 28, 33, 37, 42, 47, 52, 56, 61, 66, 70",
            f"- Normalized frame: {frame['width']}x{frame['height']} pixels",
            f"- Atlas: {atlas['width']}x{atlas['height']} pixels, RGBA with true transparency",
            f"- Playback: {clip['fps']} FPS",
            f"- Cycle duration: {len(manifest['frames']) / float(clip['fps']):.9f} seconds",
            f"- Anchor: {json.dumps(manifest['frames'][0]['anchor'], sort_keys=True)}",
            "- Sparse sampling preserves the approved source interval duration; it does not replay at native 30 FPS.",
            "- GIF delay is 157 ms/frame; HTML manifest playback is authoritative for the exact fractional FPS.",
            "",
            "## Quality result",
            "",
            "- Reviewer approved candidate-01 with no reported issues.",
            "- Extraction provenance, cutout alpha/geometry, and atlas integrity/timing gates passed.",
            "- Static atlas inspection found consistent identity/facing, no visible clipping, and no obvious matte halo at native scale.",
            "- Visual quality remains explicitly uncertified: the static atlas cannot fully prove temporal jitter/seam quality, and edge behavior can vary by background.",
            "",
            "## Cost and liability",
            "",
            f"- This reviewer call: USD {report['automatic_review']['budget']['actual_cost_usd']:.6f} known billed.",
            "- Ten removals: USD 0.040 quoted; completed, charge not authoritatively returned, retained as open liability.",
            f"- Cumulative known billed in this ledger: USD {report['cost']['known_billed_cost_usd']:.8f}.",
            f"- Cumulative open/ambiguous liability: USD {report['cost']['open_or_ambiguous_liability_usd']:.6f}.",
            f"- Maximum accounted total: USD {report['cost']['maximum_accounted_total_usd']:.8f} of USD 1.00.",
            "",
            "## Exact limits",
            "",
            "- One northeast direction and one walk-like cycle only; no multi-direction aggregate.",
            "- Existing WAN video was reused; no facing or video generation occurred.",
            "- Reviewer evidence was a bounded 12-image sequence, not native video.",
            "- MP4 is a convenience preview and does not retain alpha; atlas PNG and GIF retain transparency.",
            "- The old USD 0.790032 ambiguous reviewer liability remains preserved.",
            "- Public service policy, UI, game, global configuration, and deployment were not changed.",
            "",
            f"Trace: {run_dir / 'TRACE.md'}",
            f"Ledger: {run_dir / 'cost-ledger.json'}",
        ]) + "\n",
        encoding="utf-8",
    )
    shutil.copyfile(complete, run_dir / complete.name)
    print(json.dumps({"status": report["status"], "run_dir": str(run_dir), "complete_report": str(complete), "outputs": outputs}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
