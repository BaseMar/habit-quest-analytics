from src.database.db import get_session, init_db
from src.database.models import Category
from src.constants import DEFAULT_CATEGORIES


def seed_default_categories() -> None:
    init_db()
    session = get_session()
    try:
        existing_names = {
            name for (name,) in session.query(Category.name).all()
        }
        for name, description in DEFAULT_CATEGORIES:
            if name not in existing_names:
                session.add(Category(name=name, description=description))
        session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    seed_default_categories()
    print("Seeded default categories.")
