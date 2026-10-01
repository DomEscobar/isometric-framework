# Landscape verification (v5 / production v2)

Use this inside the existing six production stages. It does not add a landscape
method or a second acceptance flow.

`production.landscape` declares project-root `geometrySource`, `compositionRecipe`, `densityMatrix`, `decisions`,
`compositionReport`, `pairedCaptures`, and `wholeMapViews`. The geometry source
is an external JSON export with `coordinateSpace`, `projection`, `origin`,
`canvas`, `layout.path`, named `masks.*.path`, and uniquely identified instances.
Its nested paths resolve beside the geometry file and must be included in every
consuming check's inputs. Every layout/placement check must name exactly the
export's layout file as its source; a second independently maintained copy is rejected.

The compositor report names the canonical project-root `geometrySource`; the
recipe's `geometrySource` resolves beside the recipe and must reach that same file.
The report binds `geometrySha256`, `recipeSha256`, and a project-root `inputHashes`
map covering all consumed geometry, masks, layout, materials and contact assets.
`protectedPixelReport` and `output` contain hashed report-relative paths.
The required `passOrder` is `baseSurface`, `regionalContacts`, `objectUnderlays`;
`protectedPixelReport.unchangedAfterUnderlays` must be true. Assembly, static, and
final receipts reject omitted consumed inputs or stale sources and derivatives.

Each v5 ticket begins with `--author-id`. Submission carries the same `authorId`;
the reviewer must differ. A review supplies one judgment for every protected
requirement/view, including image-backed automatic art/layout checks. Image
reviews additionally bind capture metadata to the actual
evidence path and hash. Ground-only/dressed pairs share camera, viewport,
renderer, world/time state, geometry hash, and whole-map bounds; only the view
mode changes. Final review includes each declared whole-map view and a detail
capture. A stopped decision stays stopped unless a later selected record for the
same scope and variant has explicit authorization.

Use records with this shape (values shown are examples, not framework constants):

```json
{
  "densityMatrix": {"version":1,"views":[{"id":"desktop","sourcePixels":[64,32],"exportPixels":[128,64],"worldSize":[1024,768],"cameraZoom":1,"cssViewport":[1280,720],"dpr":2,"rendererPixels":[2560,1440],"textures":[1024,512],"rendererLimits":{"maxTexture":4096}}]},
  "decision": {"id":"bank-study","scope":"shore","variant":"reed-bank-a","status":"stopped","evidence":"reviews/bank-a.json"},
  "capture": {"id":"shore-ground","path":"captures/shore-ground.png","sha256":"<image-sha256>","view":"desktop","mode":"ground-only","pairId":"shore","camera":{"x":320,"y":240,"zoom":1},"viewport":[1280,720],"renderer":{"dpr":2},"worldState":"seed-17","timeState":"midday","geometrySource":"diagnostics/landscape/geometry.json","geometrySha256":"<geometry-sha256>","scope":"whole-map","worldBounds":[1024,768]},
  "judgment": {"requirement":"connections","view":"desktop","status":"pass","reviewer":"reviewer-42","observed":"Inspected bank and foundation contacts."}
}
```

The dressed partner repeats every capture field except `id`, `mode` (`dressed`),
and its evidence path/hash. A later `selected` record for the stopped scope and
variant needs a nonempty `authorization` field.

These records make omissions and stale evidence detectable; they do not prove
that a person or subagent actually inspected an image. The independent reviewer
must open the runtime captures, record observed differences against the rubric,
and distinguish synthetic pipeline tests from acceptance of the game's art.
