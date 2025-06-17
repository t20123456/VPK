"""Add CANCELLING status to JobStatus enum

Revision ID: f55f72e130c2
Revises: 5a79a029a278
Create Date: 2025-06-04 13:17:18.962461+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f55f72e130c2'
down_revision = '28a075bb7af8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add CANCELLING to the jobstatus enum
    op.execute("ALTER TYPE jobstatus ADD VALUE IF NOT EXISTS 'CANCELLING'")


def downgrade() -> None:
    pass