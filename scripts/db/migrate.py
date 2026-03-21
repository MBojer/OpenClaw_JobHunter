"""
scripts/db/migrate.py
Run all pending migrations in order.
Safe to re-run — already-applied migrations are skipped.
"""
import os
import sys
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "db" / "migrations"
SCHEMA_FILE    = Path(__file__).parent.parent.parent / "db" / "schema.sql"


def run():
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    # Apply base schema (idempotent — uses IF NOT EXISTS throughout)
    print("Applying base schema...")
    cur.execute(SCHEMA_FILE.read_text())
    print("  ✓ schema.sql applied")

    # Apply numbered migrations in order
    migrations = sorted(MIGRATIONS_DIR.glob("*.sql"))
    for migration in migrations:
        version = migration.stem
        cur.execute(
            "SELECT 1 FROM schema_migrations WHERE version = %s", (version,)
        )
        if cur.fetchone():
            print(f"  - {version} already applied, skipping")
            continue
        print(f"  Applying {version}...")
        cur.execute(migration.read_text())
        cur.execute(
            "INSERT INTO schema_migrations (version) VALUES (%s)", (version,)
        )
        print(f"  ✓ {version} applied")

    cur.close()
    conn.close()
    print("\nMigrations complete.")


if __name__ == "__main__":
    run()
