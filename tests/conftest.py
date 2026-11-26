import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from src.database import db


@pytest.fixture
def migration_config():
    return Config(Path(__file__).resolve().parents[1] / "alembic.ini")


@pytest.fixture
def postgres(monkeypatch, migration_config):
    configured_url = os.getenv("TEST_POSTGRESQL_URL")
    if not configured_url:
        pytest.skip("Set TEST_POSTGRESQL_URL to run PostgreSQL integration tests.")

    from alembic import command
    monkeypatch.setenv("DATABASE_URL", configured_url)
    url = db.get_database_url()
    if url.get_backend_name() != "postgresql":
        pytest.fail("TEST_POSTGRESQL_URL must point to a PostgreSQL database.")
    admin = create_engine(url)
    schema = f"hq_test_{uuid4().hex}"
    options = f"{url.query.get('options', '')} -csearch_path={schema} -cstatement_timeout=15000".strip()
    test_url = url.update_query_dict({"options": options})
    engine = create_engine(test_url)
    try:
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
        monkeypatch.setattr(db, "DATABASE_URL", test_url)
        monkeypatch.setattr(db, "engine", engine)
        command.upgrade(migration_config, "head")
        command.check(migration_config)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True, if_exists=True))
        admin.dispose()
