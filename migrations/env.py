from alembic import context

from src.database.db import DATABASE_URL, engine
from src.database.models import Base


if DATABASE_URL.get_backend_name() != "postgresql":
    raise SystemExit("Set DATABASE_URL to the PostgreSQL database before running Alembic.")

if context.is_offline_mode():
    context.configure(url=DATABASE_URL, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
