from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.constants import DEFAULT_CATEGORIES
from src.database.models import Base, Category
from src.database.seed import ensure_default_categories


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    return TestingSession()


def test_ensure_default_categories_creates_missing_categories():
    session = _session()
    try:
        ensure_default_categories(session=session)

        names = {name for (name,) in session.query(Category.name).all()}

        assert names == {name for name, _ in DEFAULT_CATEGORIES}
    finally:
        session.close()


def test_ensure_default_categories_is_idempotent():
    session = _session()
    try:
        ensure_default_categories(session=session)
        ensure_default_categories(session=session)

        assert session.query(Category).count() == len(DEFAULT_CATEGORIES)
    finally:
        session.close()


def test_ensure_default_categories_preserves_existing_categories():
    session = _session()
    try:
        session.add(Category(name="Learning", description="Custom learning description"))
        session.commit()

        ensure_default_categories(session=session)

        learning = session.query(Category).filter_by(name="Learning").one()
        names = {name for (name,) in session.query(Category.name).all()}

        assert learning.description == "Custom learning description"
        assert names == {name for name, _ in DEFAULT_CATEGORIES}
    finally:
        session.close()
