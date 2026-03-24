import sys

from sqlalchemy import text

from app.database.connection.database import get_session


def check_database_connection() -> bool:
    db = get_session()

    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        db.close()


if __name__ == "__main__":
    is_ok = check_database_connection()
    if is_ok:
        print("Database connection successful")
        sys.exit(0)
    print("Database connection failed")
    sys.exit(1)
