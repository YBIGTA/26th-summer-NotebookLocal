"""Hybrid storage coordinator for PostgreSQL + Weaviate."""

from typing import Dict, List, Any, Optional, Union, Tuple
import hashlib
import uuid
import logging
import time
from pathlib import Path

from sqlalchemy.orm import Session
from ..database.connection import get_db
from ..database.models import Document, Chunk
from .vector_store import WeaviateVectorStore, SimpleVectorStore
from ..processors.embedder import Embedder
from ..processors.text_processor import ChunkData

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
        
        logger.info(f"Starting document storage: {Path(file_path).name}")
        logger.info(f"  Chunks to store: {len(chunks)}")
        logger.info(f"  Source type: {source_type}")
        logger.info(f"  Language: {lang}")
        
        db = next(get_db())
        try:
            # Calculate file checksum
            logger.info("Calculating file checksum...")
            checksum = self._calculate_checksum(file_path)
            logger.info(f"File checksum: {checksum}")
            
            # Check if document already exists
            logger.info("Checking for existing document in database...")
            existing_doc = db.query(Document).filter(Document.checksum == checksum).first()
            if existing_doc:
                logger.info(f"Document already exists:")
                logger.info(f"  Document ID: {existing_doc.doc_uid}")
                logger.info(f"  Existing chunks: {len(existing_doc.chunks)}")
                return {
                    "doc_uid": str(existing_doc.doc_uid),
                    "status": "exists",
                    "chunks": len(existing_doc.chunks),
                    "images": 0
                }
            
            # Create document record
            doc_uid = uuid.uuid4()
            logger.info(f"Creating new document:")
            logger.info(f"  Document ID: {doc_uid}")
            logger.info(f"  Title: {title or Path(file_path).stem}")
            logger.info(f"  Author: {author}")
            
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
            logger.info("Document record created in PostgreSQL")
            
            # Store chunks in PostgreSQL and Weaviate
            logger.info(f"Processing {len(chunks)} chunks for storage...")
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
            
            logger.info(f"All {len(chunks)} chunks prepared for PostgreSQL")
            
            # Generate embeddings and store in Weaviate
            if chunks:
                logger.info("Generating embeddings for chunks...")
                start_time = time.time()
                embeddings = self.embedder.embed(weaviate_texts)
                embed_time = time.time() - start_time
                logger.info(f"Embeddings generated in {embed_time:.2f}s")
                logger.info(f"  Number of embeddings: {len(embeddings)}")
                logger.info(f"  Embedding dimension: {len(embeddings[0]) if embeddings else 0}")
                
                logger.info("Storing embeddings in vector database...")
                vector_start = time.time()
                if isinstance(self.vector_store, WeaviateVectorStore):
                    self.vector_store.add_texts(
                        texts=weaviate_texts,
                        embeddings=embeddings,
                        metadatas=weaviate_metadatas
                    )
                    logger.info("Embeddings stored in Weaviate")
                else:  # SimpleVectorStore
                    self.vector_store.add_texts(weaviate_texts, embeddings)
                    logger.info("Embeddings stored in SimpleVectorStore")
                
                vector_time = time.time() - vector_start
                logger.info(f"Vector storage completed in {vector_time:.2f}s")
            
            # Commit all changes
            logger.info("Committing database transaction...")
            commit_start = time.time()
            db.commit()
            commit_time = time.time() - commit_start
            logger.info(f"Database transaction committed in {commit_time:.2f}s")
            
            logger.info("Document storage completed successfully:")
            logger.info(f"  Document ID: {doc_uid}")
            logger.info(f"  Chunks stored: {len(chunks)}")
            logger.info(f"  Status: created")
            
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
    
    def store_document_with_pages(
        self,
        file_path: str,
        chunks: List[ChunkData],
        descriptions: List[str] = None,
        title: Optional[str] = None,
        author: Optional[str] = None,
        source_type: str = "pdf",
        lang: str = "auto",
        tags: Optional[List[str]] = None,
        page_count: Optional[int] = None
    ) -> Dict[str, Any]:
        """Store document and chunks with page information in both PostgreSQL and Weaviate."""
        
        logger.info(f"Starting page-aware document storage: {Path(file_path).name}")
        logger.info(f"  Text chunks to store: {len(chunks)}")
        logger.info(f"  Image descriptions to store: {len(descriptions or [])}")
        logger.info(f"  Source type: {source_type}")
        logger.info(f"  Language: {lang}")
        
        db = next(get_db())
        try:
            # Calculate file checksum
            logger.info("Calculating file checksum...")
            checksum = self._calculate_checksum(file_path)
            logger.info(f"File checksum: {checksum}")
            
            # Check if document already exists
            logger.info("Checking for existing document in database...")
            existing_doc = db.query(Document).filter(Document.checksum == checksum).first()
            if existing_doc:
                logger.info(f"Document already exists:")
                logger.info(f"  Document ID: {existing_doc.doc_uid}")
                logger.info(f"  Existing chunks: {len(existing_doc.chunks)}")
                return {
                    "doc_uid": str(existing_doc.doc_uid),
                    "status": "exists",
                    "chunks": len(existing_doc.chunks),
                    "images": len(descriptions or [])
                }
            
            # Create document record
            doc_uid = uuid.uuid4()
            logger.info(f"Creating new document:")
            logger.info(f"  Document ID: {doc_uid}")
            logger.info(f"  Title: {title or Path(file_path).stem}")
            logger.info(f"  Author: {author}")
            logger.info(f"  Page count: {page_count}")
            
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
            logger.info("Document record created in PostgreSQL")
            
            # Store text chunks with page information
            logger.info(f"Processing {len(chunks)} text chunks for storage...")
            chunk_records = []
            weaviate_texts = []
            weaviate_metadatas = []
            
            for i, chunk_data in enumerate(chunks):
                chunk_id = uuid.uuid4()
                
                # Create chunk record for PostgreSQL with page info
                chunk_record = Chunk(
                    chunk_id=chunk_id,
                    doc_uid=doc_uid,
                    text=chunk_data.text,
                    order_index=i,
                    page=chunk_data.page_number,  # Store the page number
                    tokens=len(chunk_data.text.split()) * 1.3  # Rough token estimate
                )
                chunk_records.append(chunk_record)
                db.add(chunk_record)
                
                # Prepare for Weaviate
                weaviate_texts.append(chunk_data.text)
                weaviate_metadatas.append({
                    "chunk_id": str(chunk_id),
                    "doc_uid": str(doc_uid),
                    "order_index": i,
                    "page_number": chunk_data.page_number,
                    "chunk_index": chunk_data.chunk_index
                })
                
                logger.info(f"  Chunk {i+1}: Page {chunk_data.page_number}, Chunk {chunk_data.chunk_index}, {len(chunk_data.text)} chars")
            
            # Store image descriptions as additional chunks
            if descriptions:
                logger.info(f"Processing {len(descriptions)} image descriptions...")
                for i, description in enumerate(descriptions):
                    chunk_id = uuid.uuid4()
                    order_index = len(chunks) + i
                    
                    # Create chunk record for image description
                    chunk_record = Chunk(
                        chunk_id=chunk_id,
                        doc_uid=doc_uid,
                        text=description,
                        order_index=order_index,
                        page=None,  # Image descriptions don't have specific pages yet
                        section="image_description",
                        tokens=len(description.split()) * 1.3
                    )
                    chunk_records.append(chunk_record)
                    db.add(chunk_record)
                    
                    # Prepare for Weaviate
                    weaviate_texts.append(description)
                    weaviate_metadatas.append({
                        "chunk_id": str(chunk_id),
                        "doc_uid": str(doc_uid),
                        "order_index": order_index,
                        "type": "image_description"
                    })
                    
                    logger.info(f"  Image description {i+1}: {len(description)} chars")
            
            total_items = len(chunks) + len(descriptions or [])
            logger.info(f"All {total_items} items prepared for PostgreSQL")
            
            # Generate embeddings and store in Weaviate
            if weaviate_texts:
                logger.info("Generating embeddings for all content...")
                start_time = time.time()
                embeddings = self.embedder.embed(weaviate_texts)
                embed_time = time.time() - start_time
                logger.info(f"Embeddings generated in {embed_time:.2f}s")
                logger.info(f"  Number of embeddings: {len(embeddings)}")
                logger.info(f"  Embedding dimension: {len(embeddings[0]) if embeddings else 0}")
                
                logger.info("Storing embeddings in vector database...")
                vector_start = time.time()
                if isinstance(self.vector_store, WeaviateVectorStore):
                    self.vector_store.add_texts(
                        texts=weaviate_texts,
                        embeddings=embeddings,
                        metadatas=weaviate_metadatas
                    )
                    logger.info("Embeddings stored in Weaviate")
                else:  # SimpleVectorStore
                    self.vector_store.add_texts(weaviate_texts, embeddings)
                    logger.info("Embeddings stored in SimpleVectorStore")
                
                vector_time = time.time() - vector_start
                logger.info(f"Vector storage completed in {vector_time:.2f}s")
            
            # Commit all changes
            logger.info("Committing database transaction...")
            commit_start = time.time()
            db.commit()
            commit_time = time.time() - commit_start
            logger.info(f"Database transaction committed in {commit_time:.2f}s")
            
            logger.info("Page-aware document storage completed successfully:")
            logger.info(f"  Document ID: {doc_uid}")
            logger.info(f"  Text chunks stored: {len(chunks)}")
            logger.info(f"  Image descriptions stored: {len(descriptions or [])}")
            logger.info(f"  Total items: {total_items}")
            logger.info(f"  Status: created")
            
            return {
                "doc_uid": str(doc_uid),
                "status": "created",
                "chunks": len(chunks),
                "images": len(descriptions or []),
                "total_items": total_items
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error storing page-aware document: {e}")
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