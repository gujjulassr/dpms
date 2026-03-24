import os
from urllib.parse import quote_plus

from dotenv import load_dotenv


load_dotenv()


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name, str(default))
    return int(value)


DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = _get_int("DB_PORT", 5432)
DB_NAME = os.getenv("DB_NAME", "dpam")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


def validate_database_settings() -> None:
    if not DB_HOST:
        raise ValueError("DB_HOST is required")
    if DB_PORT <= 0:
        raise ValueError("DB_PORT must be greater than 0")
    if not DB_NAME:
        raise ValueError("DB_NAME is required")
    if not DB_USER:
        raise ValueError("DB_USER is required")


def build_database_url() -> str:
    user = quote_plus(DB_USER)
    password = quote_plus(DB_PASSWORD)
    name = quote_plus(DB_NAME)
    return f"postgresql://{user}:{password}@{DB_HOST}:{DB_PORT}/{name}"


validate_database_settings()
DATABASE_URL = build_database_url()


__all__ = [
    "DATABASE_URL",
    "DB_HOST",
    "DB_NAME",
    "DB_PASSWORD",
    "DB_PORT",
    "DB_USER",
    "build_database_url",
    "validate_database_settings",
]
