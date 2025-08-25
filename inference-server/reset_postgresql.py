#!/usr/bin/env python3
"""
Database reset script - drops and recreates all tables with new schema.
Use this after making schema changes like JSON -> JSONB conversion.
"""

import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

from src.database.connection import engine, Base
from src.database.models import Document, Chunk, VaultFile  # Import to register models
from src.database.init_db import init_database_on_startup, test_connection
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def drop_all_tables():
    """Drop all existing tables."""
    try:
        logger.info("🗑️  Dropping all existing tables...")
        
        with engine.connect() as conn:
            # Drop tables in correct order (chunks first due to foreign key constraints)
            conn.execute(text("DROP TABLE IF EXISTS chunks CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS vault_files CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS documents CASCADE"))
            conn.commit()
            
        logger.info("✅ All tables dropped successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to drop tables: {e}")
        return False


def recreate_database():
    """Drop and recreate the entire database schema."""
    logger.info("🔄 Starting database recreation...")
    
    # Test connection first
    if not test_connection():
        logger.error("❌ Cannot connect to PostgreSQL")
        return False
    
    # Drop existing tables
    if not drop_all_tables():
        return False
    
    # Recreate tables with new schema
    logger.info("🏗️  Creating tables with new schema...")
    if init_database_on_startup():
        logger.info("✅ Database recreation completed successfully!")
        logger.info("🎉 New JSONB schema is now active")
        return True
    else:
        logger.error("❌ Failed to recreate database")
        return False


def show_current_schema():
    """Show current table schemas for verification."""
    try:
        logger.info("📋 Current database schema:")
        
        with engine.connect() as conn:
            # Check tables
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            
            tables = [row[0] for row in result]
            logger.info(f"Tables: {tables}")
            
            # Check documents table structure
            if 'documents' in tables:
                result = conn.execute(text("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'documents' 
                    AND table_schema = 'public'
                    ORDER BY ordinal_position
                """))
                
                logger.info("Documents table columns:")
                for row in result:
                    column_name, data_type = row
                    if column_name == 'tags':
                        logger.info(f"  📌 {column_name}: {data_type} {'✅ JSONB' if 'jsonb' in data_type.lower() else '⚠️ ' + data_type}")
                    else:
                        logger.info(f"     {column_name}: {data_type}")
            
            # Check vault_files table structure
            if 'vault_files' in tables:
                result = conn.execute(text("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'vault_files' 
                    AND table_schema = 'public'
                    ORDER BY ordinal_position
                """))
                
                logger.info("Vault files table columns:")
                for row in result:
                    column_name, data_type = row
                    if column_name in ['processing_started_at', 'processing_completed_at']:
                        logger.info(f"  📌 {column_name}: {data_type}")
                    else:
                        logger.info(f"     {column_name}: {data_type}")
            
            # Check indexes
            result = conn.execute(text("""
                SELECT indexname, indexdef 
                FROM pg_indexes 
                WHERE tablename IN ('documents', 'chunks', 'vault_files')
                ORDER BY tablename, indexname
            """))
            
            logger.info("Indexes:")
            for row in result:
                index_name, index_def = row
                if 'gin' in index_def.lower():
                    logger.info(f"  📌 {index_name}: {index_def}")
                else:
                    logger.info(f"     {index_name}")
                    
    except Exception as e:
        logger.error(f"❌ Failed to show schema: {e}")


if __name__ == "__main__":
    print("🔄 Database Reset Tool")
    print("=" * 50)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--show-schema":
        show_current_schema()
        sys.exit(0)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage:")
        print("  python reset_database.py           # Reset database")
        print("  python reset_database.py --show-schema  # Show current schema")
        print("  python reset_database.py --help         # Show this help")
        sys.exit(0)
    
    print("⚠️  This will DROP ALL DATA and recreate the database!")
    print("This is needed to apply the JSON -> JSONB schema change.")
    print()
    
    response = input("Are you sure you want to continue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("❌ Operation cancelled")
        sys.exit(1)
    
    print()
    if recreate_database():
        print()
        print("🎉 Database reset completed successfully!")
        print("You can now restart your application.")
        show_current_schema()
    else:
        print("❌ Database reset failed!")
        sys.exit(1)