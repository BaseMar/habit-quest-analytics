"""Assign pre-login data to a verified account after its first sign-in."""

import argparse

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from src.constants import DEFAULT_CATEGORIES
from src.database.db import get_engine
from src.database.models import Base, Category, PlayerProfile, UserAccount
from src.database.seed import add_missing_default_categories


def claim_legacy_data(email: str) -> int:
    engine = get_engine()
    tables = [table for table in Base.metadata.sorted_tables if "user_id" in table.c]
    prepare = engine.dialect.identifier_preparer
    names = ", ".join(prepare.format_table(table) for table in [UserAccount.__table__, *tables])
    with engine.begin() as connection:
        connection.exec_driver_sql("SET LOCAL lock_timeout = '10s'")
        connection.exec_driver_sql(f"LOCK TABLE {names} IN SHARE ROW EXCLUSIVE MODE")
        accounts = connection.scalars(select(UserAccount.id).where(UserAccount.email == email.strip().lower())).all()
        if len(accounts) != 1:
            raise ValueError("The email must belong to exactly one account that has signed in with Google.")
        user_id = accounts[0]
        legacy_counts = {
            table.name: connection.scalar(select(func.count()).select_from(table).where(table.c.user_id.is_(None)))
            for table in tables
        }
        if not any(legacy_counts.values()):
            return 0
        if legacy_counts[PlayerProfile.__tablename__] > 1:
            raise ValueError("There is more than one legacy profile. Resolve the duplicate profiles before claiming data.")
        for table in tables:
            if table.name in {Category.__tablename__, PlayerProfile.__tablename__}:
                continue
            if connection.scalar(select(table.c.id).where(table.c.user_id == user_id).limit(1)) is not None:
                raise ValueError("Claim the legacy data before adding items to the account.")

        categories = connection.execute(
            select(Category.name, Category.description).where(Category.user_id == user_id)
        ).all()
        if set(categories) - set(DEFAULT_CATEGORIES):
            raise ValueError("Claim the legacy data before changing the account's default categories.")
        profile = connection.execute(
            select(PlayerProfile.character_name, PlayerProfile.total_xp, PlayerProfile.avatar_path)
            .where(PlayerProfile.user_id == user_id)
        ).one_or_none()
        if profile is not None and tuple(profile) != ("Adventurer", 0, None):
            raise ValueError("Claim the legacy data before changing the account's profile.")

        connection.exec_driver_sql("SET CONSTRAINTS ALL DEFERRED")
        connection.execute(delete(Category).where(Category.user_id == user_id))
        if legacy_counts[PlayerProfile.__tablename__]:
            connection.execute(delete(PlayerProfile).where(PlayerProfile.user_id == user_id))
        for table in tables:
            connection.execute(update(table).where(table.c.user_id.is_(None)).values(user_id=user_id))
        with Session(bind=connection) as session:
            add_missing_default_categories(session, user_id)
        return sum(legacy_counts.values())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Verified Google email of the account that owns the legacy data.")
    args = parser.parse_args()
    try:
        count = claim_legacy_data(args.email)
    except ValueError as error:
        parser.exit(1, f"{error}\n")
    print(f"Assigned {count} legacy rows.")


if __name__ == "__main__":
    main()
