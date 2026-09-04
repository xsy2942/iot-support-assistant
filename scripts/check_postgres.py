from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def main() -> None:
    db_url = os.getenv("TICKET_DB_URL")
    if not db_url:
        raise SystemExit("TICKET_DB_URL is empty. Fill it in .env to enable PostgreSQL.")

    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("psycopg is missing. Run: pip install -r requirements.txt") from exc

    with psycopg.connect(db_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user, version()")
            database, user, version = cursor.fetchone()
            cursor.execute("SELECT EXISTS (SELECT FROM pg_extension WHERE extname = 'vector')")
            vector_enabled = cursor.fetchone()[0]

    print(f"database={database}")
    print(f"user={user}")
    print(f"pgvector_enabled={vector_enabled}")
    print(version)


if __name__ == "__main__":
    main()
