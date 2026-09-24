from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

SAFE_BASENAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")
STATES = {"queued", "running", "needs_review", "completed", "failed", "needs_attention"}


def now() -> float:
    return time.time()


def dumps(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def loads(data: str | None, default: Any) -> Any:
    if not data:
        return default
    return json.loads(data)


def safe_basename(name: str) -> bool:
    if not isinstance(name, str):
        return False
    if not SAFE_BASENAME_RE.fullmatch(name):
        return False
    if name in {".", ".."} or "/" in name or "\\" in name:
        return False
    return True


class Store:
    def __init__(self, db_path: str | Path, data_dir: str | Path):
        self.db_path = Path(db_path)
        self.data_dir = Path(data_dir)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    options_json TEXT NOT NULL,
                    latest_stage TEXT,
                    message TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS stage_jobs (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    stage TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    worker_id TEXT,
                    created_at REAL NOT NULL,
                    claimed_at REAL,
                    finished_at REAL
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    bytes INTEGER NOT NULL,
                    stage TEXT,
                    revision INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    PRIMARY KEY(job_id, name)
                );
                CREATE TABLE IF NOT EXISTS reviews (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    artifact TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS automatic_reviews (
                    id TEXT PRIMARY KEY,
                    stage_job_id TEXT NOT NULL UNIQUE REFERENCES stage_jobs(id) ON DELETE CASCADE,
                    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    source_artifact TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL,
                    source_revision INTEGER NOT NULL,
                    model TEXT NOT NULL,
                    status TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                """
            )

    def job_dir(self, job_id: str) -> Path:
        if not safe_basename(job_id):
            raise ValueError("invalid job id")
        return self.data_dir / job_id

    def create_job(self, source_name: str, options: dict[str, Any], content: bytes) -> dict[str, Any]:
        if not safe_basename(source_name):
            raise ValueError("invalid source filename")
        job_id = uuid.uuid4().hex
        job_dir = self.job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=False)
        source_path = job_dir / "reference.png"
        source_path.write_bytes(content)
        ts = now()
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO jobs(id,state,source_name,options_json,latest_stage,message,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (job_id, "queued", "reference.png", dumps(options), None, None, ts, ts),
            )
            self.upsert_artifact(conn, job_id, "reference.png", "upload", source_path)
        return self.get_job(job_id)

    def list_jobs(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
        return [self._job_from_row(r) for r in rows]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                return None
            job = self._job_from_row(row)
            job["artifacts"] = self.list_artifacts(job_id, conn)
            job["automatic_reviews"] = self.list_automatic_reviews(job_id, conn)
            return job

    def _job_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "state": row["state"],
            "source_name": row["source_name"],
            "options": loads(row["options_json"], {}),
            "latest_stage": row["latest_stage"],
            "message": row["message"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def set_job_state(self, job_id: str, state: str, latest_stage: str | None = None, message: str | None = None) -> None:
        if state not in STATES:
            raise ValueError("invalid state")
        with self.connect() as conn:
            conn.execute(
                "UPDATE jobs SET state=?, latest_stage=COALESCE(?, latest_stage), message=?, updated_at=? WHERE id=?",
                (state, latest_stage, message, now(), job_id),
            )

    def enqueue_stage(self, job_id: str, stage: str, params: dict[str, Any]) -> dict[str, Any]:
        stage_id = uuid.uuid4().hex
        ts = now()
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO stage_jobs(id,job_id,stage,params_json,state,created_at) VALUES(?,?,?,?,?,?)",
                (stage_id, job_id, stage, dumps(params), "queued", ts),
            )
            conn.execute("UPDATE jobs SET state=?, latest_stage=?, updated_at=? WHERE id=?", ("queued", stage, ts, job_id))
        return {"id": stage_id, "job_id": job_id, "stage": stage, "params": params, "state": "queued"}

    def claim_next_stage(self, worker_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM stage_jobs WHERE state='queued' ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            if not row:
                conn.execute("COMMIT")
                return None
            ts = now()
            conn.execute(
                "UPDATE stage_jobs SET state='running', worker_id=?, claimed_at=? WHERE id=? AND state='queued'",
                (worker_id, ts, row["id"]),
            )
            conn.execute(
                "UPDATE jobs SET state='running', latest_stage=?, updated_at=? WHERE id=?",
                (row["stage"], ts, row["job_id"]),
            )
            conn.execute("COMMIT")
        return {
            "id": row["id"],
            "job_id": row["job_id"],
            "stage": row["stage"],
            "params": loads(row["params_json"], {}),
            "state": "running",
        }

    def finish_stage(self, stage_job: dict[str, Any], result: dict[str, Any], artifact_names: list[str]) -> None:
        status = result.get("status")
        if status == "needs_review":
            job_state = "needs_review"
        elif status == "completed":
            job_state = "completed"
        elif status == "needs_attention":
            job_state = "needs_attention"
        else:
            job_state = "needs_attention"
        job_id = stage_job["job_id"]
        stage = stage_job["stage"]
        ts = now()
        with self.connect() as conn:
            for name in artifact_names:
                self.upsert_artifact(conn, job_id, name, stage, self.job_dir(job_id) / name)
            conn.execute(
                "UPDATE stage_jobs SET state='completed', result_json=?, finished_at=? WHERE id=?",
                (dumps(result), ts, stage_job["id"]),
            )
            conn.execute(
                "UPDATE jobs SET state=?, latest_stage=?, message=?, updated_at=? WHERE id=?",
                (job_state, stage, sanitize_message(result.get("details", {}).get("message")), ts, job_id),
            )

    def finish_automatic_review(
        self,
        stage_job: dict[str, Any],
        result: dict[str, Any],
        artifact_names: list[str],
        record: dict[str, Any],
    ) -> dict[str, Any]:
        """Atomically publish artifacts, the typed receipt, and terminal queue state."""
        status = record.get("status")
        if status not in {"approved", "rejected", "needs_attention"}:
            raise ValueError("invalid automatic review status")
        source = self.get_artifact(stage_job["job_id"], record.get("source_artifact", ""))
        if not source or source["sha256"] != record.get("source_sha256") or source["revision"] != record.get("source_revision"):
            raise Conflict("automatic review source does not match current artifact revision")
        review_id = record.get("id") or uuid.uuid4().hex
        if not safe_basename(review_id):
            raise ValueError("invalid automatic review id")
        stored = {
            **record,
            "id": review_id,
            "stage_job_id": stage_job["id"],
            "approval_type": "automatic_model_validated" if status == "approved" else None,
        }
        job_state = "needs_review" if status == "approved" else "needs_attention"
        message = sanitize_message(record.get("reason") or ("automatic source selection completed; extracted frames require review" if status == "approved" else "automatic review needs attention"))
        ts = now()
        with self.connect() as conn:
            for name in artifact_names:
                self.upsert_artifact(conn, stage_job["job_id"], name, "automatic_review", self.job_dir(stage_job["job_id"]) / name)
            conn.execute(
                "INSERT INTO automatic_reviews(id,stage_job_id,job_id,source_artifact,source_sha256,source_revision,model,status,record_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (review_id, stage_job["id"], stage_job["job_id"], record["source_artifact"], record["source_sha256"], record["source_revision"], record["model"], status, dumps(stored), ts),
            )
            conn.execute("UPDATE stage_jobs SET state='completed', result_json=?, finished_at=? WHERE id=?", (dumps(result), ts, stage_job["id"]))
            conn.execute("UPDATE jobs SET state=?, latest_stage='automatic_review', message=?, updated_at=? WHERE id=?", (job_state, message, ts, stage_job["job_id"]))
        return stored

    def list_automatic_reviews(self, job_id: str, conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        own = conn is None
        conn = conn or self.connect()
        try:
            rows = conn.execute(
                "SELECT stage_job_id,record_json FROM automatic_reviews WHERE job_id=? ORDER BY created_at DESC",
                (job_id,),
            ).fetchall()
            return [
                {**loads(row["record_json"], {}), "stage_job_id": row["stage_job_id"]}
                for row in rows
            ]
        finally:
            if own:
                conn.close()

    def fail_stage(self, stage_job: dict[str, Any], message: str, state: str = "failed") -> None:
        ts = now()
        msg = sanitize_message(message)
        with self.connect() as conn:
            conn.execute(
                "UPDATE stage_jobs SET state=?, error=?, finished_at=? WHERE id=?",
                (state, msg, ts, stage_job["id"]),
            )
            conn.execute(
                "UPDATE jobs SET state=?, latest_stage=?, message=?, updated_at=? WHERE id=?",
                (state, stage_job["stage"], msg, ts, stage_job["job_id"]),
            )

    def upsert_artifact(self, conn: sqlite3.Connection, job_id: str, name: str, stage: str, path: Path) -> None:
        if not safe_basename(name):
            raise ValueError("unsafe artifact name")
        if not path.is_file():
            raise ValueError(f"artifact missing: {name}")
        data = path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        existing = conn.execute("SELECT revision FROM artifacts WHERE job_id=? AND name=?", (job_id, name)).fetchone()
        revision = (existing["revision"] + 1) if existing else 1
        conn.execute(
            "INSERT OR REPLACE INTO artifacts(job_id,name,sha256,bytes,stage,revision,created_at) VALUES(?,?,?,?,?,?,?)",
            (job_id, name, sha, len(data), stage, revision, now()),
        )

    def list_artifacts(self, job_id: str, conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        own = conn is None
        conn = conn or self.connect()
        try:
            rows = conn.execute(
                "SELECT name,sha256,bytes,stage,revision,created_at FROM artifacts WHERE job_id=? ORDER BY name",
                (job_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            if own:
                conn.close()

    def get_artifact(self, job_id: str, name: str) -> dict[str, Any] | None:
        if not safe_basename(name):
            return None
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM artifacts WHERE job_id=? AND name=?", (job_id, name)).fetchone()
            return dict(row) if row else None

    def add_review(self, job_id: str, artifact: str, sha256: str, decision: str) -> dict[str, Any]:
        if decision not in {"approve", "reject"}:
            raise ValueError("invalid decision")
        if not re.fullmatch(r"[0-9a-f]{64}", sha256 or ""):
            raise Conflict("sha256 mismatch")
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM artifacts WHERE job_id=? AND name=?", (job_id, artifact)).fetchone()
            if not row or row["sha256"] != sha256:
                raise Conflict("artifact sha256 does not match current revision")
            review_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO reviews(id,job_id,artifact,sha256,decision,revision,created_at) VALUES(?,?,?,?,?,?,?)",
                (review_id, job_id, artifact, sha256, decision, row["revision"], now()),
            )
            if decision == "reject":
                conn.execute("UPDATE jobs SET state='needs_attention', message=?, updated_at=? WHERE id=?", ("artifact rejected", now(), job_id))
            return {"id": review_id, "approved": decision == "approve", "artifact": artifact, "sha256": sha256, "revision": row["revision"]}

    def has_approval(self, job_id: str, artifact: str | None = None) -> bool:
        with self.connect() as conn:
            parameters: tuple[Any, ...]
            artifact_filter = ""
            parameters = (job_id,)
            if artifact:
                artifact_filter = " AND r.artifact=?"
                parameters = (job_id, artifact)
            row = conn.execute(
                """
                SELECT 1
                FROM reviews AS r
                JOIN artifacts AS a
                  ON a.job_id=r.job_id
                 AND a.name=r.artifact
                 AND a.sha256=r.sha256
                 AND a.revision=r.revision
                WHERE r.job_id=? AND r.decision='approve'
                """ + artifact_filter + " ORDER BY r.created_at DESC LIMIT 1",
                parameters,
            ).fetchone()
            if row:
                return True
            automatic_filter = " AND ar.source_artifact=?" if artifact else ""
            automatic_parameters: tuple[Any, ...] = (job_id, artifact) if artifact else (job_id,)
            automatic = conn.execute(
                """
                SELECT 1
                FROM automatic_reviews AS ar
                JOIN artifacts AS a
                  ON a.job_id=ar.job_id
                 AND a.name=ar.source_artifact
                 AND a.sha256=ar.source_sha256
                 AND a.revision=ar.source_revision
                WHERE ar.job_id=? AND ar.status='approved'
                  AND ar.model='google/gemini-3.8-flash'
                """ + automatic_filter + " ORDER BY ar.created_at DESC LIMIT 1",
                automatic_parameters,
            ).fetchone()
            if automatic:
                return True
            if not artifact:
                return False
            current_artifact = conn.execute(
                "SELECT sha256 FROM artifacts WHERE job_id=? AND name=?",
                (job_id, artifact),
            ).fetchone()
            if not current_artifact:
                return False
            approved_reviews = conn.execute(
                """
                SELECT ar.id, ar.source_sha256
                FROM automatic_reviews AS ar
                JOIN artifacts AS source
                  ON source.job_id=ar.job_id
                 AND source.name=ar.source_artifact
                 AND source.sha256=ar.source_sha256
                 AND source.revision=ar.source_revision
                WHERE ar.job_id=? AND ar.status='approved'
                  AND ar.model='google/gemini-3.8-flash'
                ORDER BY ar.created_at DESC
                """,
                (job_id,),
            ).fetchall()
            extraction_path = self.job_dir(job_id) / "extract-frames.json"
            try:
                extraction = loads(extraction_path.read_text(encoding="utf-8"), {})
            except OSError:
                return False
            if extraction.get("automatic_selection") is not True:
                return False
            frames = extraction.get("frames")
            if not isinstance(frames, list):
                return False
            matching_frame = next(
                (
                    frame for frame in frames
                    if isinstance(frame, dict)
                    and frame.get("file") == artifact
                    and frame.get("sha256") == current_artifact["sha256"]
                ),
                None,
            )
            if matching_frame is None:
                return False
            return any(
                extraction.get("automatic_review_id") == review["id"]
                and extraction.get("source", {}).get("sha256") == review["source_sha256"]
                for review in approved_reviews
            )

    def recover_incomplete(self, reason: str = "service restart") -> int:
        msg = sanitize_message(f"incomplete stage marked needs_attention after {reason}")
        ts = now()
        with self.connect() as conn:
            rows = conn.execute("SELECT DISTINCT job_id FROM stage_jobs WHERE state='running'").fetchall()
            conn.execute("UPDATE stage_jobs SET state='needs_attention', error=?, finished_at=? WHERE state='running'", (msg, ts))
            for row in rows:
                conn.execute("UPDATE jobs SET state='needs_attention', message=?, updated_at=? WHERE id=?", (msg, ts, row["job_id"]))
            return len(rows)


class Conflict(Exception):
    pass


def sanitize_message(message: Any) -> str | None:
    if message is None:
        return None
    text = str(message)
    for key in ["ANIMATION_API_TOKEN", "WAVESPEED_API_KEY", "Authorization", "Bearer"]:
        text = text.replace(key, "[redacted]")
    return text[:500]
