"""Add application settings table and update system settings

Revision ID: 3a2b1c4d5e6f
Revises: f55f72e130c2
Create Date: 2025-06-05 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '3a2b1c4d5e6f'
down_revision = 'f55f72e130c2'
branch_labels = None
depends_on = None


def upgrade():
    # Add missing columns to existing system_settings table
    op.add_column('system_settings', sa.Column('is_encrypted', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('system_settings', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True))
    
    # Create application_settings table
    op.create_table('application_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('max_cost_per_hour', sa.DECIMAL(precision=10, scale=4), nullable=False),
        sa.Column('max_total_cost', sa.DECIMAL(precision=10, scale=4), nullable=False),
        sa.Column('max_upload_size_mb', sa.Integer(), nullable=False),
        sa.Column('max_hash_file_size_mb', sa.Integer(), nullable=False),
        sa.Column('data_retention_days', sa.Integer(), nullable=False),
        sa.Column('s3_bucket_name', sa.String(length=255), nullable=True),
        sa.Column('s3_region', sa.String(length=50), nullable=True),
        sa.Column('vast_cloud_connection_id', sa.String(length=255), nullable=True),
        sa.Column('aws_access_key_id_encrypted', sa.Text(), nullable=True),
        sa.Column('aws_secret_access_key_encrypted', sa.Text(), nullable=True),
        sa.Column('vast_api_key_encrypted', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Insert default settings row
    op.execute("""
        INSERT INTO application_settings (
            id, max_cost_per_hour, max_total_cost, max_upload_size_mb, 
            max_hash_file_size_mb, data_retention_days, s3_region
        ) VALUES (
            1, 2.0, 1000.0, 1000, 50, 30, 'us-east-1'
        )
    """)


def downgrade():
    op.drop_table('application_settings')
    op.drop_column('system_settings', 'created_at')
    op.drop_column('system_settings', 'is_encrypted')