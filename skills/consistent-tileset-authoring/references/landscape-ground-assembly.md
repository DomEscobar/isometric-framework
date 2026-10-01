# Deterministic landscape-ground composition

`compose-landscape-ground.py` adds explicit contact art and object-specific ground patches to a quilted or prepared flat surface. It is an offline compositor: the host owns geography, masks, instances, collision and navigation. It does not infer a route, create fallback art, raise terrain, or change the runtime scene.

```sh
uv run --python 3.12 --with Pillow==12.3.0 --with numpy==2.5.0 python -B skills/consistent-tileset-authoring/scripts/compose-landscape-ground.py recipe.json --out composed-ground
node --experimental-strip-types skills/consistent-tileset-authoring/scripts/bind-ground.mjs game/scene.json composed-ground/packed-art.json --out bound-ground --image-url ./art/composed-ground/ground.png
```

Start from the example recipe. `geometrySource` is one local JSON export and is the only layout and instance authority. Its required fields are `version`, nonempty `coordinateSpace` and `projection`, `origin`, `canvas`, `masks`, `layout`, and `instances`. Geometry masks and layout paths are local to the geometry JSON directory and each has the required SHA-256 of its actual source bytes. The surface must have the exact canvas and origin of this export.

The recipe may refer to geometry mask IDs and geometry instance IDs; it cannot embed a second map, origin or instance list. `regionalMaterials` names full-canvas prepared or quilted RGBA sources, and each regional path copies its source through the host mask. A geometry instance contains its ID, pixel anchor, positive `[x,y]` transform scale and a required `contactId`: the exact underlay ID, or explicit `null` when no baked contact is intended. Every non-null contact must be composed exactly once. An underlay uses that anchor and scale as its only target transform; its required `assetAnchor` is the pixel contact point in the source patch and `exportScale` states its source density. The compositor scales pixels and source anchor by `instanceScale/exportScale` with nearest sampling. This binds the root patch, sprite anchor, scale and host standing geometry to the same instance instead of inventing a second placement.

Contacts are explicit RGBA assets with one of eight named orientations, target `anchor`, source `assetAnchor`, inside/outside masks, `edgeWidth`, and an allowed placement mask. `pathExterior` computes the exposed four-neighbour boundary of the union of every regional-path mask and allows the configured inward band, never an internal route pixel, so T and four-way intersections do not receive seams. The declared orientation must have a matching adjacent inside/outside boundary. Opaque contact pixels may not overlap an earlier contact. `materialPair` is likewise explicit and must touch both declared material masks. Missing orientation, masks, asset, anchor, unknown family, off-mask alpha, geometry hash, origin mismatch, or missing contacts is an error.

After the contact pass, underlays are clipped to their allowed mask with every declared protected mask removed. Every route mask and every geometry mask marked semantic `water` must be protected. `protected-pixels.png` records the protected union and the compositor verifies that its pixels are byte-identical before and after this pass. Contacts may alter their declared bands; underlays cannot alter roads or water.

The binder-compatible output contains `ground.png`, `manifest.json`, and `packed-art.json`. `composition-report.json` has the exact recipe-declared `geometrySource`, actual `geometrySha256`, pass order, contact and underlay pixel counts, `protectedPixelReport` and output hashes. Its generated paths are relative to the report directory. The geometry source string remains recipe-relative so production gates can match it exactly; geometry-owned nested paths resolve relative to the geometry file.

Synthetic tests establish pixel and geometry invariants only. They do not establish visual quality, browser behavior, motion, touch, or performance acceptance.
