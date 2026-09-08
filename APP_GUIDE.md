# Independent demo playtest guide

## Start and target

Run `npm install` and `npm run dev` from `Runtime/`. The standalone demonstration is **http://127.0.0.1:4175**. The legacy multiplayer application's public deployment is a different target; this folder's changes are not automatically deployed there. For repository end-to-end checks, respect the root `AGENTS.md` public-URL requirement and report missing deployment explicitly. This guide describes expected behavior; it is not executed test evidence.

The page title is “Little Worlds · Isometric Runtime”. Initial loading ends with “Running” and **06 — Sunflower courtyard**, a 9 × 9 pixel-art café garden. “All floors” is initially selected. “Fit map” restores the whole map after dragging or zooming. Select **04 — Jump & dodge** for the bridge and trap checks below.

## Weidenkai

Open **http://127.0.0.1:4175/examples/willow-quay/**. Start at `(4,6)` on the
apothecary bank. Apotheke walks to `(4,5)`, Über die Brücke crosses the actual
upper floor to `(7,11)`, and Am Kanal returns to `(11,6)`. Buildings and water
remain blocked. Click paths or use WASD; mobile provides D-pad and Jump. Use +/−
to inspect details and Übersicht to restore the map. Pause freezes simulation;
Inspizieren exposes footprints and floor data. No saved progress or interiors.
See [WILLOW_QUAY.md](docs/WILLOW_QUAY.md) for source preparation and visual limits.

## Autotile lab

Open **http://127.0.0.1:4175/examples/autotile-lab/**. The default hollow bed ring
blocks walking into its center. Use **Paint tiles**, remove `(2,4)`, then
**Finish painting** and click `(4,4)` to walk through the opening. Neighbors
change their border/corner artwork when you edit. Painting on the traveler is
rejected. The shape selector also provides a strip, L, filled patch and two
diagonal-only cells. Inspect footprints reveals coordinates; selecting a cell
reports its mask and variant. Mobile uses a held bottom-right D-pad.

The generated source and deterministic bed assembly are documented in
[AUTOTILING.md](docs/AUTOTILING.md). This lab does not use saved progress.

## Environment lab

The separate **Environment lab** is at
**http://127.0.0.1:4175/examples/environment-lab/**. It opens generated artwork with
a fixed fountain and animated splash rings. Compare raw and registered generated
sheets in the selector; the earlier SVG trials are grouped separately. Cross bridge walks
to `(12,5)` via the raised deck. Walk underneath selects ground view and walks
through the dry towpath to `(4,3)`. Pause freezes the water; Inspect shows actual
footprints and sprite data. Reset restores the selected scene. Mobile has a
bottom-right D-pad and Jump button. The original B/C trials deliberately retain
their basin-only fountain collider; the recommended scene adds the central stone
body. Generated sheets and their remaining projection/animation limits are
documented in [the generated trial](docs/GENERATED_ENVIRONMENT_TRIAL.md). The final
fountain's baked jets stay static while separate splashes animate. No saved
progress is used in this lab.

## Sunflower courtyard

**Inventory and saved progress:** With no local save, start at `(2,6)` and `0 / 3`.
Pick a flower: the basket contains one `flower` item and that pot disappears.
The garden saves automatically after completed steps, landings, and picking.
Reload should restore the basket, remaining pots, and last committed actor cell.
Save/Continue controls and item contents appear below scene export. Continue can
return from another preset; Restart resets the original garden and stored basket.
Only Sunflower uses this save slot; scene export/import remains scene-only.
A corrupt save or unavailable storage must show an error while keeping play usable.
Use a fresh browser context when testing the default empty garden. In-flight
actions and jumps are not restored, and browser-local saves do not sync devices.

**Interaction module:** Click/tap the ground cell of a small path flower at
`(2,2)`, `(6,5)`, or `(4,7)`. The gardener walks to a clear adjacent tile, faces
the flower, plays a 0.9-second gesture, removes exactly one pot and increments
**Flowers in basket**, then settles for 0.45 seconds. Walking onto a pot alone
does not collect it. The completion message is “All flowers are in your basket.
Time for a rest under the parasol.” Planted borders remain solid scenery.

Repeated clicks on the same flower during approach/preparation must not restart
the action or multiply the reward. Pause during preparation freezes both the
progress bar and clip; Resume continues. **Cancel**, the mobile **Cancel picking**
button, or Escape while the map is focused stops the action. Before the effect,
the pot and counter remain unchanged; during recovery, the flower stays in the
basket. Clicking another ground tile or using WASD/D-pad/Jump interrupts picking.
Release a held direction after interruption: the actor must finish only its
current step and stop. Restart restores all three pots and `0 / 3`.

**Debug overlay:** Initially off. Toggle it in the side panel and select the
traveler. Cyan shows tiles, red committed collision footprints, yellow the route,
and green the sprite origin/full-frame bounds. During preparation the readout
must show the target-facing `pick-*` clip, then `pick-recover-*`, then automatic
idle. Pan/zoom/resize should keep outlines aligned; clicking through the SVG
still reaches the map. Disable it to restore the plain view. This is an authoring
aid, not evidence that the artwork itself is correctly drawn.

The picking gesture reuses existing grounded directional frames and their reverse;
it is not newly drawn hand-to-flower action art. Inspect this visual limitation
separately from the routing, timing, and exactly-once inventory behavior.

All built-in scenes use tile-axis click/tap routing (`diagonal: false`). Each
walking step changes either column or row by one, never both. Clicking a target
offset in both coordinates must produce turns along the tiles, including around
obstacles. This applies to Sunflower, Art calibration, and Woodland as well as
the original demos. Imported scene JSON retains its own explicit routing setting.

The default scene assembles local terrain, flowerbeds, iron railings, a palm, a lamp, a golden parasol with table/chairs, and an independently animated gardener. The traveler starts at **(2,6), Ground / 0 px**. Three small flower pots on the open paving at **(2,2)**, **(6,5)**, and **(4,7)** are interaction targets; planted borders are solid. The counter starts at `0 / 3`. Restart restores the traveler and pots.

An open route is `(2,6) → (2,2) → (3,2) → (4,2) → (4,4) → (6,4) → (6,5) → (5,5) → (4,5) → (4,7)`. Click destinations or use the shared tile-axis controls. The café furniture blocks **(5,2), (6,2), (5,3), (6,3)**; flower borders block their planted cells, including **(2,1)** and **(7,5)**. Open center tiles permit a four-direction loop, jumps, and walking around the table. Face/hat orientation follows NE/SE/SW/NW; feet animate during walking. Tall props occlude a traveler behind them; a traveler in front draws above them.

At 390px, the bottom-right D-pad, separate Jump button, and Cancel picking button occupy the reserved HUD below the map. Hold a direction and tap Jump with another finger; release stops after landing/current step. Fit map must keep the full courtyard and parasol visible. Export/import preserves asset references and remaining entities, but resets the collection counter against the remaining pots. All four PNG atlases are bundled locally; moving exported JSON to another deployment requires its image URLs there. Artwork metadata and layout live in `demo/pixel-cafe.ts`, interaction rules in `demo/main.ts`, and generation prompts in `demo/art/pixel-cafe/README.md`.

## Viewports and evidence

The revised courtyard separates stone/soil bases from foliage. Bases follow exact
80×40 ground diamonds, are 10 pixels high, and omit retaining walls between
adjoining planted cells. Flowers may overhang naturally; stone must not protrude
from its occupied footprint. Furniture width is calibrated to the gardener using
seat/tabletop heights. The group remains solid: walking between its chairs or
under its umbrella is not implemented.

Select **07 — Art calibration** for the exposed 9×9 inspection scene. The actor
starts at `(2,6)`. Beds occupy `(2,2), (3,2), (4,2), (4,3), (4,4)`: three along
each axis sharing a corner. An empty blocking stone base at `(2,4)` exposes its
ground outline; a lamp at `(1,4)` supports front/back contact inspection. The
furniture occupies `(6,2), (7,2), (6,3), (7,3)`, and the gardener can stand at
`(5,3)` or `(6,4)` beside its seats. Inspect from `(6,1)` behind the group and
`(6,4)` in front. The pot is at `(7,6)` and palm at `(1,1)`. No collectibles or
trap are present in this fixture. Use the regular controls, zoom, and Fit map.

Calibration inspection requires close views as well as the fitted whole scene.
All four local PNGs must decode. Original asset sources are retained; the revised
foliage and authored planter bases are separate files. Imported scenes are now
listed as **08 — Imported scene**.

- Desktop: 1280 × 900. Map and controls sit side by side. Focus the map before using keyboard movement. The mobile directional pad is hidden for a fine pointer.
- Mobile: 390 × 844. The map appears before the controls; scroll as needed. A visible four-button directional cross occupies its own HUD row below the canvas, with a Jump button to its left and camera buttons below it. Neither movement control may cover map tiles or camera buttons. Touch dragging the map pans; holding a directional button walks; scrolling outside either control scrolls the page.
- A coarse pointer also displays the directional pad on wider screens. There must be no horizontal document overflow, clipped labels, or overlapping controls.

Record screenshots and browser console/runtime errors for each tested state. Inspect the rendered page and public controls; do not depend on private engine fields or a QA-only global. Scene JSON exports can corroborate traveler locations and floor IDs.

## Controls and exact routes

Coordinates are `(column, row)`. Omitted floor IDs mean `ground`. Keyboard and directional-pad buttons preserve the original engine's axes: W northeast, D southeast, S southwest, A northwest. This matches `Client/engine/move-handler.js` and the user's explicit W upper-right direction. The cross sits at the bottom right of the game HUD. Hold a direction to continue stepping; release to finish the current step and stop. WASD and arrows use the same mapping:

| Keys | Grid direction |
|---|---|
| W / Up ↗ | `(+c, 0)` |
| D / Right ↘ | `(0, +r)` |
| S / Down ↙ | `(-c, 0)` |
| A / Left ↖ | `(0, -r)` |
| W + D / Up + Right → | `(+c, +r)` |
| W + A / Up + Left ↑ | `(+c, -r)` |
| S + D / Down + Right ↓ | `(-c, +r)` |
| S + A / Down + Left ← | `(-c, -r)` |

The jump-scene traveler starts at **(2, 6), Ground / 0 px**. Space alone hops in place; hold W and press Space immediately to leap from `(2,6), Ground` onto `(4,6), Bridge`. The equivalent touch gesture holds ↗ with one finger and taps Jump with a second. Release the direction during flight to stay on the landing tile. The bridge landing must remain at **72 px** after flight; it must not fall through to ground. Raised jumps peak at most **84 px above takeoff** (just 12 pixels above this bridge), while neutral/same-floor hops peak at **40 px**. Default flight duration is **0.8 seconds**; the maximum forward distance is two cells, with the first reachable raised platform preferred.

The trap launches along ground row 6, from `(0,6)` toward `(10,6)`, at **20 px absolute height** and **5 tiles per second**. Its first launch occurs **1.6 seconds** after a scene starts, restarts, resumes, or the trap is enabled; later launches occur every **2.4 seconds**. An idle traveler at `(2,6)` is hit at approximately **2.0 seconds** after restart. Press neutral Space at approximately **1.6 seconds** to clear that first bolt. Use the visibly approaching bolt for manual timing. Being on the 72-pixel bridge also clears the low lane. Hits increment a visible counter without respawn or a life limit. Pause clears pending bolts and resets hits. Turning the trap off clears bolts but retains the hit count; importing scene JSON leaves the host trap rule off.

For the original stair and floor checks below, select **“03 — Above & below”**, whose traveler starts at **(1, 6), Ground / 0 px** and whose trap is absent. All bridge tiles are at height 72, covering **c = 4..6, r = 4..6**.

- West stairs: ground `(1,5)` at 18 px → `(2,5)` at 36 px → `(3,5)` at 54 px → bridge `(4,5)` at 72 px. From spawn, briefly hold A for one step, then hold W along the stair flight. Reverse with S.
- East stairs: bridge `(6,5)` at 72 px → ground `(7,5)` at 54 px → `(8,5)` at 36 px → `(9,5)` at 18 px. Continue to `(9,6)` for height 0. Both stair links are bidirectional.
- Underpass: select **Ground**, then route from spawn through ground `(2,6)`, `(3,6)`, `(4,6)`, `(5,6)`, then `(5,5)`. This remains at height 0. For keyboard control, hold W along row 6, release near column 5, then use A to step to row 5.
- Two distinct lights share **(5,5)**: one on Ground and one on Bridge. A third light is at **(6,4), Bridge**.
- Ground has a blocking stone at **(5,4)**. Bridge has a blocking hedge at **(5,6)**. Ground `(5,6)` remains open beneath that hedge; Bridge `(5,4)` remains open above the stone.

Keyboard taps must last long enough to initiate a step. Exact grid position is visible in the Traveler readout. A diagonal step only succeeds when the adjacent cells needed to avoid cutting a corner are clear.

## Observable checks

1. **Jump-scene render (select 04 first):** The bridge, both stair flights, launcher, rose lane, and traveler are visible. Traveler initially reads `2, 6`, floor reads `Ground / 0 px`, movement reads `Grounded`, collection reads `0 / 3`, and Trap hits initially reads `0`. The first visible bolt can then hit the idle traveler. The stage remains usable after resizing. Select “03 — Above & below” for checks 2–4 and 7; its traveler starts at `1, 6` and trap controls are hidden.
2. **Floor views:** Select Ground; the bridge and its objects disappear, exposing the underpass and ground light. Select Bridge; the upper tiles are visible and clicks target that floor. Select All floors; the visible top surface is picked. View changes must leave the traveler in place. Follow traveler automatically adjusts the cutaway when a stair transition completes.
3. **Independent floors:** On Ground, collect `(5,5)` via the underpass. The counter becomes `1 / 3`; the bridge light at the same coordinates remains. Select Bridge and click its `(5,5)` light. The traveler must use a stair connection, rise smoothly to 72 px, and collect only the upper light. Collect `(6,4), Bridge` for `3 / 3` and the completion message. Restart restores all three.
4. **Stairs and height:** Walk the full west-to-east stair route using held W where column increases. The live height readout changes smoothly across the 18/36/54/72-pixel steps. The floor label changes to Bridge only on entry and back to Ground on exit. Walking off an unlinked bridge edge must be blocked; overlapping ground must not cause a drop or teleport.
5. **Keyboard lifecycle:** Verify W, A, S, D, arrows, combined directions, release, and reversing. Clicking a distant tile then pressing a movement key replaces the click route. Hold a key, move focus to a select/input or another window, then release; returning must not resume held movement. Form controls must remain usable. Pause, restart, and scene changes clear held movement. Resume focuses the world for new keys.
6. **Touch directional pad:** At 390px verify a four-button cross at the bottom right of the game HUD, with no joystick. Hold each button: W ↗, D ↘, S ↙, A ↖. The traveler follows the same tile axes as keyboard input. Hold two buttons together to combine directions. Release outside the pad or cancel the touch: the traveler must stop after its current step, pressed feedback must clear, and the camera must remain stationary. Pause and scene changes reset it. A separate map drag still pans without sending the traveler walking.
7. **Collision by floor:** Ground `(5,4)` is blocked; Bridge `(5,4)` is open. Bridge `(5,6)` is blocked; Ground `(5,6)` is open. Neither keyboard nor directional pad may pass through a blocker, water, missing floor, or a diagonal corner. A click path routes around obstacles.
8. **Camera:** Drag horizontally and vertically, zoom with the wheel, then click Fit map. Repeat using the visible + and − controls on mobile. A drag must not also send the traveler walking. All levels must fit without clipping the top of the bridge or stair flights.
9. **Original scenes:** Select “01 — Quiet courtyard”. The traveler starts at `4, 7`, counter is `0 / 0`, and stone `(4,4)` / hedge `(2,2)` remain blocked. Select “02 — Collect the lights”. Gems at `(2,4)`, `(4,2)`, `(6,4)` form the original three-light challenge. Both version-1 scenes support keyboard and directional-pad movement; floor options contain only Ground plus the view modes.
10. **Export/import:** Export while the traveler is on Bridge, then import. Version 2, `levels`, `links`, traveler floor, and remaining lights must survive. Floor options refresh and All floors is restored. Imported remaining lights form a fresh challenge; previous collection-counter history is not stored. A version-1 export from an original scene must still load.
11. **Import rejection:** Import malformed JSON and structurally invalid JSON, such as `{ "version": 99 }`. Expect explicit readable feedback; the current map stays visible and playable. The file input has accessible label “Import scene”.
12. **Repeated use:** Switch between all seven scenes, restart, pause/resume, and resize repeatedly. Expect one canvas, one directional pad, and one mobile Jump button, stable controls, no duplicate movement/collection, and no accumulating console errors. The original courtyard, collection, and Above & below scene data remain unchanged.
13. **Jump onto the second floor:** In Jump & dodge, turn the trap off and restart as needed. From `(2,6), Ground`, hold W and press Space immediately, then release W during flight. Expect an arc to `(4,6), Bridge`, a feet-height peak no higher than 84 px above the starting ground, Airborne during flight, then Grounded / Bridge / 72 px. Wait several frames to verify the traveler stands on the bridge rather than continuing through it. Export and confirm its `level` is `bridge`. Do not accept a visual hop that lands back on ground as a pass. Holding Space must not continually jump. A neutral hop remains on the same tile.
14. **Flying trap collision and dodge:** Restart and stay idle at `(2,6)` until the first bolt hits; verify visible flight, hit feedback, and count `1`. Restart, then perform a neutral Space hop as the first bolt approaches (about 1.6 seconds after restart). The low bolt passes beneath the airborne traveler and the hit count remains `0` after that bolt passes. Compare these under the same timing/position conditions. Separately reach the bridge and wait for another bolt; standing at height 72 must avoid its ground-lane hit. Turn Trap off and verify pending bolts disappear and no new bolts spawn. Pause/resume and restart must not leave old projectiles or duplicate trap timers.
15. **Mobile jump with held direction:** At 390px, hold the ↗ directional-pad button and tap Jump using a second touch. Jump activation must preserve the held direction long enough to launch onto `(4,6), Bridge`; releasing either touch must clear its pressed state. The camera must remain stationary and the two controls must have separate hit areas. Also test a neutral Jump-button hop, pause during flight, resume, and restart. Verify the same floor landing and height limit as desktop.

## Woodland atelier: texture and sprite checks

Select **“05 — Woodland atelier”**. This optional fifth scene is a 9 × 9 mossy island with warm paths, four broad oaks, mushroom clusters, two mossy rocks, and a small ranger wearing a golden hat and green cloak. The first four presets and Jump & dodge remain available. Imported scenes are labeled **“08 — Imported scene”**.

The traveler starts at **(4,6), Ground / 0 px**. The firefly lantern is at **(4,2)**. The direct collection route is `(4,6) → (4,5) → (4,4) → (4,3) → (4,2)`: hold **A / Left / ↖** for four steps, or click the lantern's tile. The counter changes from `0 / 1` to `1 / 1`, the lantern disappears, and the existing completion message appears. The host identifies this collectible through `data.role: "collectible"`; its sprite appearance does not determine the rule.

- **Grounding and depth:** Feet touch the path; trunks, mushrooms, and rocks rest on their cells without floating or clipped tops. Walk behind and in front of an oak. Its canopy should naturally cover the traveler only when the traveler is behind it. Blocking oak cells are `(1,2)`, `(6,1)`, `(7,3)`, `(1,7)`; mushrooms occupy `(2,3)` and `(6,5)`; rocks occupy `(3,2)` and `(7,7)`. The outer water ring is impassable.
- **Four facing directions:** Around the open center, walk W to `(5,4)`, D to `(5,5)`, S to `(4,5)`, then A to `(4,4)`. Expect northeast, southeast, southwest, northwest facings respectively. Southern facings show the face; northern facings show the pack. Four distinct walk frames move the feet and cloak. Releasing movement returns to a gentle two-frame idle in the last facing direction. Combined keys use the corresponding nearest authored facing.
- **Jump and pause:** Space alone hops in place, switches to the airborne pose, and lands with feet at height 0. Pause during movement or idle: both simulation and sprite animation stop. Resume continues; repeated pause/resume must not accelerate animation or duplicate controls.
- **Restart:** After collecting, Restart restores `(4,6)`, the lantern, and `0 / 1`. Moss/path variants stay at exactly the same coordinates after restart, repeated Fit map, pan/zoom, and returning from another scene.
- **Theme round-trip:** Export and import the woodland scene. Named textures, frame rectangles, anchors, animation clips, directional mappings, physical heights, and collectible data survive. The atlas URL remains a reference; the JSON does not embed the image. Importing in a different deployment requires that referenced image URL to be available there.
- **Desktop and mobile:** At 1280 × 900 and 390 × 844, fit the map and inspect canopy tops, lantern detail, sprite feet, and controls. The entire island must remain visible without clipping. Mobile movement and Jump retain the existing controls and axes.

The original four presets require no asset requests. Woodland uses one locally bundled SVG atlas, imported with Vite's `?url` handling from `demo/art/woodland.svg`; it makes no third-party requests. Its artwork is authored in `demo/art/build-atlas.mjs` and reproducible with `node demo/art/build-atlas.mjs` from `Runtime/`. `demo/art-pack.ts` supplies the replaceable manifest and fixed scene layout. Image failure recovery, independent simultaneous instances, and lifecycle disposal need separate focused runtime checks; this demo alone does not prove them.
