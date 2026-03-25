from pathlib import Path

from app.database.connection.database import get_session


BASE_DIR = Path(__file__).resolve().parent
MIGRATIONS_DIR = BASE_DIR / "migrations"

DROP_TABLES_SQL = """
DROP TABLE IF EXISTS doctor_ratings CASCADE;
DROP TABLE IF EXISTS notification_log CASCADE;
DROP TABLE IF EXISTS cancellation_log CASCADE;
DROP TABLE IF EXISTS waitlist CASCADE;
DROP TABLE IF EXISTS appointments CASCADE;
DROP TABLE IF EXISTS sessions CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS staff CASCADE;
DROP TABLE IF EXISTS doctors CASCADE;
DROP TABLE IF EXISTS patients CASCADE;
"""


def setup_database() -> None:
    db = get_session()

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

    try:
        raw_connection = db.connection().connection
        with raw_connection.cursor() as cursor:
            cursor.execute(DROP_TABLES_SQL)
            for migration_file in migration_files:
                print(f"Running migration: {migration_file.name}")
                cursor.execute(migration_file.read_text(encoding="utf-8"))
        db.commit()
        print("Database tables recreated successfully")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    setup_database()
