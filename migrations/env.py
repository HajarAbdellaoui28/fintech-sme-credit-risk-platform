from alembic import context

from fintech_risk.database import Base, engine

target_metadata = Base.metadata
with engine().connect() as connection:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()
