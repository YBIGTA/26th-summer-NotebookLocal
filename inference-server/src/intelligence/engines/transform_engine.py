"""
TransformEngine - Intelligently edit and restructure content.

Core behaviors:
- Always preserve [[links]] and #tags exactly
- Maintain user's voice and style
- Show preview before applying changes
- Support rewrite, restructure, split, merge, format operations
"""

import logging
import time
from typing import Dict, List, Any
import re

from .base_engine import BaseEngine, EngineResponse
from ..context_engine import ContextPyramid
from ..intent_detector import DetectedIntent

logger = logging.getLogger(__name__)

class TransformEngine(BaseEngine):
    """Intelligently transform and edit content."""
    
    def __init__(self, llm_router):
        super().__init__(llm_router, "TransformEngine")
    
    async def process(
        self,
        message: str,
        intent: DetectedIntent,
        context: ContextPyramid
    ) -> EngineResponse:
        """Process TRANSFORM intent to edit and improve content."""
        
        start_time = time.time()
        self.logger.info(f"✏️ Processing TRANSFORM query: {intent.sub_capability}")
        
        try:
            # Get current note content for transformation
            current_content = self._get_current_note_content(context)
            
            if not current_content:
                return EngineResponse(
                    content="I need a current note to transform. Please open a note and try again.",
                    confidence=0.0,
                    metadata={'error': 'no_current_note'},
                    suggested_actions=["Open a note in Obsidian", "Use @filename.md to specify a note"],
                    processing_time=time.time() - start_time
                )
            
            # Route to specific transformation type
            if intent.sub_capability == 'rewrite':
                return await self._handle_rewrite(message, current_content, context)
            elif intent.sub_capability == 'restructure':
                return await self._handle_restructure(message, current_content, context)
            elif intent.sub_capability == 'format':
                return await self._handle_format(message, current_content, context)
            elif intent.sub_capability == 'improve':
                return await self._handle_improve(message, current_content, context)
            else:
                return await self._handle_general_transform(message, current_content, context)
                
        except Exception as e:
            self.logger.error(f"Error in TransformEngine: {e}")
            
            return EngineResponse(
                content=f"I had trouble transforming your content: {str(e)}",
                confidence=0.0,
                metadata={'error': str(e)},
                suggested_actions=["Try a more specific transformation request"],
                processing_time=time.time() - start_time
            )
    
    def _get_current_note_content(self, context: ContextPyramid) -> str:
        """Extract current note content from context pyramid."""
        
        current_items = [item for item in context.items if item.context_type == 'current']
        return current_items[0].content if current_items else ""
    
    async def _handle_rewrite(self, message: str, content: str, context: ContextPyramid) -> EngineResponse:
        """Handle rewrite requests - change tone, style, clarity."""
        
        # Extract transformation intent from message
        transform_intent = self._extract_transform_intent(message)
        
        response_text = await self._query_llm_with_templates(
            sub_capability='rewrite',
            message=message,
            context=content,
            template_variables={
                'transform_intent': transform_intent,
                'content_length': len(content.split()),
                'links_count': len(re.findall(r'\[\[.*?\]\]', content)),
                'tags_count': len(re.findall(r'#\w+', content))
            }
        )
        
        # Validate that links and tags are preserved
        validation_result = self._validate_preservation(content, response_text)
        
        suggestions = [
            "Review the preview before applying",
            "Apply transformation to current note",
            "Save as new version instead of overwriting"
        ]
        
        if not validation_result['valid']:
            suggestions.insert(0, "⚠️ Check that links and tags are preserved")
        
        return EngineResponse(
            content=response_text,
            confidence=0.8 if validation_result['valid'] else 0.5,
            metadata={
                'transform_type': 'rewrite',
                'preservation_check': validation_result,
                'intent': transform_intent
            },
            suggested_actions=suggestions,
            processing_time=time.time() - time.time()
        )
    
    async def _handle_restructure(self, message: str, content: str, context: ContextPyramid) -> EngineResponse:
        """Handle restructure requests - reorganize for better flow."""
        
        response_text = await self._query_llm_with_templates(
            sub_capability='restructure',
            message=message,
            context=content,
            template_variables={
                'content_length': len(content.split()),
                'has_headings': bool(re.search(r'^#+\s', content, re.MULTILINE))
            }
        )
        
        validation_result = self._validate_preservation(content, response_text)
        
        return EngineResponse(
            content=response_text,
            confidence=0.8 if validation_result['valid'] else 0.5,
            metadata={
                'transform_type': 'restructure',
                'preservation_check': validation_result
            },
            suggested_actions=[
                "Review structural changes",
                "Apply restructuring to note",
                "Consider splitting into multiple notes if too long"
            ],
            processing_time=time.time() - time.time()
        )
    
    async def _handle_format(self, message: str, content: str, context: ContextPyramid) -> EngineResponse:
        """Handle format requests - convert between formats."""
        
        return await self._handle_general_transform(message, content, context)
    
    async def _handle_improve(self, message: str, content: str, context: ContextPyramid) -> EngineResponse:
        """Handle improve requests - enhance clarity and quality."""
        
        return await self._handle_general_transform(message, content, context)
    
    async def _handle_general_transform(self, message: str, content: str, context: ContextPyramid) -> EngineResponse:
        """Handle general transformation requests."""
        
        response_text = await self._query_llm_with_templates(
            sub_capability='general',
            message=message,
            context=content
        )
        
        validation_result = self._validate_preservation(content, response_text)
        
        return EngineResponse(
            content=response_text,
            confidence=0.8 if validation_result['valid'] else 0.5,
            metadata={
                'transform_type': 'general',
                'preservation_check': validation_result
            },
            suggested_actions=[
                "Review changes before applying",
                "Apply transformation",
                "Try a different transformation approach"
            ],
            processing_time=time.time() - time.time()
        )
    
    def _extract_transform_intent(self, message: str) -> str:
        """Extract specific transformation intent from message."""
        
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['professional', 'formal', 'business']):
            return "make more professional and formal"
        elif any(word in message_lower for word in ['casual', 'informal', 'friendly']):
            return "make more casual and friendly"
        elif any(word in message_lower for word in ['clear', 'clearer', 'simple']):
            return "make clearer and easier to understand"
        elif any(word in message_lower for word in ['detailed', 'expand', 'elaborate']):
            return "add more detail and explanation"
        elif any(word in message_lower for word in ['concise', 'shorter', 'brief']):
            return "make more concise and to the point"
        else:
            return "improve the content"
    
    def _validate_preservation(self, original: str, transformed: str) -> Dict[str, Any]:
        """Validate that links and tags are preserved in transformation."""
        
        # Extract links and tags from both versions
        original_links = set(re.findall(r'\[\[([^\]]+)\]\]', original))
        transformed_links = set(re.findall(r'\[\[([^\]]+)\]\]', transformed))
        
        original_tags = set(re.findall(r'#(\w+)', original))
        transformed_tags = set(re.findall(r'#(\w+)', transformed))
        
        # Check preservation
        links_preserved = original_links == transformed_links
        tags_preserved = original_tags == transformed_tags
        
        issues = []
        if not links_preserved:
            missing_links = original_links - transformed_links
            added_links = transformed_links - original_links
            if missing_links:
                issues.append(f"Missing links: {missing_links}")
            if added_links:
                issues.append(f"Added links: {added_links}")
        
        if not tags_preserved:
            missing_tags = original_tags - transformed_tags
            added_tags = transformed_tags - original_tags
            if missing_tags:
                issues.append(f"Missing tags: {missing_tags}")
            if added_tags:
                issues.append(f"Added tags: {added_tags}")
        
        return {
            'valid': links_preserved and tags_preserved,
            'links_preserved': links_preserved,
            'tags_preserved': tags_preserved,
            'issues': issues,
            'original_links': len(original_links),
            'original_tags': len(original_tags)
        }
    
    def _format_context_simple(self, context: ContextPyramid) -> str:
        """Simple context formatting for LLM."""
        if not context.items:
            return "No relevant context found."
        
        sections = []
        for item in context.items:
            sections.append(f"\n--- {item.source_path} ---\n{item.content}")
        
        return f"CONTEXT FROM YOUR VAULT:\n{''.join(sections)}"