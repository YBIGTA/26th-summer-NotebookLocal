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

from src.workflows.intelligence_workflow import IntelligenceWorkflow, initialize_intelligence_workflow
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

# Global intelligence workflow instance
_intelligence_workflow = None

# Dependency to get intelligence workflow
async def get_intelligence_workflow() -> IntelligenceWorkflow:
    """Initialize and return LangGraph intelligence workflow."""
    
    global _intelligence_workflow
    
    if _intelligence_workflow is not None:
        return _intelligence_workflow
    
    try:
        # Get configured components from main processor
        from api.routes import processor
        
        # Initialize LangGraph intelligence workflow
        _intelligence_workflow = initialize_intelligence_workflow(
            file_manager=file_manager,  # Use the imported global file_manager
            hybrid_store=processor.store,
            embedder=processor.embedder,
            llm_router=None  # Will use default singleton
        )
        
        logger.info("✅ LangGraph IntelligenceWorkflow initialized")
        return _intelligence_workflow
        
    except Exception as e:
        logger.error(f"Failed to initialize intelligence workflow: {e}")
        raise HTTPException(status_code=500, detail=f"Intelligence workflow initialization failed: {str(e)}")

@router.post("/chat", response_model=IntelligenceResponse)
async def intelligent_chat(
    request: IntelligenceRequest,
    workflow: IntelligenceWorkflow = Depends(get_intelligence_workflow)
):
    """
    Main intelligence endpoint - processes natural language with LangGraph workflow.
    
    Uses LangGraph for visual workflow orchestration, automatic state management,
    conditional routing, and enhanced error recovery.
    
    Natural language processing:
    - "What did I conclude about X?" → UNDERSTAND
    - "Find my notes about Y" → NAVIGATE  
    - "Make this clearer" → TRANSFORM
    - "What patterns do you see?" → SYNTHESIZE
    - "Check for issues" → MAINTAIN
    """
    
    try:
        logger.info(f"🧠 LangGraph Intelligence request: '{request.message[:50]}...'")
        
        # Process message using LangGraph workflow
        response_dict = await workflow.process_message(
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
        logger.error(f"LangGraph intelligence chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/capabilities", response_model=CapabilityInfoResponse)
async def get_capabilities(workflow: IntelligenceWorkflow = Depends(get_intelligence_workflow)):
    """Get information about available intelligence capabilities."""
    
    try:
        capabilities = {
            'engines': {
                'understand': {
                    'description': 'Answer questions using vault content',
                    'sub_capabilities': ['question_answer', 'explanation', 'verification']
                },
                'navigate': {
                    'description': 'Find connections and navigate knowledge',
                    'sub_capabilities': ['find_connections', 'discovery', 'exploration']
                },
                'transform': {
                    'description': 'Edit and restructure content',
                    'sub_capabilities': ['rewrite', 'restructure', 'format', 'split', 'merge']
                },
                'synthesize': {
                    'description': 'Extract patterns and generate insights',
                    'sub_capabilities': ['pattern_analysis', 'insight_generation', 'contradiction_detection']
                },
                'maintain': {
                    'description': 'Vault health and organization',
                    'sub_capabilities': ['health_check', 'fix_links', 'organize', 'find_duplicates']
                }
            },
            'features': {
                'context_building': True,
                'intent_detection': True,
                'multi_file_processing': True,
                'semantic_search': True,
                'conversation_history': True,
                'langgraph_workflow': True
            }
        }
        
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
    workflow: IntelligenceWorkflow = Depends(get_intelligence_workflow)
):
    """Detect intent from natural language message (useful for UI hints)."""
    
    try:
        intent_result = await workflow.intent_detector.detect_intent(
            message=request.message,
            current_note_path=request.current_note_path,
            conversation_history=request.conversation_history or []
        )
        
        return {
            'intent_type': intent_result.intent_type.value,
            'confidence': intent_result.confidence,
            'sub_capability': intent_result.sub_capability,
            'parameters': intent_result.parameters,
            'reasoning': intent_result.reasoning
        }
        
    except Exception as e:
        logger.error(f"Intent detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/context/build")
async def build_context(
    query: str,
    current_note_path: Optional[str] = None,
    max_tokens: Optional[int] = None,
    workflow: IntelligenceWorkflow = Depends(get_intelligence_workflow)
):
    """Build context pyramid for a query (useful for debugging and preview)."""
    
    try:
        pyramid = await workflow.context_engine.build_context_pyramid(
            query=query,
            current_note_path=current_note_path,
            max_tokens=max_tokens
        )
        
        context_preview = {
            'query': pyramid.query,
            'current_note_path': pyramid.current_note_path,
            'total_items': len(pyramid.items),
            'total_tokens': pyramid.total_tokens,
            'truncated': pyramid.truncated,
            'items': [
                {
                    'source_path': item.source_path,
                    'relevance_score': item.relevance_score,
                    'context_type': item.context_type,
                    'token_count': item.token_count,
                    'content_preview': item.content[:100] + '...' if len(item.content) > 100 else item.content
                }
                for item in pyramid.items
            ],
            'built_at': pyramid.built_at.isoformat()
        }
        
        return context_preview
        
    except Exception as e:
        logger.error(f"Context building error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper functions
# All helper functions removed - using clean IntelligenceWorkflow and FileManager now