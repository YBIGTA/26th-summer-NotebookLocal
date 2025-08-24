"""
DatabaseManager - Unified database connection and session management.

Provides consistent patterns for all database operations:
- ORM sessions for complex queries with models
- Raw connections for performance-critical operations
- Automatic transaction management and cleanup
"""

import logging
from contextlib import contextmanager
from typing import Generator, Any
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine, Connection

import config

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Centralized database connection and session management."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
            
        self.engine: Engine = create_engine(
            config.DATABASE_URL,
            echo=config.DATABASE_ECHO,
            pool_pre_ping=True,
            pool_recycle=300,
        )
        
        self.SessionLocal = sessionmaker(
            autocommit=False, 
            autoflush=False, 
            bind=self.engine
        )
        
        self._initialized = True
        logger.info("DatabaseManager initialized")
    
    @classmethod
    def get_instance(cls) -> 'DatabaseManager':
        """Get singleton instance."""
        return cls()
    
    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """
        Get ORM session with automatic transaction management.
        
        Use for:
        - Complex queries with models
        - Multi-table operations
        - When you need ORM features
        
        Example:
            with db_manager.session() as session:
                file = session.query(VaultFile).filter(...).first()
                session.add(new_file)
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    @contextmanager
    def connection(self) -> Generator[Connection, None, None]:
        """
        Get raw SQLAlchemy connection for direct SQL.
        
        Use for:
        - Simple, fast queries
        - Custom SQL operations
        - When ORM overhead isn't needed
        
        Example:
            with db_manager.connection() as conn:
                result = conn.execute(text("SELECT * FROM vault_files WHERE path = :path"), {"path": path})
        """
        conn = self.engine.connect()
        try:
            yield conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            conn.close()
    
    def execute_query(self, query: str, params: dict = None) -> Any:
        """
        Execute simple query without managing connections manually.
        
        Use for:
        - One-off queries
        - Simple SELECT statements
        - When you don't need context manager overhead
        
        Example:
            result = db_manager.execute_query(
                "SELECT COUNT(*) FROM vault_files WHERE status = :status", 
                {"status": "processed"}
            )
        """
        with self.connection() as conn:
            result = conn.execute(text(query), params or {})
            return result
    
    def test_connection(self) -> bool:
        """Test database connectivity."""
        try:
            with self.connection() as conn:
                result = conn.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def initialize_database(self) -> bool:
        """Initialize database with tables and indexes."""
        try:
            from .models import Base
            
            # Create all tables
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
            
            # Create additional indexes
            self._create_additional_indexes()
            
            return True
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            return False
    
    def _create_additional_indexes(self):
        """Create performance indexes."""
        try:
            with self.connection() as conn:
                # JSONB index for tags
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


# Global instance for easy access
db_manager = DatabaseManager.get_instance()