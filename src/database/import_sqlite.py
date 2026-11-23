"""Copy a local SQLite database into a fresh PostgreSQL schema."""

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.engine import Connection, Engine, URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.database.db import get_engine
from src.database.models import Base
from src.services.quest_service import backfill_goal_session_numbers


def import_sqlite(source_path: Path, destination: Engine) -> dict[str, int]:
    """Copy all application rows and preserve their IDs in one transaction."""
    if destination.dialect.name != "postgresql":
        raise ValueError("Set DATABASE_URL to the destination PostgreSQL database.")
    source_path = source_path.resolve()
    if not source_path.is_file():
        raise ValueError(f"SQLite database file does not exist: {source_path}")

    with TemporaryDirectory() as temp_dir:
        snapshot_path = Path(temp_dir) / "habit_quest.db"
        with (
            closing(sqlite3.connect(f"{source_path.as_uri()}?mode=ro", uri=True)) as source,
            closing(sqlite3.connect(snapshot_path)) as snapshot,
        ):
            source.backup(snapshot)

        snapshot_engine = create_engine(URL.create("sqlite", database=str(snapshot_path)))
        try:
            if not inspect(snapshot_engine).has_table("quests"):
                raise ValueError("The source file has no quests table.")
            _prepare_sqlite_snapshot(snapshot_engine)
            with snapshot_engine.connect() as source, destination.begin() as target:
                return _copy_rows(source, target)
        finally:
            snapshot_engine.dispose()


def _prepare_sqlite_snapshot(bind: Engine) -> None:
    """Add fields missing from older backups before reading the snapshot."""
    Base.metadata.create_all(bind)
    legacy_columns = {
        "quests": {
            "estimated_minutes": "INTEGER",
            "planned_start_at": "DATETIME",
            "planned_end_at": "DATETIME",
            "goal_id": "INTEGER",
            "goal_session_number": "INTEGER",
        },
        "recurring_habits": {"planned_start_time": "TIME", "planned_end_time": "TIME"},
        "player_profiles": {"avatar_path": "VARCHAR(255)"},
    }
    with bind.begin() as connection:
        inspector = inspect(connection)
        for table, fields in legacy_columns.items():
            existing = {column["name"] for column in inspector.get_columns(table)}
            for field, sql_type in fields.items():
                if field not in existing:
                    connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {field} {sql_type}")

    with Session(bind, autoflush=False) as session:
        backfill_goal_session_numbers(session=session)


def _copy_rows(source: Connection, target: Connection) -> dict[str, int]:
    tables = Base.metadata.sorted_tables
    missing_tables = set(table.name for table in tables) - set(inspect(target).get_table_names())
    if missing_tables:
        raise ValueError("Run python -m alembic upgrade head before importing.")

    prepare = target.dialect.identifier_preparer
    table_names = ", ".join(prepare.format_table(table) for table in tables)
    # Serialize imports and keep application writes out until the ID generators are reset.
    target.exec_driver_sql(f"LOCK TABLE {table_names} IN ACCESS EXCLUSIVE MODE")
    for table in tables:
        if target.scalar(select(table.c.id).limit(1)) is not None:
            raise ValueError(f"The destination must be empty. The {table.name} table already contains data.")

    counts = {}
    for table in tables:
        counts[table.name] = 0
        for batch in source.execute(table.select()).mappings().partitions(500):
            target.execute(table.insert(), batch)
            counts[table.name] += len(batch)

        if counts[table.name]:
            max_id = target.scalar(select(func.max(table.c.id)))
            next_id = max(1, max_id + 1)
            target.exec_driver_sql(
                f"ALTER TABLE {prepare.format_table(table)} ALTER COLUMN id RESTART WITH {next_id}"
            )
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Path to the SQLite database file.")
    args = parser.parse_args()
    try:
        counts = import_sqlite(args.source, get_engine())
    except (OSError, sqlite3.Error, SQLAlchemyError, ValueError) as exc:
        parser.exit(1, f"Import failed: {exc}\n")

    print(f"Imported {sum(counts.values())} rows into PostgreSQL.")
    for table, count in counts.items():
        print(f"  {table}: {count}")


if __name__ == "__main__":
    main()
