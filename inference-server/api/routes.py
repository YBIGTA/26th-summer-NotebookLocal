from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pathlib import Path
import tempfile
import os
import json
import asyncio
import uuid
import time
import logging
import traceback
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

logger = logging.getLogger(__name__)

from src.main import LectureProcessor
from src.llm.core.router import LLMRouter
from src.llm.models.requests import ChatRequest, Message

# Import route modules
from .vault_routes import router as vault_router
from .intelligence_routes import router as intelligence_router
from .document_routes import router as document_router


def extract_chunk_content(raw_chunk: str) -> str:
    """Extract clean text content from OpenAI streaming chunk format."""
    try:
        # Handle cases where raw_chunk is already clean text
        if not raw_chunk.startswith('data: '):
            return raw_chunk.strip()
        
        # Remove 'data: ' prefix
        json_str = raw_chunk[6:].strip()
        
        # Skip [DONE] messages
        if json_str == '[DONE]':
            return ""
            
        # Parse the JSON chunk
        chunk_data = json.loads(json_str)
        
        # Extract content from OpenAI format: choices[0].delta.content
        if 'choices' in chunk_data and len(chunk_data['choices']) > 0:
            delta = chunk_data['choices'][0].get('delta', {})
            content = delta.get('content', '')
            return content
        
        return ""
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.warning(f"Failed to parse streaming chunk: {raw_chunk[:100]}... Error: {e}")
        return ""
from src.llm.models.responses import ChatResponse, Choice, Usage

router = APIRouter()
processor = LectureProcessor()

# Initialize LLM Router
try:
    llm_router = LLMRouter()
except Exception as e:
    print(f"Warning: Failed to initialize LLM router: {e}")
    llm_router = None


# Original models for existing web interface
class QuestionRequest(BaseModel):
    question: str


class ProcessResponse(BaseModel):
    filename: str
    chunks: int
    images: int
    status: str


class QuestionResponse(BaseModel):
    question: str
    answer: str


# Extended models for Obsidian plugin integration
class ObsidianChatRequest(BaseModel):
    message: str
    chat_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    stream: bool = False


class ObsidianChatResponse(BaseModel):
    message: str
    chat_id: str
    timestamp: datetime
    sources: Optional[List[str]] = None


class DocumentMetadata(BaseModel):
    id: str
    filename: str
    content_preview: str
    chunks: int
    images: int
    processed_at: datetime
    file_size: int


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    similarity_threshold: float = 0.7


class SearchResult(BaseModel):
    content: str
    source: str
    score: float
    metadata: Dict[str, Any]


class IndexStatus(BaseModel):
    total_documents: int
    total_chunks: int
    last_updated: datetime
    is_empty: bool


@router.post("/process", response_model=ProcessResponse)
async def process_file(file: UploadFile = File(...)):
    """Process a PDF file and store it in the vector database."""
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    filename = file.filename
    
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDFs are supported.")

    try:
        # Read file contents
        contents = await file.read()
        
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
            tmp.write(contents)
            temp_path = tmp.name
        
        # Process the document
        result = await processor.process_document(temp_path)
        
        # Clean up temporary file
        os.unlink(temp_path)
        
        return ProcessResponse(
            filename=filename,
            chunks=result.get("chunks", 0),
            images=result["images"],
            status="success"
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        # Clean up temp file if it exists
        if 'temp_path' in locals():
            try:
                os.unlink(temp_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(exc)}") from exc


@router.post("/ask", response_model=QuestionResponse)
async def ask_question(request: QuestionRequest):
    """Ask a question about the processed documents."""
    try:
        answer = await processor.ask_question(request.question)
        return QuestionResponse(question=request.question, answer=answer)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to answer question: {str(exc)}") from exc


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    llm_status = "unknown"
    if llm_router:
        try:
            health_status = await llm_router.health_check()
            llm_status = "healthy" if health_status else "unhealthy"
        except Exception:
            llm_status = "error"
    
    return {
        "status": "healthy", 
        "service": "lecture-processor",
        "llm_router": llm_status
    }


# ========================================
# OpenAI-Compatible Endpoints
# ========================================

@router.post("/chat/completions", response_model=ChatResponse)
async def chat_completions(request: ChatRequest):
    """OpenAI-compatible chat completions endpoint."""
    if not llm_router:
        raise HTTPException(status_code=503, detail="LLM router not available")
    
    try:
        if request.stream:
            return StreamingResponse(
                llm_router.route(request), 
                media_type="text/plain"
            )
        else:
            result = await llm_router.route(request)
            return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat completion failed: {str(e)}")


@router.get("/models")
async def list_models():
    """List available models (OpenAI-compatible)."""
    if not llm_router:
        raise HTTPException(status_code=503, detail="LLM router not available")
    
    models = []
    for adapter_name, adapter in llm_router.adapters.items():
        models.append({
            "id": adapter.model_id or adapter.name,
            "object": "model",
            "owned_by": adapter_name,
            "created": int(time.time())
        })
    return {"data": models}


# ========================================
# Extended API for Obsidian Plugin Integration
# ========================================

# Legacy endpoints removed - now using intelligence system


@router.post("/obsidian/search", response_model=List[SearchResult])
async def obsidian_search(request: SearchRequest):
    """Semantic search endpoint for Obsidian plugin."""
    try:
        from src.storage.hybrid_store import HybridStore
        
        if isinstance(processor.store, HybridStore):
            # Use hybrid search with rich metadata
            results = processor.store.search(
                query=request.query,
                k=request.limit,
                alpha=0.7  # Favor semantic search
            )
            
            search_results = []
            for result in results:
                doc_info = result.get("document", {})
                search_results.append(SearchResult(
                    content=result["text"],
                    source=doc_info.get("title", "Unknown"),
                    score=result.get("score", 0.0),
                    metadata={
                        "doc_uid": result.get("doc_uid"),
                        "chunk_id": result.get("chunk_id"),
                        "page": result.get("page"),
                        "section": result.get("section"),
                        "tags": doc_info.get("tags", []),
                        "lang": doc_info.get("lang", "auto")
                    }
                ))
            
            return search_results
        else:
            # Fallback to basic vector search
            return []
            
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(exc)}") from exc


@router.get("/obsidian/documents", response_model=List[DocumentMetadata])
async def get_obsidian_documents():
    """Get list of processed documents for Obsidian plugin."""
    try:
        from src.storage.hybrid_store import HybridStore
        
        if isinstance(processor.store, HybridStore):
            # Get documents from PostgreSQL
            documents = processor.store.get_documents(limit=100)
            
            document_list = []
            for doc in documents:
                document_list.append(DocumentMetadata(
                    id=doc["doc_uid"],
                    filename=doc["title"],
                    content_preview=f"Document with {doc['chunk_count']} chunks",
                    chunks=doc["chunk_count"],
                    images=0,  # TODO: Add image tracking
                    processed_at=datetime.fromisoformat(doc["ingested_at"]) if doc["ingested_at"] else datetime.now(),
                    file_size=0  # TODO: Add file size tracking
                ))
            
            return document_list
        else:
            # Fallback for legacy vector store
            return []
            
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get documents: {str(exc)}") from exc


@router.delete("/obsidian/documents/{document_id}")
async def delete_obsidian_document(document_id: str):
    """Delete a document from the index."""
    try:
        from src.storage.hybrid_store import HybridStore
        
        if isinstance(processor.store, HybridStore):
            success = processor.store.delete_document(document_id)
            if success:
                return {"status": "deleted", "document_id": document_id}
            else:
                raise HTTPException(status_code=404, detail="Document not found")
        else:
            # Legacy vector store doesn't support deletion
            raise HTTPException(status_code=501, detail="Delete not supported in legacy mode")
            
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(exc)}") from exc


@router.get("/obsidian/index/status", response_model=IndexStatus)
async def get_obsidian_index_status():
    """Get current index status for Obsidian plugin."""
    try:
        from src.storage.hybrid_store import HybridStore
        
        if isinstance(processor.store, HybridStore):
            # Get actual statistics from PostgreSQL
            documents = processor.store.get_documents(limit=1000)  # Get more for counting
            total_documents = len(documents)
            total_chunks = sum(doc.get("chunk_count", 0) for doc in documents)
            
            # Find most recent document
            last_updated = datetime.now()
            if documents:
                latest_doc = max(documents, key=lambda d: d.get("ingested_at", ""))
                if latest_doc.get("ingested_at"):
                    last_updated = datetime.fromisoformat(latest_doc["ingested_at"])
            
            return IndexStatus(
                total_documents=total_documents,
                total_chunks=total_chunks,
                last_updated=last_updated,
                is_empty=total_documents == 0
            )
        else:
            # Legacy fallback
            return IndexStatus(
                total_documents=0,
                total_chunks=0,
                last_updated=datetime.now(),
                is_empty=True
            )
            
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get index status: {str(exc)}") from exc


@router.post("/obsidian/index/rebuild")
async def rebuild_obsidian_index():
    """Rebuild the entire index."""
    try:
        # TODO: Implement index rebuilding
        return {"status": "rebuilding", "message": "Index rebuild started"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to rebuild index: {str(exc)}") from exc


# Debug endpoints for monitoring and troubleshooting
@router.get("/debug/health-detailed")
async def debug_health_detailed():
    """Get detailed system health information"""
    logger.info("🔍 DEBUG: Detailed health check requested")
    
    try:
        from src.storage.hybrid_store import HybridStore
        
        health_info = {
            "timestamp": datetime.now().isoformat(),
            "system_status": "healthy",
            "components": {}
        }
        
        # Check database connection
        try:
            if isinstance(processor.store, HybridStore):
                documents = processor.store.get_documents(limit=1)
                health_info["components"]["postgresql"] = {
                    "status": "connected",
                    "can_query": True,
                    "sample_query_success": True
                }
            else:
                health_info["components"]["postgresql"] = {
                    "status": "not_used",
                    "message": "Using vector store only"
                }
        except Exception as e:
            health_info["components"]["postgresql"] = {
                "status": "error",
                "error": str(e)
            }
            health_info["system_status"] = "degraded"
        
        # Check vector store
        try:
            # This is a simple check - we'll add more specific Weaviate checks later
            health_info["components"]["vector_store"] = {
                "status": "available",
                "type": type(processor.store).__name__
            }
        except Exception as e:
            health_info["components"]["vector_store"] = {
                "status": "error",
                "error": str(e)
            }
            health_info["system_status"] = "degraded"
        
        # Check LLM router
        try:
            if llm_router:
                health_info["components"]["llm_router"] = {
                    "status": "available",
                    "adapters_count": len(llm_router._adapters) if hasattr(llm_router, '_adapters') else 0
                }
            else:
                health_info["components"]["llm_router"] = {
                    "status": "not_initialized",
                    "message": "LLM router failed to initialize"
                }
        except Exception as e:
            health_info["components"]["llm_router"] = {
                "status": "error", 
                "error": str(e)
            }
        
        logger.info(f"✅ DEBUG: Health check completed - Status: {health_info['system_status']}")
        return health_info
        
    except Exception as e:
        logger.error(f"❌ DEBUG: Health check failed: {str(e)}")
        return {
            "timestamp": datetime.now().isoformat(),
            "system_status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@router.get("/debug/db-stats")
async def debug_db_stats():
    """Get detailed database statistics"""
    logger.info("🔍 DEBUG: Database stats requested")
    
    try:
        from src.storage.hybrid_store import HybridStore
        
        if not isinstance(processor.store, HybridStore):
            return {"error": "Database stats only available for hybrid store"}
        
        # Get document statistics
        documents = processor.store.get_documents(limit=1000)
        
        stats = {
            "timestamp": datetime.now().isoformat(),
            "total_documents": len(documents),
            "total_chunks": 0,
            "documents_by_type": {},
            "recent_documents": [],
            "chunk_size_distribution": {"small": 0, "medium": 0, "large": 0}
        }
        
        for doc in documents:
            # Count chunks
            chunk_count = doc.get("chunk_count", 0)
            stats["total_chunks"] += chunk_count
            
            # Group by source type
            source_type = doc.get("source_type", "unknown")
            stats["documents_by_type"][source_type] = stats["documents_by_type"].get(source_type, 0) + 1
            
            # Classify document size
            if chunk_count < 5:
                stats["chunk_size_distribution"]["small"] += 1
            elif chunk_count < 20:
                stats["chunk_size_distribution"]["medium"] += 1
            else:
                stats["chunk_size_distribution"]["large"] += 1
        
        # Get 5 most recent documents
        if documents:
            sorted_docs = sorted(documents, key=lambda d: d.get("ingested_at", ""), reverse=True)
            stats["recent_documents"] = [
                {
                    "title": doc.get("title", "Untitled"),
                    "source_type": doc.get("source_type", "unknown"),
                    "chunks": doc.get("chunk_count", 0),
                    "ingested_at": doc.get("ingested_at", "unknown")
                }
                for doc in sorted_docs[:5]
            ]
        
        logger.info(f"✅ DEBUG: Database stats retrieved - {stats['total_documents']} documents, {stats['total_chunks']} chunks")
        return stats
        
    except Exception as e:
        logger.error(f"❌ DEBUG: Database stats failed: {str(e)}")
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }

# Include route modules in the main router
router.include_router(vault_router)
router.include_router(intelligence_router)
router.include_router(document_router)
