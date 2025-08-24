"""
SynthesizeEngine - Extract patterns and insights across multiple notes.

Core behaviors:
- Find patterns across time periods
- Identify recurring themes
- Spot contradictions between notes
- Generate insights user hasn't explicitly noted
"""

import logging
import time
from typing import Dict, List, Any
from datetime import datetime, timedelta
import re

from .base_engine import BaseEngine, EngineResponse
from ..context_engine import ContextPyramid
from ..intent_detector import DetectedIntent

logger = logging.getLogger(__name__)

class SynthesizeEngine(BaseEngine):
    """Extract patterns and generate insights from multiple notes."""
    
    def __init__(self, llm_router):
        super().__init__(llm_router, "SynthesizeEngine")
    
    async def process(
        self,
        message: str,
        intent: DetectedIntent,
        context: ContextPyramid
    ) -> EngineResponse:
        """Process SYNTHESIZE intent to extract patterns and insights."""
        
        start_time = time.time()
        self.logger.info(f"🔍 Processing SYNTHESIZE query: {intent.sub_capability}")
        
        try:
            # Route to specific synthesis capability
            if intent.sub_capability == 'summarize':
                return await self._handle_summarize(message, context)
            elif intent.sub_capability == 'analyze':
                return await self._handle_analyze(message, context)
            elif intent.sub_capability == 'compare':
                return await self._handle_compare(message, context)
            elif intent.sub_capability == 'timeline':
                return await self._handle_timeline(message, context)
            else:
                return await self._handle_general_synthesis(message, context)
                
        except Exception as e:
            self.logger.error(f"Error in SynthesizeEngine: {e}")
            
            return EngineResponse(
                content=f"I had trouble synthesizing your content: {str(e)}",
                confidence=0.0,
                metadata={'error': str(e)},
                suggested_actions=["Try focusing on a specific aspect", "Ensure relevant notes are processed"],
                processing_time=time.time() - start_time
            )
    
    async def _handle_summarize(self, message: str, context: ContextPyramid) -> EngineResponse:
        """Handle summarization requests."""
        
        system_prompt = """You are a synthesis specialist focused on creating clear, comprehensive summaries.

Your job is to:
1. Extract the most important points from multiple notes
2. Organize information logically
3. Identify key themes and takeaways
4. Present a coherent synthesis that's more than just concatenation

Always cite which specific notes contain each piece of information."""

        context_analysis = self._analyze_context_for_synthesis(context)
        context_text = self._format_context_simple(context)
        
        user_prompt = f"""Create a synthesis summary based on my request: {message}

Context analysis:
- Notes span: {context_analysis['date_range']}
- Content types: {', '.join(context_analysis['content_types'])}
- Key topics: {', '.join(context_analysis['topics'])}

Content to synthesize:
{context_text}

Provide a clear, organized summary with key insights and themes."""

        response_text = await self._query_llm(
            system_prompt=system_prompt,
            user_message=user_prompt,
            model_preference="claude-3-5-sonnet-20241022",
            temperature=0.4,  # Balanced for synthesis
            max_tokens=1000
        )
        
        suggestions = [
            "Create a summary note from this synthesis",
            "Dive deeper into one of the key themes",
            "Compare with summaries from different time periods"
        ]
        
        return EngineResponse(
            content=response_text,
            confidence=self._estimate_confidence(context, intent, len(response_text)),
            metadata={
                'synthesis_type': 'summary',
                'notes_synthesized': len(context.items),
                'date_range': context_analysis['date_range']
            },
            suggested_actions=suggestions,
            processing_time=time.time() - time.time()
        )
    
    async def _handle_analyze(self, message: str, context: ContextPyramid) -> EngineResponse:
        """Handle pattern analysis requests."""
        
        system_prompt = """You are a pattern analysis specialist. Your job is to:

1. Identify recurring themes and patterns across multiple notes
2. Spot trends and evolution of ideas over time  
3. Highlight contradictions or inconsistencies
4. Generate insights the user might not have explicitly noted
5. Make connections between seemingly unrelated content

Focus on finding meaningful patterns, not just listing topics."""

        context_text = self._format_context_simple(context)
        
        user_prompt = f"""Analyze patterns and themes in my notes: {message}

Content to analyze:
{context_text}

What patterns, themes, trends, and insights do you see across these notes?"""

        response_text = await self._query_llm(
            system_prompt=system_prompt,
            user_message=user_prompt,
            model_preference="claude-3-5-sonnet-20241022",
            temperature=0.5,  # Higher creativity for pattern recognition
            max_tokens=1000
        )
        
        suggestions = [
            "Explore one pattern in more detail",
            "Create a pattern map or index note",
            "Look for these patterns in other areas of your vault"
        ]
        
        return EngineResponse(
            content=response_text,
            confidence=self._estimate_confidence(context, intent, len(response_text)),
            metadata={'synthesis_type': 'pattern_analysis'},
            suggested_actions=suggestions,
            processing_time=time.time() - time.time()
        )
    
    async def _handle_compare(self, message: str, context: ContextPyramid) -> EngineResponse:
        """Handle comparison requests."""
        
        system_prompt = """You are a comparison specialist. Your job is to:

1. Identify similarities and differences between concepts, approaches, or time periods
2. Highlight evolution of thinking over time
3. Show contradictions that need resolution
4. Present balanced analysis of different perspectives

Always cite specific notes when making comparisons."""

        context_text = self._format_context_simple(context)
        
        user_prompt = f"""Compare and contrast based on my request: {message}

Content to compare:
{context_text}

Provide a structured comparison highlighting similarities, differences, and evolution of ideas."""

        response_text = await self._query_llm(
            system_prompt=system_prompt,
            user_message=user_prompt,
            temperature=0.4,
            max_tokens=1000
        )
        
        return EngineResponse(
            content=response_text,
            confidence=self._estimate_confidence(context, intent, len(response_text)),
            metadata={'synthesis_type': 'comparison'},
            suggested_actions=[
                "Create comparison table or note",
                "Resolve any contradictions found",
                "Explore one side of the comparison deeper"
            ],
            processing_time=time.time() - time.time()
        )
    
    async def _handle_timeline(self, message: str, context: ContextPyramid) -> EngineResponse:
        """Handle timeline analysis requests."""
        
        # Sort context items by date for timeline analysis
        timeline_items = self._sort_context_by_date(context)
        
        system_prompt = """You are a timeline analysis specialist. Your job is to:

1. Show evolution of ideas and decisions over time
2. Identify key milestones and turning points
3. Track progress and changes in thinking
4. Highlight temporal patterns and cycles

Present information chronologically with clear progression."""

        timeline_text = self._format_timeline_context(timeline_items)
        
        user_prompt = f"""Create a timeline analysis based on: {message}

Chronologically organized content:
{timeline_text}

Show the evolution and timeline of relevant information."""

        response_text = await self._query_llm(
            system_prompt=system_prompt,
            user_message=user_prompt,
            temperature=0.4,
            max_tokens=1000
        )
        
        return EngineResponse(
            content=response_text,
            confidence=self._estimate_confidence(context, intent, len(response_text)),
            metadata={
                'synthesis_type': 'timeline',
                'date_range': self._get_date_range(timeline_items)
            },
            suggested_actions=[
                "Create timeline visualization",
                "Focus on specific time period",
                "Identify next steps based on progression"
            ],
            processing_time=time.time() - time.time()
        )
    
    async def _handle_general_synthesis(self, message: str, context: ContextPyramid) -> EngineResponse:
        """Handle general synthesis requests."""
        
        system_prompt = """You are a knowledge synthesis specialist. Extract meaningful insights and patterns from multiple notes to help the user understand their knowledge better."""

        context_text = self._format_context_simple(context)
        
        user_prompt = f"""Synthesize insights from my notes: {message}

Content:
{context_text}

What insights, patterns, and synthesis can you provide?"""

        response_text = await self._query_llm(
            system_prompt=system_prompt,
            user_message=user_prompt,
            temperature=0.5,
            max_tokens=1000
        )
        
        return EngineResponse(
            content=response_text,
            confidence=self._estimate_confidence(context, intent, len(response_text)),
            metadata={'synthesis_type': 'general'},
            suggested_actions=self._generate_suggested_actions(intent, context, response_text),
            processing_time=time.time() - time.time()
        )
    
    def _analyze_context_for_synthesis(self, context: ContextPyramid) -> Dict[str, Any]:
        """Analyze context to understand what we're synthesizing."""
        
        # Extract dates
        dates = []
        for item in context.items:
            if 'modified_at' in item.metadata and item.metadata['modified_at']:
                dates.append(item.metadata['modified_at'])
        
        # Extract topics (basic keyword extraction)
        topics = set()
        for item in context.items:
            # Extract hashtags as topics
            tags = re.findall(r'#(\w+)', item.content)
            topics.update(tags)
        
        # Extract content types
        content_types = [item.context_type for item in context.items]
        
        return {
            'date_range': f"{min(dates).strftime('%Y-%m-%d')} to {max(dates).strftime('%Y-%m-%d')}" if dates else "Unknown",
            'topics': list(topics)[:10],
            'content_types': list(set(content_types))
        }
    
    def _sort_context_by_date(self, context: ContextPyramid) -> List[Any]:
        """Sort context items chronologically."""
        
        items_with_dates = []
        
        for item in context.items:
            date = item.metadata.get('modified_at')
            if date:
                items_with_dates.append((date, item))
        
        # Sort by date
        items_with_dates.sort(key=lambda x: x[0])
        
        return [item for date, item in items_with_dates]
    
    def _format_timeline_context(self, timeline_items: List[Any]) -> str:
        """Format context items in chronological order."""
        
        sections = []
        
        for item in timeline_items:
            date_str = item.metadata.get('modified_at', 'Unknown date')
            if isinstance(date_str, datetime):
                date_str = date_str.strftime('%Y-%m-%d')
            
            sections.append(f"\n=== {date_str}: {item.source_path} ===")
            sections.append(item.content)
        
        return '\n'.join(sections)
    
    def _get_date_range(self, timeline_items: List[Any]) -> str:
        """Get date range from timeline items."""
        
        if not timeline_items:
            return "No dates available"
        
        dates = [item.metadata.get('modified_at') for item in timeline_items if item.metadata.get('modified_at')]
        
        if not dates:
            return "No dates available"
        
        min_date = min(dates)
        max_date = max(dates)
        
        if isinstance(min_date, datetime):
            min_date = min_date.strftime('%Y-%m-%d')
        if isinstance(max_date, datetime):
            max_date = max_date.strftime('%Y-%m-%d')
        
        return f"{min_date} to {max_date}"
    
    def _format_context_simple(self, context: ContextPyramid) -> str:
        """Simple context formatting for LLM."""
        if not context.items:
            return "No relevant context found."
        
        sections = []
        for item in context.items:
            sections.append(f"\n--- {item.source_path} ---\n{item.content}")
        
        return f"CONTEXT FROM YOUR VAULT:\n{''.join(sections)}"