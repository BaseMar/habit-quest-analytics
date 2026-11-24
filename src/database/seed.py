from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.orm import Session

from src.database.db import get_engine
from src.database.models import Category
from src.constants import DEFAULT_CATEGORIES


def add_missing_default_categories(session, user_id: int | None = None) -> None:
    """Add an account's missing categories inside the caller's transaction."""
    existing_names = set(session.scalars(select(Category.name).where(Category.user_id == user_id)))
    missing = [
        {"name": name, "description": description, "user_id": user_id}
        for name, description in DEFAULT_CATEGORIES
        if name not in existing_names
    ]
    if not missing:
        return
    if session.get_bind().dialect.name == "postgresql":
        session.execute(postgresql_insert(Category).values(missing).on_conflict_do_nothing())
    else:
        session.add_all(Category(**values) for values in missing)


def ensure_default_categories(session=None) -> None:
    """Create defaults for a legacy dataset before it is assigned to an account."""
    owns_session = session is None
    session = session or Session(get_engine())
    try:
        add_missing_default_categories(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


if __name__ == "__main__":
    ensure_default_categories()
    print("Seeded default categories.")
