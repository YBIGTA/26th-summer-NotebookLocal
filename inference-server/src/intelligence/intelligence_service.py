"""
IntelligenceService - Main service layer for intelligence operations.

Coordinates all intelligence components using clean manager dependencies:
- Uses FileManager for file operations
- Uses ContextEngineClean for context building  
- Uses CapabilityRouter for intent routing
- Provides clean interface for API layer
"""

import logging
from typing import List, Optional, Dict, Any

from ..database.manager import DatabaseManager, db_manager  
from ..database.file_manager import FileManager, file_manager
from ..storage.hybrid_store import HybridStore
from ..processors.embedder import Embedder
from ..llm.core.router import LLMRouter
from .context_engine_clean import ContextEngineClean
from .capability_router import CapabilityRouter
from .intent_detector import IntentDetector
from .engines.understand_engine import UnderstandEngine
from .engines.navigate_engine import NavigateEngine
from .engines.transform_engine import TransformEngine
from .engines.synthesize_engine import SynthesizeEngine
from .engines.maintain_engine import MaintainEngine

logger = logging.getLogger(__name__)


class IntelligenceService:
    """Main service for intelligence operations with clean dependencies."""
    
    def __init__(self,
                 file_manager: FileManager = None,
                 hybrid_store: HybridStore = None,
                 embedder: Embedder = None,
                 llm_router: LLMRouter = None):
        
        # Core dependencies
        self.files = file_manager or file_manager
        self.store = hybrid_store
        self.embedder = embedder
        self.llm = llm_router or LLMRouter.get_instance()
        
        # Initialize intelligence components
        self._initialize_components()
        
        logger.info("✅ IntelligenceService initialized with clean dependencies")
    
    def _initialize_components(self):
        """Initialize all intelligence components with proper dependencies."""
        
        # Context engine with clean dependencies
        self.context_engine = ContextEngineClean(
            hybrid_store=self.store,
            embedder=self.embedder,
            file_manager=self.files
        )
        
        # Intent detector
        self.intent_detector = IntentDetector()
        
        # Capability engines
        self.understand_engine = UnderstandEngine(self.llm)
        self.navigate_engine = NavigateEngine(self.llm, self.store)
        self.transform_engine = TransformEngine(self.llm)
        self.synthesize_engine = SynthesizeEngine(self.llm)
        self.maintain_engine = MaintainEngine(self.llm)
        
        # Main capability router
        self.capability_router = CapabilityRouter(
            context_engine=self.context_engine,
            intent_detector=self.intent_detector,
            understand_engine=self.understand_engine,
            navigate_engine=self.navigate_engine,
            transform_engine=self.transform_engine,
            synthesize_engine=self.synthesize_engine,
            maintain_engine=self.maintain_engine
        )
    
    async def process_intelligent_message(self,
                                        message: str,
                                        current_note_path: Optional[str] = None,
                                        conversation_history: List[str] = None,
                                        session_id: str = None,
                                        max_tokens: int = None,
                                        mentioned_files: List[str] = None,
                                        mentioned_folders: List[str] = None) -> Dict[str, Any]:
        """
        Process intelligent message with full context building and routing.
        
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
        logger.info(f"🧠 Processing intelligent message: '{message[:50]}...'")
        
        try:
            # Use capability router for full processing
            response = await self.capability_router.process_message(
                message=message,
                current_note_path=current_note_path,
                conversation_history=conversation_history or [],
                session_id=session_id or 'default',
                max_tokens=max_tokens,
                mentioned_files=mentioned_files or [],
                mentioned_folders=mentioned_folders or []
            )
            
            logger.info(f"✅ Intelligence response generated: {len(response.content)} chars")
            
            # Convert to dict for API response
            return {
                'content': response.content,
                'sources': response.sources,
                'confidence': response.confidence,
                'intent_type': response.intent_type,
                'sub_capability': response.sub_capability,
                'metadata': response.metadata,
                'suggested_actions': response.suggested_actions,
                'session_id': session_id
            }
            
        except Exception as e:
            logger.error(f"Error processing intelligent message: {e}")
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
    
    async def detect_intent(self, 
                           message: str, 
                           current_note_path: str = None,
                           conversation_history: List[str] = None) -> Dict[str, Any]:
        """
        Detect intent for message without full processing.
        
        Useful for providing hints or previews.
        """
        try:
            intent = await self.intent_detector.detect_intent(
                message=message,
                current_note_path=current_note_path,
                conversation_history=conversation_history or []
            )
            
            return {
                'intent_type': intent.intent_type.value,
                'confidence': intent.confidence,
                'sub_capability': intent.sub_capability,
                'parameters': intent.parameters,
                'reasoning': intent.reasoning
            }
            
        except Exception as e:
            logger.error(f"Error detecting intent: {e}")
            return {
                'intent_type': 'understand',
                'confidence': 0.5,
                'sub_capability': 'question_answer',
                'parameters': {},
                'reasoning': f'Error during detection: {str(e)}'
            }
    
    async def build_context_preview(self,
                                  query: str,
                                  current_note_path: str = None,
                                  max_tokens: int = None) -> Dict[str, Any]:
        """
        Build context preview for debugging/UI purposes.
        
        Returns context pyramid information without processing.
        """
        try:
            pyramid = await self.context_engine.build_context_pyramid(
                query=query,
                current_note_path=current_note_path,
                max_tokens=max_tokens
            )
            
            return {
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
            
        except Exception as e:
            logger.error(f"Error building context preview: {e}")
            return {
                'error': str(e),
                'query': query,
                'current_note_path': current_note_path
            }
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get information about available intelligence capabilities."""
        return {
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
                'semantic_search': self.store is not None,
                'conversation_history': True
            },
            'limits': {
                'dynamic_token_allocation': True,
                'context_pyramid': True,
                'relevance_ranking': True
            }
        }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system health and status information."""
        try:
            file_count = self.files.get_file_count()
            processed_count = self.files.get_file_count('processed')
            
            return {
                'status': 'healthy',
                'file_manager': {
                    'total_files': file_count,
                    'processed_files': processed_count,
                    'processing_rate': processed_count / max(file_count, 1)
                },
                'components': {
                    'context_engine': 'initialized',
                    'capability_router': 'initialized',
                    'intent_detector': 'initialized',
                    'hybrid_store': 'available' if self.store else 'not_available'
                },
                'engines': {
                    'understand': 'ready',
                    'navigate': 'ready',
                    'transform': 'ready', 
                    'synthesize': 'ready',
                    'maintain': 'ready'
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }


# Global instance for easy access
intelligence_service = IntelligenceService()