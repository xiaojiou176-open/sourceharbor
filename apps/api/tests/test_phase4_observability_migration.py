from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
INIT_SQL = (ROOT / "infra/migrations/20260221_000001_init.sql").read_text(encoding="utf-8")
MIGRATION_SQL = (ROOT / "infra/migrations/20260221_000003_phase4_observability.sql").read_text(
    encoding="utf-8"
)
BASE_DB_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/postgres"
)


@pytest.fixture
def migration_db() -> Iterator[str | None]:
    parsed = make_url(BASE_DB_URL)
    if parsed.drivername != "postgresql+psycopg":
        yield None
        return

    database_name = f"phase4_obs_{uuid.uuid4().hex[:12]}"
    admin_database = parsed.database or "postgres"
    app_url = parsed.set(drivername="postgresql", database=database_name).render_as_string(
        hide_password=False
    )
    admin_url = parsed.set(drivername="postgresql", database=admin_database).render_as_string(
        hide_password=False
    )

    with psycopg.connect(admin_url, autocommit=True) as admin_conn, admin_conn.cursor() as cur:
        cur.execute(f'CREATE DATABASE "{database_name}"')

    try:
        yield app_url
    finally:
        with psycopg.connect(admin_url, autocommit=True) as admin_conn, admin_conn.cursor() as cur:
            cur.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s
                  AND pid <> pg_backend_pid()
                """,
                (database_name,),
            )
            cur.execute(f'DROP DATABASE IF EXISTS "{database_name}"')


def test_phase4_observability_migration_accepts_existing_degraded_pipeline_status(
    migration_db: str | None,
) -> None:
    if migration_db is None:
        return

    with psycopg.connect(migration_db) as conn, conn.cursor() as cur:
        cur.execute(INIT_SQL)
        cur.execute(
            """
            ALTER TABLE jobs
                ADD COLUMN pipeline_final_status VARCHAR(32);

            INSERT INTO videos (platform, video_uid, source_url)
            VALUES ('youtube', 'legacy-video', 'https://example.com/watch?v=legacy-video');

            INSERT INTO jobs (video_id, kind, status, idempotency_key, pipeline_final_status)
            SELECT id, 'phase2_ingest_stub', 'succeeded', 'legacy-job', 'degraded'
            FROM videos
            WHERE video_uid = 'legacy-video';
            """
        )

        cur.execute(MIGRATION_SQL)
        cur.execute(
            """
            SELECT pipeline_final_status
            FROM jobs
            WHERE idempotency_key = 'legacy-job'
            """
        )
        assert cur.fetchone() == ("degraded",)

        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                """
                INSERT INTO jobs (video_id, kind, status, idempotency_key, pipeline_final_status)
                SELECT id, 'phase2_ingest_stub', 'succeeded', 'invalid-job', 'partial'
                FROM videos
                WHERE video_uid = 'legacy-video';
                """
            )
