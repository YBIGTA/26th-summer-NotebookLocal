"""Hybrid storage coordinator for PostgreSQL + Weaviate."""

from typing import Dict, List, Any, Optional, Union, Tuple
import hashlib
import uuid
from pathlib import Path
import logging

from sqlalchemy.orm import Session
from ..database.connection import get_db
from ..database.models import Document, Chunk
from .vector_store import WeaviateVectorStore, SimpleVectorStore
from ..processors.embedder import Embedder

logger = logging.getLogger(__name__)


class HybridStore:
    """Coordinates between PostgreSQL (metadata) and Weaviate (vectors)."""
    
    def __init__(
        self,
        vector_store: Union[WeaviateVectorStore, SimpleVectorStore],
        embedder: Embedder
    ):
        self.vector_store = vector_store
        self.embedder = embedder
    
    def store_document(
        self,
        file_path: str,
        chunks: List[str],
        title: Optional[str] = None,
        author: Optional[str] = None,
        source_type: str = "pdf",
        lang: str = "auto",
        tags: Optional[List[str]] = None,
        page_count: Optional[int] = None
    ) -> Dict[str, Any]:
        """Store document and chunks in both PostgreSQL and Weaviate."""
        
        db = next(get_db())
        try:
            # Calculate file checksum
            checksum = self._calculate_checksum(file_path)
            
            # Check if document already exists
            existing_doc = db.query(Document).filter(Document.checksum == checksum).first()
            if existing_doc:
                logger.info(f"Document with checksum {checksum} already exists")
                return {
                    "doc_uid": str(existing_doc.doc_uid),
                    "status": "exists",
                    "chunks": len(existing_doc.chunks),
                    "images": 0
                }
            
            # Create document record
            doc_uid = uuid.uuid4()
            document = Document(
                doc_uid=doc_uid,
                title=title or Path(file_path).stem,
                author=author,
                source_type=source_type,
                path=file_path,
                lang=lang,
                tags=tags or [],
                page_count=page_count,
                checksum=checksum
            )
            db.add(document)
            db.flush()  # Get the ID without committing
            
            # Store chunks in PostgreSQL and Weaviate
            chunk_records = []
            weaviate_texts = []
            weaviate_metadatas = []
            
            for i, chunk_text in enumerate(chunks):
                chunk_id = uuid.uuid4()
                
                # Create chunk record for PostgreSQL
                chunk_record = Chunk(
                    chunk_id=chunk_id,
                    doc_uid=doc_uid,
                    text=chunk_text,
                    order_index=i,
                    tokens=len(chunk_text.split()) * 1.3  # Rough token estimate
                )
                chunk_records.append(chunk_record)
                db.add(chunk_record)
                
                # Prepare for Weaviate
                weaviate_texts.append(chunk_text)
                weaviate_metadatas.append({
                    "chunk_id": str(chunk_id),
                    "doc_uid": str(doc_uid),
                    "order_index": i
                })
            
            # Generate embeddings and store in Weaviate
            if chunks:
                embeddings = self.embedder.embed(weaviate_texts)
                
                if isinstance(self.vector_store, WeaviateVectorStore):
                    self.vector_store.add_texts(
                        texts=weaviate_texts,
                        embeddings=embeddings,
                        metadatas=weaviate_metadatas
                    )
                else:  # SimpleVectorStore
                    self.vector_store.add_texts(weaviate_texts, embeddings)
            
            # Commit all changes
            db.commit()
            
            return {
                "doc_uid": str(doc_uid),
                "status": "created",
                "chunks": len(chunks),
                "images": 0  # TODO: Handle images separately
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error storing document: {e}")
            raise
        finally:
            db.close()
    
    def search(
        self,
        query: str,
        k: int = 4,
        filters: Optional[Dict[str, Any]] = None,
        alpha: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Hybrid search: filter by metadata, then vector search."""
        
        db = next(get_db())
        try:
            # Step 1: Filter documents by metadata if filters provided
            eligible_doc_uids = None
            if filters:
                eligible_doc_uids = self._filter_documents(db, filters)
                if not eligible_doc_uids:
                    return []  # No documents match filters
            
            # Step 2: Vector search in Weaviate
            if isinstance(self.vector_store, WeaviateVectorStore):
                # Add doc_uid filter for Weaviate if we have filtered documents
                weaviate_filter = None
                if eligible_doc_uids:
                    weaviate_filter = {
                        "path": ["doc_uid"],
                        "operator": "ContainsAny",
                        "valueTextArray": [str(uid) for uid in eligible_doc_uids]
                    }
                
                vector_results = self.vector_store.similarity_search(
                    query=query,
                    k=k,
                    alpha=alpha
                )
            else:  # SimpleVectorStore
                query_embedding = self.embedder.embed([query])[0]
                vector_results = self.vector_store.similarity_search(query_embedding, k)
                # Convert format to match WeaviateVectorStore output
                vector_results = [{"text": text, "score": score} for text, score in vector_results]
            
            # Step 3: Enrich results with PostgreSQL metadata
            enriched_results = []
            for result in vector_results:
                # Find chunk by text (or chunk_id if available in metadata)
                chunk = db.query(Chunk).filter(Chunk.text == result["text"]).first()
                if chunk:
                    doc = chunk.document
                    enriched_result = {
                        **result,
                        "chunk_id": str(chunk.chunk_id),
                        "doc_uid": str(chunk.doc_uid),
                        "order_index": chunk.order_index,
                        "page": chunk.page,
                        "section": chunk.section,
                        "document": {
                            "title": doc.title,
                            "author": doc.author,
                            "source_type": doc.source_type,
                            "lang": doc.lang,
                            "tags": doc.tags or []
                        }
                    }
                    enriched_results.append(enriched_result)
            
            return enriched_results
            
        finally:
            db.close()
    
    def get_documents(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get documents with optional filtering."""
        
        db = next(get_db())
        try:
            query = db.query(Document)
            
            # Apply filters
            if filters:
                if "source_type" in filters:
                    query = query.filter(Document.source_type == filters["source_type"])
                if "lang" in filters:
                    query = query.filter(Document.lang == filters["lang"])
                if "tags" in filters:
                    # PostgreSQL JSONB contains operation
                    for tag in filters["tags"]:
                        query = query.filter(Document.tags.contains([tag]))
            
            documents = query.offset(offset).limit(limit).all()
            return [doc.to_dict() for doc in documents]
            
        finally:
            db.close()
    
    def delete_document(self, doc_uid: str) -> bool:
        """Delete document from both PostgreSQL and Weaviate."""
        
        db = next(get_db())
        try:
            # Find document
            document = db.query(Document).filter(Document.doc_uid == doc_uid).first()
            if not document:
                return False
            
            # TODO: Delete from Weaviate
            # This requires implementing delete functionality in vector_store
            
            # Delete from PostgreSQL (cascades to chunks)
            db.delete(document)
            db.commit()
            
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting document: {e}")
            return False
        finally:
            db.close()
    
    def _calculate_checksum(self, file_path: str) -> str:
        """Calculate MD5 checksum of file."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _filter_documents(
        self,
        db: Session,
        filters: Dict[str, Any]
    ) -> List[uuid.UUID]:
        """Filter documents by metadata and return eligible doc_uids."""
        
        query = db.query(Document.doc_uid)
        
        if "source_type" in filters:
            query = query.filter(Document.source_type == filters["source_type"])
        if "lang" in filters:
            query = query.filter(Document.lang == filters["lang"])
        if "tags" in filters:
            for tag in filters["tags"]:
                query = query.filter(Document.tags.contains([tag]))
        if "date_from" in filters:
            query = query.filter(Document.ingested_at >= filters["date_from"])
        if "date_to" in filters:
            query = query.filter(Document.ingested_at <= filters["date_to"])
        
        return [row.doc_uid for row in query.all()]