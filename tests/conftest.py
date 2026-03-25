"""
tests/conftest.py

Shared pytest fixtures.

DB fixture strategy:
  - Each integration test gets its own DB connection.
  - The connection opens a real transaction before the test runs.
  - Services call db.commit() internally — we use SQLAlchemy's
    begin_nested() (SAVEPOINT) so those commits only flush to the
    savepoint, not to the actual DB.
  - After the test, the outer transaction is rolled back, leaving
    the DB completely clean.
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.database.config.settings import DATABASE_URL


@pytest.fixture(scope="session")
def engine():
    return create_engine(DATABASE_URL, future=True)


@pytest.fixture()
def db(engine):
    """
    Yields a SQLAlchemy Session whose changes are rolled back after
    each test — so every test starts with the same DB state.
    """
    connection = engine.connect()
    outer_tx = connection.begin()

    # Wrap every service-level commit in a SAVEPOINT instead
    session = Session(bind=connection)
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:
            session.begin_nested()

    yield session

    session.close()
    outer_tx.rollback()
    connection.close()
