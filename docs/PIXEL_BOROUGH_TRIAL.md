# Generated-sprite comparison trial

This trial tests the authoring workflow on a playable generated-art town against
the user's supplied target. It is not a default art pack for other games.

## Method and ownership

- Target: the unchanged 1408×768 user image, SHA-256
  `d76ac05d9b0970935cbf3d3514d9b2e3abcac59b40c3f8a362e3333993e304b7`.
  It guides pixel treatment and town composition, with original identities rather
  than exact franchise marks or object positions.
- A separate Codex CLI session built `examples/pixel-borough/`, starting from the
  target and a short task brief, without the parent conversation or memories.
  Session: `01a08b75-7e59-75e0-b868-3b05e51f359e`. The temporary CLI was 0.154.0;
  the user's global installation was not replaced.
- The builder owns the host, generated artwork and its capture scripts. The
  parent owns framework changes, build integration and separate browser probes.
  Fresh image reviewers read the contract and actual images, not builder code or
  its explanation of success. Reviewer-authored files remain separate.
- Built-in image generation produced actual PNGs for the actor, creatures,
  buildings, ground, plants, bridge, fountain and props. The host preserves source
  PNGs and request records under `art/originals/`; `prepare-art.py` derives packed
  assets. Cropping, registration and derived animation are not new generation.

The first autonomous production pass was paused after its first comparison packet
to deliver the completed external review. The same saved session was resumed for
repairs. That second pass is an externally reviewed repair, not an untouched
one-shot benchmark. Framework authoring corrections made during the run are listed
below; this is not a controlled comparison of two immutable framework revisions.

## First observed result

The town contains varied buildings, connected paving, rear woodland, left meadow,
a fountain, stalls and a stream crossing. The player can approach and greet three
original creatures. A successful build or asset count does not establish reference
fidelity.

The first formal packet contains seven comparisons, covering desktop, mobile,
ground overview, ground at playing zoom and a boundary close-up. A fresh reviewer
actually inspected all six unique images; duplicate reference/current images were
identified by hashes. Its 18 localized observations include 12 failed or unverified
findings. Visual requirements **fail**:

- The explorer is too small relative to houses, and the meadow is much noisier
  than the surrounding pixel treatment.
- Grass clumps repeat in conspicuous rows. Water exposes tile seams and repeated
  ripple panels, even after switching from individual overlays to one strip.
- The bridge's far landing and the ground-only deck transition are visually
  unclear. The mobile boundary capture does not show enough of the crossing.

An earlier independent overview-only audit found related issues with creature
visibility, framing and foreground layering. It is retained as an initial image
audit, not retroactively assigned a formal source snapshot.

The builder's first journey captures preceded its candidate snapshot and corrected
river-check baseline. That ordering does not demonstrate the prescribed snapshot-
then-capture procedure. The images support the visible findings; they do not prove
capture provenance. The repair request explicitly requires the correct ordering.

## Separate runtime evidence

The builder recorded desktop/mobile bridge routes in both directions, rejected
water entry, greetings and pause, with no failed assertions or page errors in
that run. Some keyboard samples hit an obstacle, so those samples alone do not
prove four visible walking cycles.

The parent then ran 22 checks through an actual Chromium page: all four keyboard
axes, all four touch D-pad axes, release after each, focus loss, restart progress
and document overflow. They passed without page errors. Its mobile screenshot
nevertheless exposed an unasserted defect: Restart shrinks the world to a tiny
overview. Coordinate assertions do not approve the camera or actor readability.
The repair now preserves the selected overview/follow zoom after Restart. A fresh
parent probe passed 26 checks, including that regression at both sizes, and the
mobile capture was visually inspected at its restored playing zoom.

Recorded frame intervals were approximately 33.3 ms median / 33.4 ms p95 for both
game views, versus 16.7 / 16.8 ms for the blank page. Chromium used ANGLE/SwiftShader;
the game contexts also recorded video, and the blank viewport differed. These are
local measurements, not hardware/mobile performance certification. Static image
review leaves motion, gameplay and performance unverified.

Adding the host to the shared production build exposed a separate startup issue:
its top-level await is unsupported by the existing Vite browser target. The host
must fix initialization; changing the shared target is not required.

## Authoring-tool findings

- Full packed inspection during calibration stopped at future creature clips.
  `inspect --groups` now permits an explicitly labeled calibration subset while
  final acceptance always reruns the full protected spec.
- A wide river frame exceeded an arbitrary 1024-pixel side limit despite being
  smaller than the existing square pixel budget. Inspection now permits sides up
  to 4096 with the same 1,048,576-pixel area budget. Crop padding, alpha components
  and bounds remain checked. The replacement river spec's zero padding still
  needs correction; changing representation does not grant acceptance.
- The protected packet includes complete requirement descriptions. The board
  displays them beside the actual images, preserving source pixels and prior
  findings. The real seven-comparison board passed its Chromium controls probe.
- Correcting a packing spec can require a new frozen baseline. An explicit
  `--rebaseline-note` now preserves comparison history across that correction,
  requiring identical requirements, targets and comparison definitions. The board
  announces the change and retains the previous packet and open findings. The
  reviewer still has to judge the stated art-check correction; the tool does not
  authenticate permission or artistic justification for a threshold change.
- The tool can reject stale, missing or inconsistent evidence. It cannot compel
  a coding agent to use vision, authenticate a reviewer or make ugly art beautiful.
  This trial's visible defects require actual asset/host repairs and fresh review.

## Local evidence and current status

Evidence is intentionally outside source control under
`test-results/real-visual-session/` and `test-results/framework-review/`. Relevant
files include the unchanged target, session JSONL, comparison-1 board and independent
review, first town capture, input probe report and builder journey videos. A fresh
checkout needs its own supplied target and captures to execute a new comparison.

The reviewed repair pass is in progress. No final visual or world acceptance is
claimed. Public runtime APIs are unchanged.
