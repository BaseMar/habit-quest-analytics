from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from src.database.db import get_engine
from src.database.models import PlayerProfile, UserAccount
from src.database.seed import add_missing_default_categories


def register_google_account(subject: str, verified_email: str) -> int:
    """Provision a Google account exactly once after Streamlit verifies the identity."""
    engine = get_engine()
    insert = postgresql_insert if engine.dialect.name == "postgresql" else sqlite_insert
    email = verified_email.strip().lower()
    with Session(engine) as session, session.begin():
        user_id = session.scalar(
            insert(UserAccount).values(google_subject=subject, email=email)
            .on_conflict_do_nothing(index_elements=[UserAccount.google_subject])
            .returning(UserAccount.id)
        )
        if user_id is None:
            account = session.scalars(select(UserAccount).where(UserAccount.google_subject == subject)).one()
            account.email = email
            return account.id
        add_missing_default_categories(session, user_id)
        session.add(PlayerProfile(user_id=user_id))
        return user_id
