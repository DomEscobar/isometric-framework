# Generated environment follow-up — 2026-09-08

The earlier SVG exercise did not test the user's requested generated-asset
workflow. This follow-up uses actual built-in `image_gen` outputs for the fountain,
river, bridge paving/supports, replacement railing and splash animation. Original
PNGs, exact prompts and source hashes live in
`examples/environment-lab/art/generated/`. The underlying model identifier is not
exposed by that tool; this is not a WaveSpeed/Seedream benchmark. No generated art
was replaced by authored pixels. Atlas windows/anchors bind the original PNGs
directly; no repainting, nonuniform prop warp or procedural water art was used.
Terrain side faces and the reference actor remain the existing runtime graphics.

## Three processing variants

The lab defaults to **Generated · Fixed stone + splashes**. The selector also
shows **Registered frames** and **Raw sheet assumptions**, preserving mistakes
for comparison. These are three processing stages using the same generated pack,
not another set of independent A/B/C agent authors. An independent agent measured
the actual source pixels and alpha while the coordinator integrated/rendered them.

| Check | Raw sheets | Registered | Fixed stone + splashes |
| --- | --- | --- | --- |
| Actual frame placement | Fails: water jumps between rows | Corrected windows | Corrected windows |
| Rigid fountain pixels | Change between generated frames | Still change | One fixed generated frame |
| Visible water motion | Whole-sheet animation | Whole-sheet animation | River and separate splash rings |
| Bridge crossing / ground underpass / stone jump stress | Pass | Pass | Pass |
| Pause and full-loop return | Pass | Pass | Pass |

Full-loop return proves deterministic playback, not smooth motion or coherent
downstream flow. The final fountain keeps its original jets static and animates
small independently generated splashes at the landing areas. It is not a complete
animated jet simulation. The raw/registered variants show the original moving
jets together with their unwanted stone texture changes.

## What failed and what changed

- **Requested dimensions were unreliable.** Fountain/river/splash sheets decoded
  as 1254x1254. The bridge kit is 1774x887; replacement rail is 1536x1024.
- **Equal sheet cells did not align river content.** Bottom-row art was 84 source
  pixels higher and right-column art 4 pixels left. Equal 600x330 windows at
  `(15,225),(638,225),(15,768),(638,768)` register the existing frames. Their
  silhouette is slightly steeper than 2:1; it overlaps by about 2.4 world pixels
  in depth at one-tile width. No claim of perfect edge-texture continuity is made.
- **Stable silhouettes did not mean stable stone texture.** Fountain alpha bounds
  matched, but a water-free stone sample changed roughly 8.6–10 RGB levels on
  average between frames. The final host binds only `fountain-0` for stone.
- **Two water-only extraction attempts failed alpha.** Both produced RGB images
  with an opaque checkerboard. They are retained as rejected files, not loaded by
  the game. After repetition, the approach changed to newly generated small
  splash sprites. The five used assets have usable decoded alpha and were viewed
  on light/dark composites. Bright hidden RGB in transparent pixels is not itself
  a visible fringe; the rendered composite is the relevant check.
- **Original rail camera was wrong.** Its floor line had slope about −0.34 instead
  of −0.5. That piece was rejected. A focused new generation improved the slope,
  but still leaves about 3.2 world pixels of end-to-end residual over each 64px
  render span. Midpoint fitting shares that error between both ends; it does not
  repair the projection. Three spans per edge cover the whole bridge without the
  earlier center-to-center spacing gaps. Small joint/camera discrepancies remain.

## Measured placement and collision

`generated-scene.ts` owns the reproducible bindings; it changes host content only.
The fountain uses four 627px-square source windows, width217.6926 and anchor
`(.20600744,.70653907)` for a 3x3 footprint. Observed visible base contacts are
approximately `(37,443),(590,443),(314,588)` in frame0. The rear corner is hidden
and is not counted as independent evidence. Front contact residual is about
2.34 world pixels. The 3px check tolerance is a **retrospective prototype fit**,
not proof that the generator met a prior exact camera specification.

The basin reserves all nine cells with a conservative46px body covering its
corner ornaments. The separate center body is114px, covering the measured
111.45px stone top with measurement allowance. Render size does not set these
physical values. The actor is48px. River cells remain unwalkable terrain, with
nonblocking animation above them.

The sparse bridge deck stays at72px, with access links, four ground piers and
independent full-cell rail reservations. Generated pier art measures about67.1px;
it overlaps the deck slab whose underside is64px. Paving, piers and rail spans
are separate render parts. The exact lower towpath remains open. Upper-floor
occlusion and conservative grid bodies remain engine limits; this is a pier
bridge, not an exact curved arch collider or replica of the supplied illustration.

## Verification and reproduction

With the source checkout's `npm run dev` on4175:

```sh
node --experimental-strip-types tests/environment-skills.mjs generated-raw generated-registered generated-layered
node tests/environment-lab-browser.mjs
```

After the final join/overlay placement adjustment, the refined variant was rerun
with `generated-layered` alone. It passed measured fountain/river/pier/rail contact
expectations, occupancy, actual bridge/underpass movement, pixel advancement,
pause, full-loop return and the four-cell jump stress. Deliberate wrong-anchor
and solid-bridge changes were rejected. Raw-frame placement failure is expected;
comparison mode preserves that finding. Passing the declared checks does not
certify all pixels or freeform collision.

Desktop and mobile host journeys passed with zero page errors, including mobile
Jump, crossing, walking underneath, pause/resume and reset. Screenshots were
inspected. `npm run build` passed21 source boundaries, TypeScript, library, both
host entries and declarations; the existing large shared browser chunk warning
remains. Older unrelated suites were not rerun.

Local evidence is under `test-results/generated-environment/` (source measurement
and alpha), `test-results/environment-skill-comparison/` (per-variant scenes,
plans/results and screenshots), and `test-results/environment-lab/` (host journeys).
The assembly and animation skills now require generated work when requested,
measured frame registration, separate geometry/texture/alpha verdicts, rejected
candidate retention, and explicit reporting of static jets or camera residuals.
