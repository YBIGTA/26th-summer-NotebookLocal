"""Database connection setup for PostgreSQL."""

from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging

import config

logger = logging.getLogger(__name__)

# Create SQLAlchemy engine
engine = create_engine(
    config.DATABASE_URL,
    echo=config.DATABASE_ECHO,
    pool_pre_ping=True,
    pool_recycle=300,
)

# Create SessionLocal class for database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def initialize_database():
    """Initialize database with tables and indexes."""
    try:
        # Create all tables defined in models
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        
        # Create additional indexes that aren't in the model
        _create_additional_indexes()
        
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False


def _create_additional_indexes():
    """Create additional indexes for performance."""
    try:
        with engine.connect() as conn:
            # JSONB index for tags (if it doesn't exist)
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_documents_tags 
                ON documents USING GIN(tags)
            """))
            
            # Composite indexes for common queries
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_documents_source_lang 
                ON documents(source_type, lang)
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_chunks_doc_order 
                ON chunks(doc_uid, order_index)
            """))
            
            conn.commit()
            logger.info("Additional indexes created successfully")
            
    except Exception as e:
        logger.warning(f"Some indexes may already exist: {e}")


def get_db_connection():
    """Get database connection for direct SQL queries."""
    return engine.connect()


def test_connection():
    """Test database connection."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


