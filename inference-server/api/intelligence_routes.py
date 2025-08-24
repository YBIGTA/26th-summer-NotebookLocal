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

from src.intelligence.intelligence_service import IntelligenceService, intelligence_service
from src.database.file_manager import FileManager, file_manager

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

# Global intelligence service instance
_intelligence_service = None

# Dependency to get intelligence service
async def get_intelligence_service() -> IntelligenceService:
    """Initialize and return intelligence service with clean dependencies."""
    
    global _intelligence_service
    
    if _intelligence_service is not None:
        return _intelligence_service
    
    try:
        # Get configured components from main processor
        from api.routes import processor
        
        # Initialize intelligence service with existing components
        _intelligence_service = IntelligenceService(
            file_manager=file_manager,
            hybrid_store=processor.store,
            embedder=processor.embedder,
            llm_router=None  # Will use default singleton
        )
        
        logger.info("✅ IntelligenceService initialized with clean dependencies")
        return _intelligence_service
        
    except Exception as e:
        logger.error(f"Failed to initialize intelligence service: {e}")
        raise HTTPException(status_code=500, detail=f"Intelligence system initialization failed: {str(e)}")

@router.post("/chat", response_model=IntelligenceResponse)
async def intelligent_chat(
    request: IntelligenceRequest,
    service: IntelligenceService = Depends(get_intelligence_service)
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
        
        # Process message using clean intelligence service
        response_dict = await service.process_intelligent_message(
            message=request.message,
            current_note_path=request.current_note_path,
            conversation_history=request.conversation_history,
            session_id=request.session_id,
            max_tokens=request.max_tokens,
            mentioned_files=request.mentioned_files,
            mentioned_folders=request.mentioned_folders
        )
        
        # Return structured response
        return IntelligenceResponse(
            content=response_dict['content'],
            sources=response_dict['sources'],
            confidence=response_dict['confidence'],
            intent_type=response_dict['intent_type'],
            sub_capability=response_dict['sub_capability'],
            metadata=response_dict['metadata'],
            suggested_actions=response_dict['suggested_actions'],
            session_id=response_dict['session_id']
        )
        
    except Exception as e:
        logger.error(f"Intelligence chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/capabilities", response_model=CapabilityInfoResponse)
async def get_capabilities(service: IntelligenceService = Depends(get_intelligence_service)):
    """Get information about available intelligence capabilities."""
    
    try:
        capabilities = service.get_capabilities()
        
        return CapabilityInfoResponse(
            capabilities=capabilities['engines'],
            total_engines=len(capabilities['engines']),
            context_engine=capabilities['features']
        )
        
    except Exception as e:
        logger.error(f"Error getting capabilities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/intent/detect")
async def detect_intent(
    request: IntelligenceRequest,
    service: IntelligenceService = Depends(get_intelligence_service)
):
    """Detect intent from natural language message (useful for UI hints)."""
    
    try:
        intent_result = await service.detect_intent(
            message=request.message,
            current_note_path=request.current_note_path,
            conversation_history=request.conversation_history
        )
        
        return intent_result
        
    except Exception as e:
        logger.error(f"Intent detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/context/build")
async def build_context(
    query: str,
    current_note_path: Optional[str] = None,
    max_tokens: Optional[int] = None,
    service: IntelligenceService = Depends(get_intelligence_service)
):
    """Build context pyramid for a query (useful for debugging and preview)."""
    
    try:
        context_preview = await service.build_context_preview(
            query=query,
            current_note_path=current_note_path,
            max_tokens=max_tokens
        )
        
        return context_preview
        
    except Exception as e:
        logger.error(f"Context building error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper functions
# All helper functions removed - using clean IntelligenceService and FileManager now