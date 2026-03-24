from pathlib import Path

from app.database.connection.database import get_session


BASE_DIR = Path(__file__).resolve().parent
MIGRATION_FILE = BASE_DIR / "migrations" / "001_initial_schema.sql"

DROP_TABLES_SQL = """
DROP TABLE IF EXISTS notification_log CASCADE;
DROP TABLE IF EXISTS cancellation_log CASCADE;
DROP TABLE IF EXISTS waitlist CASCADE;
DROP TABLE IF EXISTS appointments CASCADE;
DROP TABLE IF EXISTS slots CASCADE;
DROP TABLE IF EXISTS sessions CASCADE;
DROP TABLE IF EXISTS staff CASCADE;
DROP TABLE IF EXISTS doctors CASCADE;
DROP TABLE IF EXISTS patients CASCADE;
"""


def setup_database() -> None:
    db = get_session()

    try:
        raw_connection = db.connection().connection
        with raw_connection.cursor() as cursor:
            cursor.execute(DROP_TABLES_SQL)
            cursor.execute(MIGRATION_FILE.read_text(encoding="utf-8"))
        db.commit()
        print("Database tables recreated successfully")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    setup_database()
