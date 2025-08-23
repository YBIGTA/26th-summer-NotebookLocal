"""
Add vault_files table for tracking Obsidian vault files

This migration adds:
- vault_files table with processing status tracking
- Indexes for efficient queries
- Foreign key relationship with documents table
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic
revision = '005'
down_revision = '004'  # Adjust based on your existing migrations
branch_labels = None
depends_on = None

def upgrade():
    # Create vault_files table
    op.create_table('vault_files',
        sa.Column('file_id', sa.UUID(), primary_key=True, server_default=text('gen_random_uuid()')),
        sa.Column('vault_path', sa.Text(), nullable=False, unique=True),
        sa.Column('file_type', sa.VARCHAR(10), nullable=True),
        sa.Column('content_hash', sa.VARCHAR(64), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('modified_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('processing_status', sa.VARCHAR(20), nullable=False, default='unprocessed'),
        sa.Column('doc_uid', sa.UUID(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=text('NOW()'))
    )

    # Add foreign key constraint
    op.create_foreign_key(
        'fk_vault_files_doc_uid',
        'vault_files',
        'documents',
        ['doc_uid'],
        ['doc_uid'],
        ondelete='SET NULL'
    )

    # Create indexes for efficient queries
    op.create_index('idx_vault_files_status', 'vault_files', ['processing_status'])
    op.create_index('idx_vault_files_path', 'vault_files', ['vault_path'])
    op.create_index('idx_vault_files_type', 'vault_files', ['file_type'])
    op.create_index('idx_vault_files_modified', 'vault_files', ['modified_at'])
    op.create_index('idx_vault_files_created', 'vault_files', ['created_at'])

    # Create trigger for updating updated_at timestamp
    op.execute(text("""
        CREATE OR REPLACE FUNCTION update_vault_files_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """))

    op.execute(text("""
        CREATE TRIGGER vault_files_updated_at_trigger
        BEFORE UPDATE ON vault_files
        FOR EACH ROW
        EXECUTE FUNCTION update_vault_files_updated_at();
    """))

    # Add constraint for processing_status values
    op.create_check_constraint(
        'ck_vault_files_processing_status',
        'vault_files',
        "processing_status IN ('unprocessed', 'queued', 'processing', 'processed', 'error')"
    )

def downgrade():
    # Drop trigger and function
    op.execute(text("DROP TRIGGER IF EXISTS vault_files_updated_at_trigger ON vault_files;"))
    op.execute(text("DROP FUNCTION IF EXISTS update_vault_files_updated_at();"))
    
    # Drop indexes
    op.drop_index('idx_vault_files_created', 'vault_files')
    op.drop_index('idx_vault_files_modified', 'vault_files')
    op.drop_index('idx_vault_files_type', 'vault_files')
    op.drop_index('idx_vault_files_path', 'vault_files')
    op.drop_index('idx_vault_files_status', 'vault_files')
    
    # Drop foreign key
    op.drop_constraint('fk_vault_files_doc_uid', 'vault_files', type_='foreignkey')
    
    # Drop constraint
    op.drop_constraint('ck_vault_files_processing_status', 'vault_files', type_='check')
    
    # Drop table
    op.drop_table('vault_files')