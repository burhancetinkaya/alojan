"""Transactional, checksum-checked SQL migrations; never log the DSN."""

import hashlib
import os
from pathlib import Path

import psycopg

MIGRATIONS = Path(__file__).resolve().parents[3] / "infra/migrations"


def migrate(dsn: str, directory: Path = MIGRATIONS) -> None:
    with psycopg.connect(dsn, connect_timeout=3) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(714203)")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, sha256 text NOT NULL)"
        )
        for path in sorted(directory.glob("*.sql")):
            sql = path.read_text()
            checksum = hashlib.sha256(sql.encode()).hexdigest()
            previous = conn.execute(
                "SELECT sha256 FROM schema_migrations WHERE name = %s", (path.name,)
            ).fetchone()
            if previous:
                if previous[0] != checksum:
                    raise ValueError(f"Applied migration changed: {path.name}")
                continue
            conn.execute(sql)
            conn.execute("INSERT INTO schema_migrations VALUES (%s, %s)", (path.name, checksum))


def main():
    dsn = os.environ.get("ALOJAN_DATABASE_URL")
    if not dsn:
        raise SystemExit("Set ALOJAN_DATABASE_URL before migration")
    try:
        migrate(dsn)
    except (psycopg.Error, ValueError):
        raise SystemExit(
            "Migration failed; verify database access and migration checksums"
        ) from None
    print("Migrations applied")


if __name__ == "__main__":
    main()
