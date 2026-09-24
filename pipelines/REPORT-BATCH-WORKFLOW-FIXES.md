# Bounded batch workflow fixes (offline development)

## Delivered
- New batches terminate `succeeded` only if both styles have valid approved strict reviews; any terminal failure is `blocked`. Per-style results use the same distinction.
- Historical `completed`/`stopped` records remain untouched. API adds derived `display_status`, `terminal`, `can_resume`, and `can_cancel`. Retained status/list/resume-on-terminal do not read reference cache files or revalidate mutable adapter code.
- Durable cancellation uses a separate `overnight_cancellations` intent table in the existing ledger. Concurrent worker saves cannot erase it. Already in-flight calls may finish and retain their receipt; subsequent stages stop. Cancellation never releases reservations, deletes jobs, or reopens on resume. Existing terminal batches are not rewritten by cancellation.
- GET `/api/overnight-batch` discovers saved batches; POST `/{id}/cancel` cancels. Existing GET/start/resume return additive display fields.
- Workbench panel discovers server-side saved batches (not just localStorage), shows each style's phase/result/source/candidate/evaluation/stop reason, provides status/resume/cancel with readback, persists selection, polls running batches, and links original diagnostic sources and retained evaluation JSON. It explicitly labels zero repairs and separate owner acceptance.

## Verification actually executed
- TDD failures observed for blocked-vs-completed semantics, missing display API, missing cancellation, cancelled per-style labels, missing discovery route, and absent browser UI; then passed.
- `python3 -m pytest tests -q` in isolated source copy `/tmp/batch-fixes-tests-77zdpp0_`: **146 passed, 57 existing deprecation warnings**. Includes parent's concurrent adapter/engine changes as snapshotted at copy creation. No import of live `app.py`; no production data copied except read-only historical layout fixture.
- `node tests/batch-ui-browser.mjs`: PASS saved discovery, resume/readback, cancellation/reload, mobile width, no page errors. Real headless browser over current static files with **MOCK HTTP**; not proof of live provider calls.
- `node --check tests/overnight-browser.mjs`: PASS. Historical retained-result harness adjusted for additive display fields; not run against live server/data.
- Full Python output: `evidence/batch-workflow-fixes/pytest.txt`.

## Boundaries
No purchases, policies, deployment, live DB writes, or historical artifact rewrites. Neither `auto_adapter.py` nor `auto_repair.py` edited by this worker. Creating the app after future deployment will create the cancellation table; no live app was created here.

This is not a unified general-purpose repair system: the overnight service still permits one initial image per style and zero repairs. Reference-independent **readback** is supported; new starts and active execution retain the existing cache-bound authorization validation and fail closed if references are missing. No new artwork success claimed. Existing source/evaluation links do not yet provide a one-click layout/candidate gameplay loader.

Files changed: `overnight_batch.py`, `static/index.html`, `static/workflows.js`, `tests/test_overnight_batch.py`, `tests/overnight-browser.mjs`; new: `tests/batch-ui-browser.mjs`, this report, `evidence/batch-workflow-fixes/pytest.txt`.

Issue during work: first targeted test hit a transient syntax error while the parent was editing `auto_adapter.py`; no edit made to that file. The next run reached the intended assertion failure. Repository has no `.git`, so no git diff/status available.
