"""add_job_rules_table_for_multiple_rule_support

Revision ID: 7851d4d65ba5
Revises: b59de7268caa
Create Date: 2025-06-12 16:23:53.466957+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7851d4d65ba5'
down_revision = 'b59de7268caa'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create job_rules table for many-to-many relationship between jobs and rule files
    op.create_table('job_rules',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('job_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rule_file', sa.String(length=500), nullable=False),  # Rule file name/key (same as current rule_list format)
        sa.Column('rule_order', sa.Integer(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index for efficient job_id queries
    op.create_index('idx_job_rules_job_id', 'job_rules', ['job_id'])
    
    # Create unique constraint to prevent duplicate rule-job combinations with same order
    op.create_index('idx_job_rules_unique_order', 'job_rules', ['job_id', 'rule_order'], unique=True)


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('idx_job_rules_unique_order', table_name='job_rules')
    op.drop_index('idx_job_rules_job_id', table_name='job_rules')
    
    # Drop the table
    op.drop_table('job_rules')