from src.database.db import get_session, init_db
from src.database.models import Category


DEFAULT_CATEGORIES = [
    ("Health", "Fitness, nutrition, sleep, and recovery quests."),
    ("Work", "Professional tasks and focused work quests."),
    ("Learning", "Study, reading, and skill-building quests."),
    ("Home", "Chores, errands, and personal admin quests."),
    ("Social", "Relationships, family, and community quests."),
]


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
