from src.database.db import get_session, init_db
from src.database.models import Category
from src.constants import DEFAULT_CATEGORIES


def ensure_default_categories(session=None) -> None:
    """Create missing default categories without duplicating existing records."""
    owns_session = session is None
    session = session or get_session()
    try:
        existing_names = {name for (name,) in session.query(Category.name).all()}
        for name, description in DEFAULT_CATEGORIES:
            if name not in existing_names:
                session.add(Category(name=name, description=description))
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def seed_default_categories() -> None:
    init_db()
    ensure_default_categories()


if __name__ == "__main__":
    seed_default_categories()
    print("Seeded default categories.")
