"""SQLAlchemy models for document and chunk metadata."""

from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from .connection import Base


class Document(Base):
    """Document metadata model."""
    
    __tablename__ = "documents"
    
    doc_uid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    title = Column(String(255), nullable=False, index=True)
    author = Column(String(255), nullable=True)
    source_type = Column(String(50), nullable=False, index=True)  # 'pdf', 'web', 'slide'
    path = Column(Text, nullable=False)
    lang = Column(String(10), default='auto', index=True)
    tags = Column(JSONB, nullable=True)  # List of tags: ['course1', 'week2', 'topic3']
    page_count = Column(Integer, nullable=True)
    checksum = Column(String(64), unique=True, nullable=True, index=True)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship with chunks
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Document(doc_uid={self.doc_uid}, title='{self.title}', source_type='{self.source_type}')>"
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "doc_uid": str(self.doc_uid),
            "title": self.title,
            "author": self.author,
            "source_type": self.source_type,
            "path": self.path,
            "lang": self.lang,
            "tags": self.tags or [],
            "page_count": self.page_count,
            "checksum": self.checksum,
            "ingested_at": self.ingested_at.isoformat() if self.ingested_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "chunk_count": len(self.chunks) if self.chunks else 0
        }


class Chunk(Base):
    """Chunk metadata model."""
    
    __tablename__ = "chunks"
    
    chunk_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    doc_uid = Column(UUID(as_uuid=True), ForeignKey("documents.doc_uid", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    order_index = Column(Integer, nullable=False, index=True)
    page = Column(Integer, nullable=True, index=True)
    page_end = Column(Integer, nullable=True)
    offset_start = Column(Integer, nullable=True)
    offset_end = Column(Integer, nullable=True)
    tokens = Column(Integer, nullable=True)
    section = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship with document
    document = relationship("Document", back_populates="chunks")
    
    def __repr__(self):
        return f"<Chunk(chunk_id={self.chunk_id}, doc_uid={self.doc_uid}, order={self.order_index})>"
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "chunk_id": str(self.chunk_id),
            "doc_uid": str(self.doc_uid),
            "text": self.text,
            "order_index": self.order_index,
            "page": self.page,
            "page_end": self.page_end,
            "offset_start": self.offset_start,
            "offset_end": self.offset_end,
            "tokens": self.tokens,
            "section": self.section,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }