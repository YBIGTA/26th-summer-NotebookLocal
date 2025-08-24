"""
Intelligence API Routes - Single endpoint for natural language vault assistance.

Provides the main intelligence endpoint that:
1. Receives natural language messages
2. Detects intent and builds context
3. Routes to appropriate capability engine
4. Returns intelligent responses with sources and suggestions
"""

import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.intelligence.context_engine import ContextEngine
from src.intelligence.intent_detector import IntentDetector
from src.intelligence.capability_router import CapabilityRouter
from src.intelligence.engines import (
    UnderstandEngine, NavigateEngine, TransformEngine, 
    SynthesizeEngine, MaintainEngine
)
from src.storage.hybrid_store import HybridStore
from src.processors.embedder import Embedder
from src.llm.core.router import LLMRouter
from src.database.models import VaultFile
from src.database.connection import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/intelligence", tags=["intelligence"])

# Request/Response models
class IntelligenceRequest(BaseModel):
    message: str
    current_note_path: Optional[str] = None
    conversation_history: Optional[List[str]] = None
    session_id: Optional[str] = None
    max_tokens: Optional[int] = None
    mentioned_files: Optional[List[str]] = None
    mentioned_folders: Optional[List[str]] = None

class IntelligenceResponse(BaseModel):
    content: str
    sources: List[str]
    confidence: float
    intent_type: str
    sub_capability: str
    metadata: Dict[str, Any]
    suggested_actions: List[str]
    session_id: Optional[str]

class CapabilityInfoResponse(BaseModel):
    capabilities: Dict[str, Any]
    total_engines: int
    context_engine: Dict[str, Any]

# Dependency to get capability router
async def get_capability_router() -> CapabilityRouter:
    """Initialize and return capability router with all engines."""
    
    try:
        # Initialize components
        embedder = Embedder()
        
        # Get hybrid store (assuming it's already initialized)
        from src.storage.hybrid_store import HybridStore
        hybrid_store = HybridStore.get_instance()  # Assume singleton pattern
        
        # Get LLM router
        from src.llm.core.router import LLMRouter
        llm_router = LLMRouter.get_instance()  # Assume singleton pattern
        
        # Initialize context engine and intent detector
        context_engine = ContextEngine(hybrid_store, embedder)
        intent_detector = IntentDetector(llm_router)
        
        # Initialize all capability engines
        understand_engine = UnderstandEngine(llm_router)
        navigate_engine = NavigateEngine(llm_router, hybrid_store)
        transform_engine = TransformEngine(llm_router)
        synthesize_engine = SynthesizeEngine(llm_router)
        maintain_engine = MaintainEngine(llm_router)
        
        # Create capability router
        capability_router = CapabilityRouter(
            context_engine=context_engine,
            intent_detector=intent_detector,
            understand_engine=understand_engine,
            navigate_engine=navigate_engine,
            transform_engine=transform_engine,
            synthesize_engine=synthesize_engine,
            maintain_engine=maintain_engine
        )
        
        return capability_router
        
    except Exception as e:
        logger.error(f"Failed to initialize capability router: {e}")
        raise HTTPException(status_code=500, detail=f"Intelligence system initialization failed: {str(e)}")

@router.post("/chat", response_model=IntelligenceResponse)
async def intelligent_chat(
    request: IntelligenceRequest,
    router: CapabilityRouter = Depends(get_capability_router)
):
    """
    Main intelligence endpoint - processes natural language with full context awareness.
    
    This replaces the need for manual commands. Users can just talk naturally:
    - "What did I conclude about X?" → UNDERSTAND
    - "Find my notes about Y" → NAVIGATE  
    - "Make this clearer" → TRANSFORM
    - "What patterns do you see?" → SYNTHESIZE
    - "Check for issues" → MAINTAIN
    """
    
    try:
        logger.info(f"🧠 Intelligence request: '{request.message[:50]}...'")
        
        # Get vault files for context building
        vault_files = await _get_vault_files()
        
        # Process message with full intelligence
        response = await router.process_message(
            message=request.message,
            current_note_path=request.current_note_path,
            conversation_history=request.conversation_history or [],
            vault_files=vault_files,
            mentioned_files=request.mentioned_files or [],
            mentioned_folders=request.mentioned_folders or []
        )
        
        # Return structured response
        return IntelligenceResponse(
            content=response.content,
            sources=response.sources,
            confidence=response.confidence,
            intent_type=response.intent_type,
            sub_capability=response.sub_capability,
            metadata=response.metadata,
            suggested_actions=response.suggested_actions,
            session_id=request.session_id
        )
        
    except Exception as e:
        logger.error(f"Intelligence chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/capabilities", response_model=CapabilityInfoResponse)
async def get_capabilities(router: CapabilityRouter = Depends(get_capability_router)):
    """Get information about available intelligence capabilities."""
    
    try:
        info = router.get_capability_info()
        
        return CapabilityInfoResponse(
            capabilities=info['capabilities'],
            total_engines=info['total_engines'],
            context_engine=info['context_engine']
        )
        
    except Exception as e:
        logger.error(f"Error getting capabilities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/intent/detect")
async def detect_intent(
    request: IntelligenceRequest,
    router: CapabilityRouter = Depends(get_capability_router)
):
    """Detect intent from natural language message (useful for UI hints)."""
    
    try:
        detected_intent = await router.intent_detector.detect_intent(
            request.message,
            request.current_note_path,
            request.conversation_history
        )
        
        return {
            "intent_type": detected_intent.intent_type.value,
            "confidence": detected_intent.confidence,
            "sub_capability": detected_intent.sub_capability,
            "parameters": detected_intent.parameters,
            "reasoning": detected_intent.reasoning
        }
        
    except Exception as e:
        logger.error(f"Intent detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/context/build")
async def build_context(
    query: str,
    current_note_path: Optional[str] = None,
    max_tokens: Optional[int] = None,
    router: CapabilityRouter = Depends(get_capability_router)
):
    """Build context pyramid for a query (useful for debugging and preview)."""
    
    try:
        vault_files = await _get_vault_files()
        
        context_pyramid = await router.context_engine.build_context_pyramid(
            query=query,
            current_note_path=current_note_path,
            vault_files=vault_files,
            max_tokens=max_tokens
        )
        
        validation = router.context_engine.validate_context_pyramid(context_pyramid)
        sources = router.context_engine.get_context_sources(context_pyramid)
        
        return {
            "total_items": len(context_pyramid.items),
            "total_tokens": context_pyramid.total_tokens,
            "truncated": context_pyramid.truncated,
            "sources": sources,
            "validation": validation,
            "built_at": context_pyramid.built_at.isoformat(),
            "items": [
                {
                    "source_path": item.source_path,
                    "relevance_score": item.relevance_score,
                    "context_type": item.context_type,
                    "token_count": item.token_count,
                    "preview": item.content[:200] + "..." if len(item.content) > 200 else item.content
                }
                for item in context_pyramid.items
            ]
        }
        
    except Exception as e:
        logger.error(f"Context building error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper functions
async def _get_vault_files() -> List[VaultFile]:
    """Get all vault files from database."""
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT file_id, vault_path, file_type, content_hash, file_size, 
                       modified_at, processing_status, doc_uid, error_message,
                       created_at, updated_at
                FROM vault_files 
                ORDER BY modified_at DESC
            """)
            
            results = cursor.fetchall()
            
            # Convert to VaultFile objects
            vault_files = []
            for row in results:
                vault_file = VaultFile(
                    file_id=row[0],
                    vault_path=row[1],
                    file_type=row[2],
                    content_hash=row[3],
                    file_size=row[4],
                    modified_at=row[5],
                    processing_status=row[6],
                    doc_uid=row[7],
                    error_message=row[8],
                    created_at=row[9],
                    updated_at=row[10]
                )
                vault_files.append(vault_file)
            
            logger.info(f"📚 Retrieved {len(vault_files)} vault files")
            return vault_files
            
    except Exception as e:
        logger.error(f"Error getting vault files: {e}")
        return []