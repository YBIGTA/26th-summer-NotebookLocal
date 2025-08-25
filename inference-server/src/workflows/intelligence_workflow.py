"""
LangGraph-powered intelligence workflow.

Replaces the manual orchestration in IntelligenceService with a graph-based approach.
Provides visual workflow, automatic state management, conditional routing, and error recovery.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from ..intelligence.intent_detector import IntentDetector, IntentType
from ..intelligence.context_engine import ContextEngine
from ..intelligence.engines.understand_engine import UnderstandEngine
from ..intelligence.engines.navigate_engine import NavigateEngine
from ..intelligence.engines.transform_engine import TransformEngine
from ..intelligence.engines.synthesize_engine import SynthesizeEngine
from ..intelligence.engines.maintain_engine import MaintainEngine
from ..database.file_manager import FileManager
from ..storage.hybrid_store import HybridStore
from ..processors.embedder import Embedder
from ..llm.core.router import LLMRouter

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Workflow execution status."""
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class IntelligenceState:
    """State object for intelligence workflow."""
    # Input
    message: str
    current_note_path: Optional[str] = None
    conversation_history: List[str] = None
    session_id: str = "default"
    max_tokens: Optional[int] = None
    mentioned_files: List[str] = None
    mentioned_folders: List[str] = None
    
    # Processing state
    status: WorkflowStatus = WorkflowStatus.PROCESSING
    current_step: str = "starting"
    error_message: Optional[str] = None
    retry_count: int = 0
    
    # Intermediate results
    intent_result: Optional[Dict[str, Any]] = None
    context_pyramid: Optional[Dict[str, Any]] = None
    engine_response: Optional[Dict[str, Any]] = None
    
    # Final output
    content: Optional[str] = None
    sources: List[str] = None
    confidence: float = 0.0
    intent_type: Optional[str] = None
    sub_capability: Optional[str] = None
    metadata: Dict[str, Any] = None
    suggested_actions: List[str] = None


class IntelligenceWorkflow:
    """LangGraph-based intelligence workflow."""
    
    def __init__(self,
                 file_manager: FileManager = None,
                 hybrid_store: HybridStore = None,
                 embedder: Embedder = None,
                 llm_router: LLMRouter = None):
        
        # Dependencies
        self.file_manager = file_manager
        self.hybrid_store = hybrid_store
        self.embedder = embedder
        self.llm_router = llm_router or LLMRouter.get_instance()
        
        # Initialize components
        self._initialize_components()
        
        # Build workflow graph
        self._build_workflow_graph()
        
        logger.info("✅ IntelligenceWorkflow initialized with LangGraph")
    
    def _initialize_components(self):
        """Initialize intelligence components."""
        self.context_engine = ContextEngine(
            hybrid_store=self.hybrid_store,
            embedder=self.embedder,
            file_manager=self.file_manager
        )
        
        self.intent_detector = IntentDetector(self.llm_router)
        
        # Capability engines
        self.understand_engine = UnderstandEngine(self.llm_router)
        self.navigate_engine = NavigateEngine(self.llm_router, self.hybrid_store)
        self.transform_engine = TransformEngine(self.llm_router)
        self.synthesize_engine = SynthesizeEngine(self.llm_router)
        self.maintain_engine = MaintainEngine(self.llm_router)
    
    def _build_workflow_graph(self):
        """Build the LangGraph workflow."""
        workflow = StateGraph(IntelligenceState)
        
        # Add nodes
        workflow.add_node("detect_intent", self._detect_intent_node)
        workflow.add_node("build_context", self._build_context_node)
        workflow.add_node("route_capability", self._route_capability_node)
        workflow.add_node("process_understand", self._process_understand_node)
        workflow.add_node("process_navigate", self._process_navigate_node)
        workflow.add_node("process_transform", self._process_transform_node)
        workflow.add_node("process_synthesize", self._process_synthesize_node)
        workflow.add_node("process_maintain", self._process_maintain_node)
        workflow.add_node("synthesize_response", self._synthesize_response_node)
        workflow.add_node("handle_error", self._handle_error_node)
        
        # Define edges
        workflow.set_entry_point("detect_intent")
        
        # Intent detection to context building
        workflow.add_edge("detect_intent", "build_context")
        
        # Context building to capability routing
        workflow.add_edge("build_context", "route_capability")
        
        # Conditional routing from capability router to engines
        workflow.add_conditional_edges(
            "route_capability",
            self._route_to_engine,
            {
                "understand": "process_understand",
                "navigate": "process_navigate", 
                "transform": "process_transform",
                "synthesize": "process_synthesize",
                "maintain": "process_maintain",
                "error": "handle_error"
            }
        )
        
        # All engines to response synthesis
        for engine_node in ["process_understand", "process_navigate", 
                           "process_transform", "process_synthesize", "process_maintain"]:
            workflow.add_edge(engine_node, "synthesize_response")
        
        # Response synthesis to end
        workflow.add_edge("synthesize_response", END)
        
        # Error handling to end
        workflow.add_edge("handle_error", END)
        
        self.workflow = workflow.compile()
        logger.info("🔗 Intelligence workflow graph compiled successfully")
    
    async def _detect_intent_node(self, state: IntelligenceState) -> IntelligenceState:
        """Node: Detect user intent from message."""
        logger.info(f"🧠 Intent detection for: '{state.message[:50]}...'")
        state.current_step = "detecting_intent"
        
        try:
            intent_result = await self.intent_detector.detect_intent(
                message=state.message,
                current_note_path=state.current_note_path,
                conversation_history=state.conversation_history or []
            )
            
            state.intent_result = {
                'intent_type': intent_result.intent_type.value,
                'confidence': intent_result.confidence,
                'sub_capability': intent_result.sub_capability,
                'parameters': intent_result.parameters,
                'reasoning': intent_result.reasoning
            }
            
            logger.info(f"🎯 Intent detected: {intent_result.intent_type.value} "
                       f"({intent_result.confidence:.2f}) - {intent_result.sub_capability}")
            
        except Exception as e:
            logger.error(f"❌ Intent detection failed: {e}")
            state.error_message = f"Intent detection failed: {str(e)}"
            state.status = WorkflowStatus.FAILED
        
        return state
    
    async def _build_context_node(self, state: IntelligenceState) -> IntelligenceState:
        """Node: Build context pyramid from available sources."""
        logger.info(f"📚 Building context pyramid")
        state.current_step = "building_context"
        
        try:
            pyramid = await self.context_engine.build_context_pyramid(
                query=state.message,
                current_note_path=state.current_note_path,
                max_tokens=state.max_tokens
            )
            
            state.context_pyramid = {
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
                ]
            }
            
            logger.info(f"📖 Context built: {len(pyramid.items)} items, "
                       f"{pyramid.total_tokens} tokens")
            
        except Exception as e:
            logger.error(f"❌ Context building failed: {e}")
            state.error_message = f"Context building failed: {str(e)}"
            state.status = WorkflowStatus.FAILED
        
        return state
    
    def _route_capability_node(self, state: IntelligenceState) -> IntelligenceState:
        """Node: Route to appropriate capability engine."""
        logger.info(f"🚦 Routing to capability engine")
        state.current_step = "routing_capability"
        
        if state.status == WorkflowStatus.FAILED:
            return state
        
        intent_type = state.intent_result.get('intent_type') if state.intent_result else 'understand'
        logger.info(f"🎯 Routing to: {intent_type}")
        
        return state
    
    def _route_to_engine(self, state: IntelligenceState) -> str:
        """Conditional routing function to select engine."""
        if state.status == WorkflowStatus.FAILED:
            return "error"
        
        intent_type = state.intent_result.get('intent_type') if state.intent_result else 'understand'
        
        # Map intent types to engine names
        route_map = {
            'understand': 'understand',
            'navigate': 'navigate',
            'transform': 'transform',
            'synthesize': 'synthesize',
            'maintain': 'maintain'
        }
        
        return route_map.get(intent_type, 'understand')
    
    async def _process_understand_node(self, state: IntelligenceState) -> IntelligenceState:
        """Node: Process understanding capability."""
        logger.info(f"🔍 Processing understand capability")
        state.current_step = "processing_understand"
        
        try:
            # Build context for engine
            pyramid = await self._rebuild_pyramid_from_state(state)
            
            response = await self.understand_engine.process(
                message=state.message,
                context_pyramid=pyramid,
                intent=state.intent_result,
                session_id=state.session_id
            )
            
            state.engine_response = {
                'content': response.content,
                'sources': response.sources,
                'confidence': response.confidence,
                'metadata': response.metadata,
                'suggested_actions': response.suggested_actions
            }
            
            logger.info(f"✅ Understand processing completed")
            
        except Exception as e:
            logger.error(f"❌ Understand processing failed: {e}")
            state.error_message = f"Understand processing failed: {str(e)}"
            state.status = WorkflowStatus.FAILED
        
        return state
    
    async def _process_navigate_node(self, state: IntelligenceState) -> IntelligenceState:
        """Node: Process navigation capability."""
        logger.info(f"🧭 Processing navigate capability")
        state.current_step = "processing_navigate"
        
        try:
            pyramid = await self._rebuild_pyramid_from_state(state)
            
            response = await self.navigate_engine.process(
                message=state.message,
                context_pyramid=pyramid,
                intent=state.intent_result,
                session_id=state.session_id
            )
            
            state.engine_response = {
                'content': response.content,
                'sources': response.sources,
                'confidence': response.confidence,
                'metadata': response.metadata,
                'suggested_actions': response.suggested_actions
            }
            
            logger.info(f"✅ Navigate processing completed")
            
        except Exception as e:
            logger.error(f"❌ Navigate processing failed: {e}")
            state.error_message = f"Navigate processing failed: {str(e)}"
            state.status = WorkflowStatus.FAILED
        
        return state
    
    async def _process_transform_node(self, state: IntelligenceState) -> IntelligenceState:
        """Node: Process transformation capability."""
        logger.info(f"🔧 Processing transform capability")
        state.current_step = "processing_transform"
        
        try:
            pyramid = await self._rebuild_pyramid_from_state(state)
            
            response = await self.transform_engine.process(
                message=state.message,
                context_pyramid=pyramid,
                intent=state.intent_result,
                session_id=state.session_id
            )
            
            state.engine_response = {
                'content': response.content,
                'sources': response.sources,
                'confidence': response.confidence,
                'metadata': response.metadata,
                'suggested_actions': response.suggested_actions
            }
            
            logger.info(f"✅ Transform processing completed")
            
        except Exception as e:
            logger.error(f"❌ Transform processing failed: {e}")
            state.error_message = f"Transform processing failed: {str(e)}"
            state.status = WorkflowStatus.FAILED
        
        return state
    
    async def _process_synthesize_node(self, state: IntelligenceState) -> IntelligenceState:
        """Node: Process synthesis capability."""
        logger.info(f"⚗️ Processing synthesize capability")
        state.current_step = "processing_synthesize"
        
        try:
            pyramid = await self._rebuild_pyramid_from_state(state)
            
            response = await self.synthesize_engine.process(
                message=state.message,
                context_pyramid=pyramid,
                intent=state.intent_result,
                session_id=state.session_id
            )
            
            state.engine_response = {
                'content': response.content,
                'sources': response.sources,
                'confidence': response.confidence,
                'metadata': response.metadata,
                'suggested_actions': response.suggested_actions
            }
            
            logger.info(f"✅ Synthesize processing completed")
            
        except Exception as e:
            logger.error(f"❌ Synthesize processing failed: {e}")
            state.error_message = f"Synthesize processing failed: {str(e)}"
            state.status = WorkflowStatus.FAILED
        
        return state
    
    async def _process_maintain_node(self, state: IntelligenceState) -> IntelligenceState:
        """Node: Process maintenance capability."""
        logger.info(f"🔧 Processing maintain capability")
        state.current_step = "processing_maintain"
        
        try:
            pyramid = await self._rebuild_pyramid_from_state(state)
            
            response = await self.maintain_engine.process(
                message=state.message,
                context_pyramid=pyramid,
                intent=state.intent_result,
                session_id=state.session_id
            )
            
            state.engine_response = {
                'content': response.content,
                'sources': response.sources,
                'confidence': response.confidence,
                'metadata': response.metadata,
                'suggested_actions': response.suggested_actions
            }
            
            logger.info(f"✅ Maintain processing completed")
            
        except Exception as e:
            logger.error(f"❌ Maintain processing failed: {e}")
            state.error_message = f"Maintain processing failed: {str(e)}"
            state.status = WorkflowStatus.FAILED
        
        return state
    
    def _synthesize_response_node(self, state: IntelligenceState) -> IntelligenceState:
        """Node: Synthesize final response."""
        logger.info(f"📝 Synthesizing final response")
        state.current_step = "synthesizing_response"
        
        if state.status == WorkflowStatus.FAILED:
            return state
        
        try:
            # Extract response from engine
            if state.engine_response:
                state.content = state.engine_response['content']
                state.sources = state.engine_response.get('sources', [])
                state.confidence = state.engine_response.get('confidence', 0.0)
                state.metadata = state.engine_response.get('metadata', {})
                state.suggested_actions = state.engine_response.get('suggested_actions', [])
            
            # Add workflow metadata
            if state.intent_result:
                state.intent_type = state.intent_result['intent_type']
                state.sub_capability = state.intent_result['sub_capability']
            
            # Add session info
            state.metadata = state.metadata or {}
            state.metadata.update({
                'session_id': state.session_id,
                'workflow_version': '1.0',
                'processing_steps': state.current_step
            })
            
            state.status = WorkflowStatus.COMPLETED
            logger.info(f"✅ Response synthesized: {len(state.content or '')} chars")
            
        except Exception as e:
            logger.error(f"❌ Response synthesis failed: {e}")
            state.error_message = f"Response synthesis failed: {str(e)}"
            state.status = WorkflowStatus.FAILED
        
        return state
    
    def _handle_error_node(self, state: IntelligenceState) -> IntelligenceState:
        """Node: Handle errors and provide fallback response."""
        logger.error(f"🚨 Handling workflow error: {state.error_message}")
        state.current_step = "handling_error"
        
        # Provide fallback response
        state.content = f"I encountered an error processing your request: {state.error_message}"
        state.sources = []
        state.confidence = 0.0
        state.intent_type = 'error'
        state.sub_capability = 'error'
        state.metadata = {
            'error': state.error_message,
            'session_id': state.session_id,
            'retry_count': state.retry_count
        }
        state.suggested_actions = [
            'Try rephrasing your question',
            'Check if the server is running properly'
        ]
        
        state.status = WorkflowStatus.FAILED
        
        return state
    
    async def _rebuild_pyramid_from_state(self, state: IntelligenceState):
        """Rebuild context pyramid object from state data."""
        # This is a simplified version - in production you'd want to 
        # store the actual pyramid object or rebuild it properly
        pyramid = await self.context_engine.build_context_pyramid(
            query=state.message,
            current_note_path=state.current_note_path,
            max_tokens=state.max_tokens
        )
        return pyramid
    
    async def process_message(self,
                            message: str,
                            current_note_path: Optional[str] = None,
                            conversation_history: List[str] = None,
                            session_id: str = "default",
                            max_tokens: Optional[int] = None,
                            mentioned_files: List[str] = None,
                            mentioned_folders: List[str] = None) -> Dict[str, Any]:
        """
        Process intelligence message using LangGraph workflow.
        
        Args:
            message: User's message
            current_note_path: Path to current file
            conversation_history: Previous messages
            session_id: Session identifier
            max_tokens: Token limit override
            mentioned_files: Files explicitly mentioned
            mentioned_folders: Folders explicitly mentioned
            
        Returns:
            Intelligence response with content, sources, metadata
        """
        logger.info(f"🧠 Processing message with LangGraph workflow: '{message[:50]}...'")
        
        # Create initial state
        initial_state = IntelligenceState(
            message=message,
            current_note_path=current_note_path,
            conversation_history=conversation_history or [],
            session_id=session_id,
            max_tokens=max_tokens,
            mentioned_files=mentioned_files or [],
            mentioned_folders=mentioned_folders or [],
            sources=[],
            metadata={}
        )
        
        try:
            # Execute workflow
            final_state = await self.workflow.ainvoke(initial_state)
            
            # Convert to API response format
            return {
                'content': final_state.content,
                'sources': final_state.sources,
                'confidence': final_state.confidence,
                'intent_type': final_state.intent_type,
                'sub_capability': final_state.sub_capability,
                'metadata': final_state.metadata,
                'suggested_actions': final_state.suggested_actions,
                'session_id': session_id
            }
            
        except Exception as e:
            logger.error(f"❌ Workflow execution failed: {e}")
            return {
                'content': f"I encountered an error processing your request: {str(e)}",
                'sources': [],
                'confidence': 0.0,
                'intent_type': 'error',
                'sub_capability': 'error',
                'metadata': {'error': str(e)},
                'suggested_actions': [
                    'Try rephrasing your question',
                    'Check if the server is running properly'
                ],
                'session_id': session_id
            }


# Global workflow instance
intelligence_workflow = None

def get_intelligence_workflow() -> IntelligenceWorkflow:
    """Get or create the global intelligence workflow instance."""
    global intelligence_workflow
    
    if intelligence_workflow is None:
        intelligence_workflow = IntelligenceWorkflow()
    
    return intelligence_workflow

def initialize_intelligence_workflow(
    file_manager: FileManager = None,
    hybrid_store: HybridStore = None,
    embedder: Embedder = None,
    llm_router: LLMRouter = None
) -> IntelligenceWorkflow:
    """Initialize the global intelligence workflow with proper dependencies."""
    global intelligence_workflow
    
    intelligence_workflow = IntelligenceWorkflow(
        file_manager=file_manager,
        hybrid_store=hybrid_store,
        embedder=embedder,
        llm_router=llm_router
    )
    
    logger.info("✅ IntelligenceWorkflow initialized with LangGraph")
    return intelligence_workflow