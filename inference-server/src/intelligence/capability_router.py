"""
CapabilityRouter - Route detected intents to appropriate capability engines.

This is the central orchestrator that:
1. Receives detected intent from IntentDetector
2. Builds appropriate context using ContextEngine  
3. Routes to the correct capability engine
4. Formats response for user consumption
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from .context_engine import ContextEngine, ContextPyramid
from .intent_detector import IntentDetector, DetectedIntent, IntentType
from .engines.understand_engine import UnderstandEngine
from .engines.navigate_engine import NavigateEngine
from .engines.transform_engine import TransformEngine  
from .engines.synthesize_engine import SynthesizeEngine
from .engines.maintain_engine import MaintainEngine
from ..llm.utils.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

@dataclass
class CapabilityResponse:
    """Response from a capability engine."""
    content: str
    sources: List[str]
    confidence: float
    intent_type: str
    sub_capability: str
    metadata: Dict[str, Any]
    suggested_actions: List[str]

class CapabilityRouter:
    """Route intents to appropriate capability engines."""
    
    def __init__(
        self,
        context_engine: ContextEngine,
        intent_detector: IntentDetector,
        understand_engine: UnderstandEngine,
        navigate_engine: NavigateEngine,
        transform_engine: TransformEngine,
        synthesize_engine: SynthesizeEngine,
        maintain_engine: MaintainEngine
    ):
        self.context_engine = context_engine
        self.intent_detector = intent_detector
        
        # Load intelligence config for token limits
        self.config_loader = ConfigLoader()
        self.intelligence_config = self.config_loader.load_config('configs/intelligence.yaml')
        self.context_config = self.intelligence_config['context']
        
        # The five capability engines
        self.engines = {
            IntentType.UNDERSTAND: understand_engine,
            IntentType.NAVIGATE: navigate_engine,
            IntentType.TRANSFORM: transform_engine,
            IntentType.SYNTHESIZE: synthesize_engine,
            IntentType.MAINTAIN: maintain_engine
        }
    
    async def process_message(
        self,
        message: str,
        current_note_path: Optional[str] = None,
        conversation_history: List[str] = None,
        vault_files: List[Any] = None,
        mentioned_files: List[str] = None,
        mentioned_folders: List[str] = None
    ) -> CapabilityResponse:
        """
        Main entry point: process a user message with full intelligence.
        
        Flow:
        1. Detect intent from natural language
        2. Build appropriate context pyramid  
        3. Route to correct capability engine
        4. Return formatted response
        """
        logger.info(f"🎯 Processing message: '{message[:50]}...'")
        
        try:
            # Step 1: Detect intent
            detected_intent = await self.intent_detector.detect_intent(
                message, current_note_path, conversation_history
            )
            logger.info(f"🧠 Detected intent: {detected_intent.intent_type.value} ({detected_intent.confidence:.2f})")
            
            # Step 2: Build context pyramid appropriate for this intent
            context_pyramid = await self._build_intent_specific_context(
                detected_intent, message, current_note_path, vault_files, mentioned_files, mentioned_folders
            )
            
            # Step 3: Route to appropriate engine
            engine = self.engines[detected_intent.intent_type]
            engine_response = await engine.process(
                message=message,
                intent=detected_intent,
                context=context_pyramid
            )
            
            # Step 4: Format final response
            response = CapabilityResponse(
                content=engine_response.content,
                sources=self.context_engine.get_context_sources(context_pyramid),
                confidence=min(detected_intent.confidence, engine_response.confidence),
                intent_type=detected_intent.intent_type.value,
                sub_capability=detected_intent.sub_capability,
                metadata={
                    'context_items': len(context_pyramid.items),
                    'context_tokens': context_pyramid.total_tokens,
                    'truncated': context_pyramid.truncated,
                    'processing_time': engine_response.processing_time,
                    **engine_response.metadata
                },
                suggested_actions=engine_response.suggested_actions
            )
            
            logger.info(f"✅ Response generated: {len(response.content)} chars, {len(response.sources)} sources")
            return response
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            
            # Return error response
            return CapabilityResponse(
                content=f"I encountered an error processing your request: {str(e)}",
                sources=[],
                confidence=0.0,
                intent_type="error",
                sub_capability="error",
                metadata={'error': str(e)},
                suggested_actions=["Try rephrasing your question", "Check if your vault files are processed"]
            )
    
    async def _build_intent_specific_context(
        self,
        intent: DetectedIntent,
        message: str,
        current_note_path: Optional[str],
        vault_files: List[Any],
        mentioned_files: List[str] = None,
        mentioned_folders: List[str] = None
    ) -> ContextPyramid:
        """Build context pyramid optimized for specific intent type."""
        
        # Adjust context building strategy based on intent using config-based token limits
        intent_name = intent.intent_type.name.lower()
        max_tokens = self.context_config['token_limits'].get(intent_name, self.context_engine.max_tokens)
        
        if intent.intent_type == IntentType.UNDERSTAND:
            # For questions, prioritize semantic similarity and current note
            return await self.context_engine.build_context_pyramid(
                query=message,
                current_note_path=current_note_path,
                vault_files=vault_files,
                max_tokens=max_tokens,
                mentioned_files=mentioned_files,
                mentioned_folders=mentioned_folders
            )
            
        elif intent.intent_type == IntentType.NAVIGATE:
            # For discovery, cast a wider net with more diverse results
            return await self.context_engine.build_context_pyramid(
                query=message,
                current_note_path=current_note_path, 
                vault_files=vault_files,
                max_tokens=max_tokens,
                mentioned_files=mentioned_files,
                mentioned_folders=mentioned_folders
            )
            
        elif intent.intent_type == IntentType.TRANSFORM:
            # For editing, focus heavily on current note with minimal outside context
            return await self.context_engine.build_context_pyramid(
                query=message,
                current_note_path=current_note_path,
                vault_files=vault_files,
                max_tokens=max_tokens,
                mentioned_files=mentioned_files,
                mentioned_folders=mentioned_folders
            )
            
        elif intent.intent_type == IntentType.SYNTHESIZE:
            # For synthesis, need broad context across multiple notes
            return await self.context_engine.build_context_pyramid(
                query=message,
                current_note_path=current_note_path,
                vault_files=vault_files,
                max_tokens=max_tokens,
                mentioned_files=mentioned_files,
                mentioned_folders=mentioned_folders
            )
            
        elif intent.intent_type == IntentType.MAINTAIN:
            # For maintenance, focus on structural information rather than content
            return await self.context_engine.build_context_pyramid(
                query=message,
                current_note_path=current_note_path,
                vault_files=vault_files,
                max_tokens=max_tokens,
                mentioned_files=mentioned_files,
                mentioned_folders=mentioned_folders
            )
        
        # Default fallback
        return await self.context_engine.build_context_pyramid(
            query=message,
            current_note_path=current_note_path,
            vault_files=vault_files,
            mentioned_files=mentioned_files,
            mentioned_folders=mentioned_folders
        )
    
    def get_capability_info(self) -> Dict[str, Any]:
        """Return information about available capabilities."""
        return {
            'capabilities': {
                'UNDERSTAND': {
                    'description': 'Answer questions using your vault as ground truth',
                    'examples': [
                        'What did I conclude about this topic?',
                        'Who mentioned this concept?',
                        'Explain this idea from my notes'
                    ],
                    'sub_capabilities': ['question_answer', 'explanation', 'verification', 'definition']
                },
                'NAVIGATE': {
                    'description': 'Find and discover content in your vault',
                    'examples': [
                        'Find everything about API design',
                        'What have I written about X?',
                        'Show me related notes'
                    ],
                    'sub_capabilities': ['search', 'discover', 'recommend', 'browse']
                },
                'TRANSFORM': {
                    'description': 'Edit and improve your content intelligently',
                    'examples': [
                        'Make this clearer',
                        'Restructure for better flow',
                        'Convert to professional tone'
                    ],
                    'sub_capabilities': ['rewrite', 'restructure', 'format', 'improve']
                },
                'SYNTHESIZE': {
                    'description': 'Extract patterns and insights across multiple notes',
                    'examples': [
                        'Summarize my research findings',
                        'What patterns emerge from my meetings?',
                        'Compare these approaches'
                    ],
                    'sub_capabilities': ['summarize', 'analyze', 'compare', 'timeline']
                },
                'MAINTAIN': {
                    'description': 'Keep your vault healthy and organized',
                    'examples': [
                        'Check for broken links',
                        'Find duplicate content', 
                        'Suggest better organization'
                    ],
                    'sub_capabilities': ['health_check', 'fix_links', 'organize', 'find_duplicates']
                }
            },
            'total_engines': len(self.engines),
            'context_engine': {
                'max_tokens': self.context_engine.max_tokens,
                'supports_pyramid': True
            }
        }