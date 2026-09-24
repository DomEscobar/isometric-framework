# Scoped new Hybrid LIVE attempt — executed, rejected upstream

## Actual result

New independent run **72e30617e8294e1f8529ffccaee00286** was created via the real loopback service, explicitly authorized, and processed by independent systemd worker. One actual OpenRouter planner POST, no manual phase handoff. Terminal `needs_attention`: **HTTP400 INVALID_ARGUMENT**, `Request contains an invalid argument.` Provider metadata names Google AI Studio and a preceding Google400. It does NOT name the offending argument. No false diagnosis that the exact schema field is proven faulty.

Call `79320908cff658062cc43764eb539e5d706a5f747029a98e62c212ef5011357a`; request SHA256 `1b56746f898a2cc7740d717d54969a955253e98a7d236949c1552cc0dae5b0ca`; response SHA256 `8805cd29f617a498f91f6982b1ccb1e0280665143e1eafd340c791ea32fb4b4b`.

Exact raw HTTP response retained privately in `data/hybrid-errors/<call-id>/response.bin` with request-bound diagnostic, 0700 directory /0600 files. Exported sanitized allowlist excludes provider user/account identifiers. This error is not a completion receipt or billing settlement. New hold817152; known actual billed cost UNKNOWN, not zero.

**Central holds6541016 microUSD; remaining3458984 microUSD.** Old817152 remains unchanged. No image purchased, no source/sample/final, no ZIP or review verdict exists. The new unknown outcome blocks further purchases. No second new run/resume paid request was attempted.

## Implementation and evidence

`hybrid_store.py` adds immutable `hybrid_liability_authorizations` plus no-update/delete triggers. Operator-only insertion binds exact historical call/request/full hold, new run/config, explicit approval text, project cap, lifetime run limits and expiry. No global bypass. Transactional checks reject changed bindings, unlisted/new unknowns, cross-run reuse, exhausted limits, insufficient full-budget headroom, stale fence and cancellation. Old rows are never updated by acknowledgment.

Authorization `805541c1655a38fd677f74b8045e9a4c9f481d973ef4344155904b8c5ae1057c`; max1image, max6total calls, max1local correction,1800seconds,4276136 microUSD. Free auth and exact metadata succeeded; quote11000 and four model reserves817152 each established3279608 first-candidate headroom. Conservative reservation method unchanged.

Strict initial RED verified absent capability, subsequent RED verified missing whole-authorized-budget headroom rejection; implemented GREEN. Full isolated suite: **283 passed**, existing162 warnings. `tests/test_hybrid_acknowledgment.py` adds13 cases including default blocker, new unknown, old unchanged, drift/reuse/lifetime protections. Full suite evidence `evidence/hybrid-scoped-attempt/tests.txt`.

`tools/verify_scoped_hybrid.py` reread every old row: all10 jobs,7 reviews,7 runs,1 call,34 events equal original field-for-field including exact request/record strings. Original snapshots private `data/hybrid-scoped-before.json`. Public hashes/counts in `verification.json`.

Real Playwright loaded run after reload, verified call1/image0, exact HTTP400 status, no download, production409, no JS errors/mobile overflow. Screenshots `live-status.png`, `live-status-native.png`, `live-mobile.png`; `browser-proof.json`, `terminal-run.json`. Subagent inspected native screenshot: needs_attention, LIVE, image limit1, USD0.817152 hold and HTTP400/no automatic retry all visible. Parent visual review remains separate. Both own systemd services active; no public deployment or game/animation changes.

## Read-only diagnosis and concrete remediation

Free current endpoint metadata lists response_format/structured_outputs support on Google and Google AI Studio; auth succeeded just before actual POST. Exact submitted schema retained in `submitted-schema.json`. Google documentation https://ai.google.dev/gemini-api/docs/structured-output explicitly warns that very large/deeply nested schemas can be rejected and only a JSON Schema subset is supported. The actual request contains nested grid/transition arrays, `$defs`/`$ref`, const, string constraints and a schema-valued dictionary. Google's documented dictionary support means blaming additionalProperties alone is NOT justified.

The proven failure is upstream request validation, not the prior local unknown blocker, missing credentials or a model-completion validation failure. Concrete next repair: create and offline-test a provider wire-contract adapter with a reduced documented schema (inline refs, fixed material keys, simple primitive arrays, keep ALL strict semantic/geometry/length checks in local Plan/compile_layout), or explicit documented JSON-object mode with local strict validation. Pin and record that transport contract; do not mutate this sealed run or claim the change works without a newly authorized live test. Provide these request/response hashes and private response through authorized provider support to identify the rejected field. No paid schema-bisection probes were made. Another paid attempt requires fresh explicit approval covering BOTH retained unknown liabilities; remaining budget alone is not authorization.

## Files

Changed `hybrid_store.py`, `HYBRID_SERVICE.md`; added `tests/test_hybrid_acknowledgment.py`, `HYBRID_SCOPED_AUTHORIZATION.md`, this report, operator single-use `tools/start_scoped_hybrid_once.py`, read-only `tools/scoped_hybrid_readback.mjs`, `tools/verify_scoped_hybrid.py`, and evidence directory. Reusable workbench skill now distinguishes explicit acknowledged unresolved liability from settlement and prohibits broad bypass.
