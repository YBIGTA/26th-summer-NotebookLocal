from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pathlib import Path
import tempfile
import os
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.main import LectureProcessor

router = APIRouter()
processor = LectureProcessor()


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
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
            tmp.write(contents)
            temp_path = tmp.name
            
        # Process the document
        result = processor.process_document(temp_path)
        
        # Clean up temporary file
        os.unlink(temp_path)
        
        return ProcessResponse(
            filename=filename,
            chunks=result["chunks"],
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
        answer = processor.ask_question(request.question)
        return QuestionResponse(question=request.question, answer=answer)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to answer question: {str(exc)}") from exc


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "lecture-processor"}


# ========================================
# Extended API for Obsidian Plugin Integration
# ========================================

@router.post("/obsidian/chat", response_model=ObsidianChatResponse)
async def obsidian_chat(request: ObsidianChatRequest):
    """Chat endpoint for Obsidian plugin with context support."""
    try:
        # Generate chat ID if not provided
        chat_id = request.chat_id or f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Use existing Q&A functionality
        answer = processor.ask_question(request.message)
        
        return ObsidianChatResponse(
            message=answer,
            chat_id=chat_id,
            timestamp=datetime.now(),
            sources=[]  # TODO: Extract sources from processor
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(exc)}") from exc


@router.post("/obsidian/chat/stream")
async def obsidian_chat_stream(request: ObsidianChatRequest):
    """Streaming chat endpoint for real-time responses."""
    if not request.stream:
        # Fallback to regular chat
        response = await obsidian_chat(request)
        return response
    
    async def generate_stream():
        try:
            # For now, simulate streaming by chunking the response
            # TODO: Implement actual streaming from LLM
            answer = processor.ask_question(request.message)
            
            # Split response into chunks for streaming
            words = answer.split()
            for i in range(0, len(words), 5):  # 5 words at a time
                chunk = " ".join(words[i:i+5])
                data = {
                    "delta": chunk + " ",
                    "chat_id": request.chat_id or "stream_chat",
                    "done": i + 5 >= len(words)
                }
                yield f"data: {json.dumps(data)}\n\n"
                await asyncio.sleep(0.1)  # Simulate streaming delay
                
        except Exception as e:
            error_data = {"error": str(e), "done": True}
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(generate_stream(), media_type="text/plain")


@router.post("/obsidian/search", response_model=List[SearchResult])
async def obsidian_search(request: SearchRequest):
    """Semantic search endpoint for Obsidian plugin."""
    try:
        # TODO: Implement proper search using your vector store
        # For now, return empty results
        return []
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(exc)}") from exc


@router.get("/obsidian/documents", response_model=List[DocumentMetadata])
async def get_obsidian_documents():
    """Get list of processed documents for Obsidian plugin."""
    try:
        # TODO: Implement document listing from vector store
        return []
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get documents: {str(exc)}") from exc


@router.delete("/obsidian/documents/{document_id}")
async def delete_obsidian_document(document_id: str):
    """Delete a document from the index."""
    try:
        # TODO: Implement document deletion from vector store
        return {"status": "deleted", "document_id": document_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(exc)}") from exc


@router.get("/obsidian/index/status", response_model=IndexStatus)
async def get_obsidian_index_status():
    """Get current index status for Obsidian plugin."""
    try:
        # TODO: Implement actual index status check
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
