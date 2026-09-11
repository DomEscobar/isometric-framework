# Larkspur Crossing

Larkspur Crossing is a compact playable village: four exterior buildings, a
curved stream, a flush three-cell crossing, planted margins, animated water and
elm leaves, and one controllable traveler. It uses only the host's local PNGs and
the public framework API.

Start it from the repository root:

```powershell
npx vite --config examples/new-village/vite.config.mjs --host 127.0.0.1 --port 4212 --strictPort
```

Open `http://127.0.0.1:4212/examples/new-village/`. Click or tap a path to walk;
W/A/S/D and the directional pad use the framework tile axes. Pause freezes the
runtime, including the water and leaf loops. Interiors are outside this host's
scope.

Build a standalone output with:

```powershell
npx vite build --config examples/new-village/vite.config.mjs
```

The output is `test-results/new-village/production/`. Runtime assets are all under
this directory; it does not require a snapshot or `test-results` input path.

Preview that output with:

```powershell
npx vite preview --config examples/new-village/vite.config.mjs --host 127.0.0.1 --port 4213 --strictPort
```

Run the pointer-journey smoke check against an explicitly started host with:

```powershell
$env:RUNTIME_QA_URL='http://127.0.0.1:4212/examples/new-village/'
node tests/new-village-browser.mjs --out test-results/new-village/browser-review
```

`layout.json` is the shared route, planting, entrance and bridge contract.
`art/art-contract.json`, `art/binding.json`, final masks, and `art/provenance/`
retain measured integration and compact generation provenance. The textual prompts
and provider records are historical source records; raw candidates and rejected
packs are intentionally not copied here. The original nine built-in image calls
are historical and authorize no further generation.

This migrated host has no full final acceptance claim. A build, decoded asset
metadata, structural checks, or a browser journey does not establish visual,
motion, performance, or complete world acceptance.
