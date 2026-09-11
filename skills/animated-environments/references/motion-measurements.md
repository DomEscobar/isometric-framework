# Measure supplied motion captures

Use when timed frames and fixed/moving masks already exist. The helper uses
Python and Pillow; no browser, provider or game runtime is required for measurement.
The host's capture adapter owns simulation time, pause and camera stability.
Keep its source in the relevant acceptance dependencies.

The following names and timings are illustrative inputs, not approved artwork:

```json
{
  "version": 1,
  "periodSeconds": 1,
  "maxSampleGapSeconds": 0.5,
  "threshold": 8,
  "movingMask": "moving.png",
  "fixedMask": "fixed.png",
  "frames": [
    {"time": 0, "file": "capture-0.png"},
    {"time": 0.5, "file": "capture-half.png"},
    {"time": 1, "file": "capture-period.png"}
  ]
}
```

```sh
python skills/animated-environments/scripts/inspect-motion.py motion.json --out review/motion-1
```

Paths are relative to the recipe. Inputs are static PNGs of equal dimensions.
Masks are binary grayscale PNGs: 255 selects pixels and 0 excludes them. The
moving mask must be nonempty. The optional fixed mask must be nonempty, disjoint
from it, and use the same capture coordinates. No color-based segmentation occurs.
Pixels outside both masks are counted as unmeasured. View `regions.png` to check
the selection: moving areas are green, fixed areas red.

Supply 3..256 strictly increasing timestamps, starting at zero and ending at the
declared period. A default maximum gap of period/8 reports sparse sampling;
override it deliberately for the clip being inspected. Three samples illustrate
the schema, not sufficient evidence for every animation. Capture the joins and
fastest action phases at suitable intervals, and retain actual playback evidence.

`report.json` includes source/tool hashes, sampling gaps, adjacent-frame changes,
drift of fixed pixels from the first frame, and the zero-to-period endpoint comparison.
Exact changes include every RGBA channel, including RGB beneath transparent alpha.
Thresholded changes count pixels where a channel difference exceeds `threshold`.
Zero thresholded differences must never be reported as exact equality.

`board.png` shows up to eight time-labelled samples; native inputs remain the
evidence for detail inspection. A separate `timings.json` records tool duration.
The output directory must be new. Exit zero means measurement completed, even
when the sequence is frozen, fixed regions drift or the sampling is sparse.
The report always leaves `visualVerdict` unverified. Matching endpoints do not
certify a smooth wrap, believable flow, authenticated timing or pause behavior.
Attach the report as measurement evidence and playback as motion evidence through
the existing [acceptance workflow](../../isometric-visual-loop/references/acceptance.md).

For this helper's focused synthetic regression tests:

```sh
python -m unittest discover -s skills/animated-environments/tests -p test_inspect_motion.py
```
