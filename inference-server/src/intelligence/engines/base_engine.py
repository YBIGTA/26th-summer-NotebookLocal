"""
BaseEngine - Base class for all capability engines.

Provides common functionality:
- LLM interaction with proper routing
- Response formatting and validation
- Error handling and fallbacks
- Performance tracking
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import time

from ...llm.core.router import LLMRouter
from ...llm.models.requests import ChatRequest, Message
from ...llm.utils.config_loader import ConfigLoader
from ..context_engine import ContextPyramid
from ..intent_detector import DetectedIntent
from ..prompt_manager import PromptManager

logger = logging.getLogger(__name__)

@dataclass
class EngineResponse:
    """Standard response format from capability engines."""
    content: str
    confidence: float
    metadata: Dict[str, Any]
    suggested_actions: List[str]
    processing_time: float

class BaseEngine:
    """Base class for all capability engines."""
    
    def __init__(self, llm_router: LLMRouter, engine_name: str):
        self.llm_router = llm_router
        self.engine_name = engine_name
        self.logger = logging.getLogger(f"{__name__}.{engine_name}")
        
        # Load routing config for model selection
        self.config_loader = ConfigLoader()
        self.routing_config = self.config_loader.load_config('configs/routing.yaml')
        self.engine_config = self.routing_config['intelligence']['engines'].get(engine_name.lower(), {})
        
        # Initialize prompt manager for configurable templates
        self.prompt_manager = PromptManager(self.config_loader)
    
    def _calculate_dynamic_tokens(self, model_name: str = None) -> int:
        """Calculate dynamic token limit based on model's context window and engine ratios."""
        # Get model to use
        if not model_name:
            model_name = self.routing_config['rules']['chat_default']
        
        # Find adapter for model using routing rules
        adapter_name = None
        for rule in self.routing_config['rules']['explicit_models']:
            if model_name in rule['models']:
                adapter_name = rule['adapter']
                break
        
        # Load model config
        model_config = self.config_loader.load_config(f'configs/models/{adapter_name}/{model_name}.yaml')
        
        # Get token allocation config
        token_allocation = self.routing_config['intelligence']['token_allocation']
        context_window_ratio = token_allocation['context_window_ratio']
        engine_ratios = token_allocation['engine_ratios']
        
        # Calculate dynamic token limit
        context_window = model_config['context_window']
        total_allocated = int(context_window * context_window_ratio)
        engine_ratio = engine_ratios[self.engine_name.lower()]
        dynamic_tokens = int(total_allocated * engine_ratio)
        
        self.logger.info(f"Dynamic tokens for {self.engine_name}: {dynamic_tokens} "
                       f"(model: {model_name}, adapter: {adapter_name}, ratio: {engine_ratio})")
        
        return dynamic_tokens
    
    async def process(
        self,
        message: str,
        intent: DetectedIntent,
        context: ContextPyramid
    ) -> EngineResponse:
        """
        Main processing method - must be implemented by subclasses.
        
        Args:
            message: User's original message
            intent: Detected intent with sub-capability
            context: Built context pyramid with relevant vault content
            
        Returns:
            EngineResponse with content and metadata
        """
        raise NotImplementedError("Subclasses must implement process method")
    
    async def _query_llm(
        self,
        system_prompt: str,
        user_message: str,
        model_preference: str = None,
        temperature: float = 0.3,
        max_tokens: int = 1000
    ) -> str:
        """Query LLM with proper error handling and config-based routing."""
        
        start_time = time.time()
        
        try:
            # Use config-based model selection if no preference provided
            model_to_use = model_preference
            if not model_to_use:
                # Use chat_default from routing rules if intelligence is configured to do so
                if self.routing_config['intelligence'].get('use_chat_default', False):
                    model_to_use = self.routing_config['rules']['chat_default']
                else:
                    # Let router decide based on routing config
                    model_to_use = None
            
            # Use config-based parameters - NO FALLBACKS
            if 'temperature' not in self.engine_config:
                raise ValueError(f"temperature not configured for engine {self.engine_name}")
            
            config_temperature = self.engine_config['temperature']
            config_max_tokens = self._calculate_dynamic_tokens(model_to_use)
            
            request = ChatRequest(
                messages=[
                    Message(role="system", content=system_prompt),
                    Message(role="user", content=user_message)
                ],
                model=model_to_use,
                temperature=config_temperature,
                max_tokens=config_max_tokens
            )
            
            self.logger.info(f"📤 Querying LLM: {model_to_use or 'config-default'} (temp={config_temperature})")
            
            response = await self.llm_router.route(request)
            
            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content.strip()
                elapsed = time.time() - start_time
                self.logger.info(f"📥 LLM response received: {len(content)} chars in {elapsed:.2f}s")
                return content
            else:
                raise Exception("No response from LLM")
                
        except Exception as e:
            elapsed = time.time() - start_time
            self.logger.error(f"❌ LLM query failed after {elapsed:.2f}s: {e}")
            raise
    
    async def _query_llm_with_templates(
        self,
        sub_capability: str,
        message: str,
        context: str = "",
        template_variables: Dict[str, Any] = None,
        model_preference: str = None,
        temperature: float = None,
        max_tokens: int = None
    ) -> str:
        """Query LLM using configurable prompt templates."""
        
        template_variables = template_variables or {}
        
        # Get prompts from template system
        system_prompt = self.prompt_manager.get_system_prompt(
            engine_name=self.engine_name,
            sub_capability=sub_capability,
            variables=template_variables
        )
        
        user_prompt = self.prompt_manager.get_user_prompt(
            engine_name=self.engine_name,
            sub_capability=sub_capability,
            message=message,
            context=context,
            **template_variables
        )
        
        # Use the standard _query_llm with template-generated prompts
        return await self._query_llm(
            system_prompt=system_prompt,
            user_message=user_prompt,
            model_preference=model_preference,
            temperature=temperature,
            max_tokens=max_tokens
        )
    
    def _estimate_confidence(
        self,
        context_pyramid: ContextPyramid,
        intent: DetectedIntent,
        response_length: int
    ) -> float:
        """Estimate confidence in the response based on context quality."""
        
        base_confidence = intent.confidence
        
        # Boost confidence based on context quality
        context_boost = 0.0
        
        # More context items generally increase confidence
        if len(context_pyramid.items) >= 3:
            context_boost += 0.1
        
        # Current note in context is good
        current_items = [item for item in context_pyramid.items if item.context_type == 'current']
        if current_items:
            context_boost += 0.1
        
        # High-relevance items boost confidence
        high_relevance_items = [item for item in context_pyramid.items if item.relevance_score >= 0.7]
        if len(high_relevance_items) >= 2:
            context_boost += 0.1
        
        # Penalize if context was truncated
        if context_pyramid.truncated:
            context_boost -= 0.1
        
        # Penalize very short responses (might indicate insufficient context)
        if response_length < 100:
            context_boost -= 0.1
        
        # Final confidence capped at 0.95
        final_confidence = min(0.95, base_confidence + context_boost)
        
        self.logger.debug(f"📊 Confidence calculation: base={base_confidence:.2f}, boost={context_boost:.2f}, final={final_confidence:.2f}")
        
        return max(0.1, final_confidence)  # Minimum 0.1 confidence
    
    def _extract_source_citations(self, response_text: str, context_pyramid: ContextPyramid) -> List[str]:
        """Extract and format source citations from response."""
        sources = [item.source_path for item in context_pyramid.items]
        
        # Filter sources to only those actually referenced in response
        referenced_sources = []
        
        for source in sources:
            # Extract file name from source label
            import re
            file_match = re.search(r'\[([^\]]+)\]', source)
            if file_match:
                file_name = file_match.group(1)
                # Check if this file is referenced in the response
                if file_name.lower() in response_text.lower():
                    referenced_sources.append(source)
        
        # If no specific references found, include top sources
        if not referenced_sources and len(sources) > 0:
            referenced_sources = sources[:3]  # Top 3 sources
        
        return referenced_sources
    
    def _generate_suggested_actions(
        self,
        intent: DetectedIntent,
        context_pyramid: ContextPyramid,
        response: str
    ) -> List[str]:
        """Generate contextual suggestions for follow-up actions."""
        
        suggestions = []
        
        # Intent-specific suggestions
        if intent.intent_type == IntentType.UNDERSTAND:
            suggestions.extend([
                "Ask a follow-up question about this topic",
                "Find related notes to explore further",
                "Summarize key insights from this information"
            ])
            
        elif intent.intent_type == IntentType.NAVIGATE:
            suggestions.extend([
                "Read the most relevant note found",
                "Explore connections between these notes",
                "Search for a more specific topic"
            ])
            
        elif intent.intent_type == IntentType.TRANSFORM:
            suggestions.extend([
                "Preview the changes before applying",
                "Transform a different section",
                "Save this version as a new note"
            ])
            
        elif intent.intent_type == IntentType.SYNTHESIZE:
            suggestions.extend([
                "Dive deeper into one of the patterns found",
                "Create a summary note from these insights",
                "Compare with patterns from a different time period"
            ])
            
        elif intent.intent_type == IntentType.MAINTAIN:
            suggestions.extend([
                "Apply the suggested fixes",
                "Schedule regular vault health checks",
                "Focus on one type of issue at a time"
            ])
        
        # Context-specific suggestions
        if context_pyramid.truncated:
            suggestions.append("Try a more specific query for better context")
        
        if len(context_pyramid.items) < 2:
            suggestions.append("Process more files to improve context")
        
        # Limit to top 3 most relevant suggestions
        return suggestions[:3]