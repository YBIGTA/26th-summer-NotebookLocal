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
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from src.main import LectureProcessor
from src.llm.core.router import LLMRouter
from src.llm.models.requests import ChatRequest, Message
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

def convert_obsidian_to_openai(obsidian_request: ObsidianChatRequest) -> ChatRequest:
    """Convert Obsidian chat request to OpenAI format."""
    messages = [
        Message(role="user", content=obsidian_request.message)
    ]
    
    return ChatRequest(
        messages=messages,
        stream=obsidian_request.stream,
        temperature=0.7,
        max_tokens=2048
    )


def add_rag_context(openai_request: ChatRequest, user_message: str) -> ChatRequest:
    """Add RAG context from vector search to OpenAI request."""
    try:
        # Use existing processor to get vector search results
        # We'll call the internal _retrieve method from qa_workflow
        from src.workflows.qa_workflow import QAWorkflow
        from src.storage.vector_store import get_vector_store
        from src.processors.embedder import Embedder
        
        embedder = Embedder()
        store = get_vector_store(embedder.embed)
        qa_workflow = QAWorkflow(store, embedder)
        
        # Get context using the existing workflow
        state = {"question": user_message}
        state = qa_workflow._retrieve(state)
        context = state.get("context", "")
        
        if context:
            # Add system message with context
            system_message = Message(
                role="system", 
                content=f"Korean PDF Context:\n{context}\n\nAnswer based on the provided context. If the question is in Korean, respond in Korean."
            )
            openai_request.messages.insert(0, system_message)
        
        return openai_request
    except Exception as e:
        print(f"Warning: Failed to add RAG context: {e}")
        return openai_request


def convert_openai_to_obsidian(openai_response: ChatResponse, chat_id: str) -> ObsidianChatResponse:
    """Convert OpenAI response to Obsidian format."""
    message_content = ""
    if openai_response.choices and len(openai_response.choices) > 0:
        message_content = openai_response.choices[0].message.content
    
    return ObsidianChatResponse(
        message=message_content,
        chat_id=chat_id,
        timestamp=datetime.now(),
        sources=[]  # TODO: Extract sources from context
    )

@router.post("/obsidian/chat", response_model=ObsidianChatResponse)
async def obsidian_chat(request: ObsidianChatRequest):
    """Chat endpoint for Obsidian plugin with context support."""
    if not llm_router:
        raise HTTPException(status_code=503, detail="LLM router not available")
    
    try:
        # Generate chat ID if not provided
        chat_id = request.chat_id or f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 1. Convert Obsidian format to OpenAI format
        openai_request = convert_obsidian_to_openai(request)
        
        # 2. Add RAG context from vector search
        openai_request = add_rag_context(openai_request, request.message)
        
        # 3. Route to appropriate model via LLMRouter
        openai_response = await llm_router.route(openai_request)
        
        # 4. Convert back to Obsidian format
        return convert_openai_to_obsidian(openai_response, chat_id)
        
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(exc)}") from exc


@router.post("/obsidian/chat/stream")
async def obsidian_chat_stream(request: ObsidianChatRequest):
    """Streaming chat endpoint for real-time responses."""
    if not llm_router:
        raise HTTPException(status_code=503, detail="LLM router not available")
    
    if not request.stream:
        # Fallback to regular chat
        response = await obsidian_chat(request)
        return response
    
    async def generate_stream():
        try:
            chat_id = request.chat_id or f"stream_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # 1. Convert Obsidian format to OpenAI format
            openai_request = convert_obsidian_to_openai(request)
            openai_request.stream = True  # Enable streaming
            
            # 2. Add RAG context from vector search
            openai_request = add_rag_context(openai_request, request.message)
            
            # 3. Stream from LLM router
            async for chunk in llm_router.route(openai_request):
                data = {
                    "content": chunk,
                    "chat_id": chat_id,
                    "done": False
                }
                yield f"data: {json.dumps(data)}\n\n"
            
            # Send completion signal
            final_data = {"content": "", "chat_id": chat_id, "done": True}
            yield f"data: {json.dumps(final_data)}\n\n"
                
        except Exception as e:
            error_data = {"error": str(e), "chat_id": request.chat_id or "error", "done": True}
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
