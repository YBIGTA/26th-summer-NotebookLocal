"""Add enhanced processing tracking fields to vault_files table

Revision ID: 006
Revises: 005
Create Date: 2025-01-24 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    """Add enhanced processing tracking fields to vault_files table."""
    
    # Add new columns for enhanced processing tracking
    op.add_column('vault_files', sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('vault_files', sa.Column('processing_completed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('vault_files', sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('vault_files', sa.Column('last_error', sa.Text(), nullable=True))
    op.add_column('vault_files', sa.Column('processing_progress', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('vault_files', sa.Column('chunks_created', sa.Integer(), nullable=True))
    op.add_column('vault_files', sa.Column('images_processed', sa.Integer(), nullable=True))
    op.add_column('vault_files', sa.Column('processing_time_seconds', sa.Integer(), nullable=True))
    
    # Add indexes for commonly queried fields
    op.create_index('ix_vault_files_processing_started_at', 'vault_files', ['processing_started_at'])
    op.create_index('ix_vault_files_processing_completed_at', 'vault_files', ['processing_completed_at'])
    op.create_index('ix_vault_files_retry_count', 'vault_files', ['retry_count'])


def downgrade():
    """Remove enhanced processing tracking fields from vault_files table."""
    
    # Drop indexes
    op.drop_index('ix_vault_files_retry_count', table_name='vault_files')
    op.drop_index('ix_vault_files_processing_completed_at', table_name='vault_files')
    op.drop_index('ix_vault_files_processing_started_at', table_name='vault_files')
    
    # Drop columns
    op.drop_column('vault_files', 'processing_time_seconds')
    op.drop_column('vault_files', 'images_processed')
    op.drop_column('vault_files', 'chunks_created')
    op.drop_column('vault_files', 'processing_progress')
    op.drop_column('vault_files', 'last_error')
    op.drop_column('vault_files', 'retry_count')
    op.drop_column('vault_files', 'processing_completed_at')
    op.drop_column('vault_files', 'processing_started_at')