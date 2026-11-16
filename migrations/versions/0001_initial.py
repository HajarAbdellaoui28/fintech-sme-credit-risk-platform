"""Initial assessment, portfolio and audit tables."""

from fintech_risk.database import Base

revision = "0001"
down_revision = None


def upgrade():
    from alembic import op

    Base.metadata.create_all(op.get_bind())


def downgrade():
    from alembic import op

    Base.metadata.drop_all(op.get_bind())
