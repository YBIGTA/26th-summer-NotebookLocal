"""Database initialization script."""

import logging
from .connection import initialize_database, test_connection
from .models import Document, Chunk  # Import models to register them

logger = logging.getLogger(__name__)


def init_database_on_startup():
    """Initialize database when the application starts."""
    logger.info("Starting database initialization...")
    
    # Test connection first
    if not test_connection():
        logger.error("❌ Cannot connect to PostgreSQL database")
        logger.error("Make sure PostgreSQL is running and DATABASE_URL is correct")
        return False
    
    logger.info("✅ PostgreSQL connection successful")
    
    # Initialize tables and indexes
    if initialize_database():
        logger.info("✅ Database initialization completed successfully")
        return True
    else:
        logger.error("❌ Database initialization failed")
        return False


def check_database_health():
    """Check if database is healthy and has expected tables."""
    try:
        from .connection import engine
        from sqlalchemy import text
        
        with engine.connect() as conn:
            # Check if tables exist
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('documents', 'chunks')
            """))
            
            tables = [row[0] for row in result]
            
            if 'documents' in tables and 'chunks' in tables:
                logger.info("✅ Database health check passed")
                return True
            else:
                logger.warning(f"⚠️ Missing tables. Found: {tables}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Database health check failed: {e}")
        return False


if __name__ == "__main__":
    # Script can be run directly for manual initialization
    logging.basicConfig(level=logging.INFO)
    init_database_on_startup()