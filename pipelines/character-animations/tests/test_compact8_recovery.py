import sqlite3

import pytest

from tools.compact8_recovery import wait_stage_id


def test_exact_stage_wait_does_not_accept_stale_terminal_job_status(tmp_path) -> None:
    database = tmp_path / "jobs.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE stage_jobs (id TEXT PRIMARY KEY, state TEXT, error TEXT, result_json TEXT)"
        )
        connection.execute(
            "INSERT INTO stage_jobs VALUES ('old-stage', 'completed', NULL, '{}')"
        )
        connection.execute(
            "INSERT INTO stage_jobs VALUES ('new-stage', 'queued', NULL, NULL)"
        )

    with pytest.raises(RuntimeError, match="exact stage new-stage timed out"):
        wait_stage_id(database, "new-stage", timeout=0.01, interval=0.001)
