# Independent framework trials

Use this optional source-checkout tool when testing whether a fresh coding agent
can build from the framework. Ordinary game production does not require a trial.

```sh
node scripts/framework-trial.mjs prepare --framework . --contract path/to/approved-contract.md --reference path/to/style.png --out test-results/trial-01
```

This copies source, the neutral starter, skills and selected API guides into
`workspace/`. The builder can build its local package and use the standalone
starter there; no example host is preselected. Maintainer routing remains available
for explicit framework repairs. Runtime tests and historical documentation are
not copied; run maintenance suites in the source checkout when they are needed.
Existing games, example artwork, historical trial reports, dependency folders and
capture archives are omitted. The approved contract becomes `PROJECT_CONTRACT.md`;
explicit references go into `reference/`. The tool prints their actual paths.
The source snapshot has no example entrypoint: the builder creates its own host
and build configuration. Dependencies must be installed or supplied separately.

Launch a **fresh agent context** with the user's available agent tool, assigning
only that workspace and contract. Record the returned agent/session ID and model:

```json
{"kind":"session","actor":"builder","agentId":"actual-returned-id","model":"actual-selected-model","note":"Fresh builder assigned the snapshot and contract"}
```

```sh
node scripts/framework-trial.mjs record test-results/trial-01 session.json
node scripts/framework-trial.mjs status test-results/trial-01
```

The recorder supplies observation timestamps; these are not active execution-time
measurements. It never starts an agent, sends a message, submits a generation or
grants spending permission. A separate folder is not an OS sandbox.

The builder owns implementation and required evidence. The reviewer reports
located defects and their evidence. General framework repairs belong to the
supervisor; record a `framework-update` after applying and checking the update in
the snapshot. This captures another framework hash set. Existing check receipts
still follow the production tool's freshness rules; this recorder cannot accept a
world or replace those receipts.

A checkpoint event uses `kind: "checkpoint"`, `actor: "reviewer"`, a `checkpoint`
name, `verdict` (`pass`, `fail`, `unverified`) and a concrete `note` with evidence
paths. Optional `cause` is `framework-gap`, `instruction-conflict`,
`execution-error`, `candidate-failure`, or `review-error`. Diagnose before deciding
whether a framework patch is warranted.

If the supervisor supplies host code, layout coordinates or implementation recipes,
record `kind: "intervention"`, `actor: "supervisor"` and the actual help in `note`.
Status then says `assisted`. Observational criticism alone is not implementation
help. A model replacement requires another session event; do not attribute its
results to the earlier builder. Changed requirements/references require an explicit
new trial baseline rather than silently rewriting the original inputs.

Keep events outside the builder workspace. Exclusive sequential files and hash
links detect accidental event replacement; they are not authenticated authorship.
`no-assistance-recorded` means exactly that, not independently proven execution.
The launcher/session history is still needed to assess actual isolation and help.
For final evidence of the repaired framework, start a fresh trial with its current
version and the original requirements, without the preceding solution discussion.
