"""
NavigateEngine - Find connections and forgotten knowledge.

Core behaviors:
- Find notes user forgot they wrote
- Suggest missing connections between notes
- Identify related content by meaning, not just keywords
- Recommend reading paths and exploration routes
"""

import logging
import time
from typing import Dict, List, Any, Set
import re
from datetime import datetime, timedelta

from .base_engine import BaseEngine, EngineResponse
from ..context_engine import ContextPyramid
from ..intent_detector import DetectedIntent

logger = logging.getLogger(__name__)

class NavigateEngine(BaseEngine):
    """Help users discover and navigate their knowledge."""
    
    def __init__(self, llm_router, hybrid_store):
        super().__init__(llm_router, "NavigateEngine")
        self.store = hybrid_store
    
    async def process(
        self,
        message: str,
        intent: DetectedIntent,
        context: ContextPyramid
    ) -> EngineResponse:
        """Process NAVIGATE intent to help discover and connect knowledge."""
        
        start_time = time.time()
        self.logger.info(f"🧭 Processing NAVIGATE query: {intent.sub_capability}")
        
        try:
            # Route to specific navigation capability
            if intent.sub_capability == 'search':
                return await self._handle_search(message, context)
            elif intent.sub_capability == 'discover':
                return await self._handle_discover(message, context)
            elif intent.sub_capability == 'recommend':
                return await self._handle_recommend(message, context)
            elif intent.sub_capability == 'browse':
                return await self._handle_browse(message, context)
            else:
                # General navigation
                return await self._handle_general_navigation(message, context)
                
        except Exception as e:
            self.logger.error(f"Error in NavigateEngine: {e}")
            
            return EngineResponse(
                content=f"I had trouble navigating your vault: {str(e)}",
                confidence=0.0,
                metadata={'error': str(e), 'sub_capability': intent.sub_capability},
                suggested_actions=["Try a more specific search query", "Check if files are processed"],
                processing_time=time.time() - start_time
            )
    
    async def _handle_search(self, message: str, context: ContextPyramid) -> EngineResponse:
        """Handle search requests - find specific content."""
        
        # Extract search terms from message
        search_terms = self._extract_search_terms(message)
        
        # Perform enhanced search using hybrid store
        search_results = self.store.search(
            query=' '.join(search_terms),
            k=10,
            alpha=0.6  # Balance semantic and keyword search
        )
        
        # Group results by document
        documents = {}
        for result in search_results:
            doc_info = result.get("document", {})
            doc_title = doc_info.get("title", "Unknown")
            
            if doc_title not in documents:
                documents[doc_title] = {
                    'title': doc_title,
                    'chunks': [],
                    'total_score': 0.0,
                    'metadata': doc_info
                }
            
            documents[doc_title]['chunks'].append({
                'text': result.get('text', ''),
                'score': result.get('score', 0.0),
                'page': result.get('page')
            })
            documents[doc_title]['total_score'] += result.get('score', 0.0)
        
        # Sort documents by relevance
        sorted_docs = sorted(documents.values(), key=lambda x: x['total_score'], reverse=True)
        
        # Format response
        if not sorted_docs:
            content = f"I couldn't find any notes about '{' '.join(search_terms)}' in your vault."
            suggestions = [
                "Try different keywords", 
                "Check spelling of search terms",
                "Make sure relevant files are processed"
            ]
        else:
            content = self._format_search_results(search_terms, sorted_docs)
            suggestions = [
                f"Read {sorted_docs[0]['title']} for most relevant content",
                "Search for more specific terms",
                "Explore connections between these results"
            ]
        
        return EngineResponse(
            content=content,
            confidence=0.8 if sorted_docs else 0.3,
            metadata={
                'search_terms': search_terms,
                'results_count': len(sorted_docs),
                'total_chunks': sum(len(doc['chunks']) for doc in sorted_docs)
            },
            suggested_actions=suggestions,
            processing_time=time.time() - time.time()
        )
    
    async def _handle_discover(self, message: str, context: ContextPyramid) -> EngineResponse:
        """Handle discovery requests - find forgotten or related content."""
        
        # Use LLM to understand what user wants to discover
        system_prompt = """You are a knowledge discovery assistant. The user wants to rediscover or find connections in their vault content.

Your job is to:
1. Analyze the provided context for patterns and connections
2. Highlight content the user might have forgotten
3. Suggest interesting connections between notes
4. Point out related topics they might want to explore

Focus on discovery and connection-making, not just answering questions."""

        context_text = self._format_context_simple(context)
        
        user_prompt = f"""Help me discover connections and forgotten knowledge.

My request: {message}

Here's the relevant context from my vault:
{context_text}

What interesting discoveries, connections, or forgotten content should I know about?"""

        response_text = await self._query_llm(
            system_prompt=system_prompt,
            user_message=user_prompt,
            model_preference="claude-3-5-sonnet-20241022",
            temperature=0.4,  # Slightly higher for creative connections
            max_tokens=1000
        )
        
        # Extract mentioned files for source citations
        sources = self._extract_source_citations(response_text, context)
        
        suggestions = [
            "Explore one of the discovered connections",
            "Create index note linking related concepts",
            "Set up regular rediscovery sessions"
        ]
        
        return EngineResponse(
            content=response_text,
            confidence=self._estimate_confidence(context, intent, len(response_text)),
            metadata={
                'discovery_type': 'connections_and_forgotten',
                'sources_found': len(sources)
            },
            suggested_actions=suggestions,
            processing_time=time.time() - time.time()
        )
    
    async def _handle_recommend(self, message: str, context: ContextPyramid) -> EngineResponse:
        """Handle recommendation requests - suggest what to read next."""
        
        system_prompt = """You are a reading recommendation assistant for an Obsidian vault.

Your job is to:
1. Analyze the user's current context and interests
2. Recommend specific notes to read next
3. Suggest reading paths and exploration routes
4. Explain why each recommendation is valuable

Provide actionable recommendations with clear reasoning."""

        context_text = self._format_context_simple(context)
        
        user_prompt = f"""Recommend what I should read or explore next.

My request: {message}

Context from my current work:
{context_text}

What should I read next and why?"""

        response_text = await self._query_llm(
            system_prompt=system_prompt,
            user_message=user_prompt,
            model_preference="gpt-4o-mini",  # Good for recommendations
            temperature=0.5,  # Higher creativity for recommendations
            max_tokens=600
        )
        
        sources = self._extract_source_citations(response_text, context)
        
        suggestions = [
            "Start with the first recommended note",
            "Create a reading plan based on recommendations", 
            "Ask for recommendations in a specific area"
        ]
        
        return EngineResponse(
            content=response_text,
            confidence=self._estimate_confidence(context, intent, len(response_text)),
            metadata={
                'recommendation_type': 'reading_path',
                'recommended_items': self._count_recommendations(response_text)
            },
            suggested_actions=suggestions,
            processing_time=time.time() - time.time()
        )
    
    async def _handle_browse(self, message: str, context: ContextPyramid) -> EngineResponse:
        """Handle browse requests - explore vault structure and content."""
        
        # Analyze vault structure from context
        structure_analysis = self._analyze_vault_structure(context)
        
        system_prompt = """You are a vault browsing assistant. Help users explore and understand their vault structure.

Your job is to:
1. Show the user what's available in their vault
2. Highlight interesting areas to explore
3. Provide overview of content organization
4. Suggest navigation paths through their knowledge

Be like a knowledgeable librarian guiding exploration."""

        context_text = self._format_context_simple(context)
        structure_text = self._format_structure_analysis(structure_analysis)
        
        user_prompt = f"""Help me browse and explore my vault.

My request: {message}

Vault structure overview:
{structure_text}

Available content:
{context_text}

What should I explore and how should I navigate my vault?"""

        response_text = await self._query_llm(
            system_prompt=system_prompt,
            user_message=user_prompt,
            model_preference="gpt-4o-mini",
            temperature=0.6,  # Creative exploration
            max_tokens=800
        )
        
        sources = self._extract_source_citations(response_text, context)
        
        suggestions = [
            "Start exploring the suggested area",
            "Create navigation index for frequently visited topics",
            "Browse by tags or folders for different perspectives"
        ]
        
        return EngineResponse(
            content=response_text,
            confidence=self._estimate_confidence(context, intent, len(response_text)),
            metadata={
                'browse_type': 'vault_exploration',
                'areas_suggested': len(structure_analysis['folders'])
            },
            suggested_actions=suggestions,
            processing_time=time.time() - time.time()
        )
    
    async def _handle_general_navigation(self, message: str, context: ContextPyramid) -> EngineResponse:
        """Handle general navigation requests."""
        
        system_prompt = """You are a vault navigation assistant. Help users find and explore their knowledge effectively.

Analyze their request and context to provide the most helpful navigation assistance, whether that's finding specific content, making connections, or suggesting exploration paths."""

        context_text = self._format_context_simple(context)
        
        user_prompt = f"""Help me navigate my vault effectively.

My request: {message}

Available context:
{context_text}

How can I best explore or find what I'm looking for?"""

        response_text = await self._query_llm(
            system_prompt=system_prompt,
            user_message=user_prompt,
            temperature=0.4,
            max_tokens=700
        )
        
        return EngineResponse(
            content=response_text,
            confidence=self._estimate_confidence(context, intent, len(response_text)),
            metadata={'navigation_type': 'general'},
            suggested_actions=self._generate_suggested_actions(intent, context, response_text),
            processing_time=time.time() - time.time()
        )
    
    def _extract_search_terms(self, message: str) -> List[str]:
        """Extract search terms from user message."""
        # Remove common words and extract meaningful terms
        stop_words = {'find', 'search', 'look', 'for', 'show', 'me', 'about', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'from'}
        
        # Simple word extraction
        words = re.findall(r'\b\w+\b', message.lower())
        search_terms = [word for word in words if word not in stop_words and len(word) > 2]
        
        return search_terms[:5]  # Limit to 5 most important terms
    
    def _format_search_results(self, search_terms: List[str], documents: List[Dict]) -> str:
        """Format search results for user consumption."""
        
        lines = [f"Found {len(documents)} notes about '{' '.join(search_terms)}':"]
        lines.append("")
        
        for i, doc in enumerate(documents[:8], 1):  # Show top 8 results
            title = doc['title']
            score = doc['total_score']
            chunk_count = len(doc['chunks'])
            
            # Show relevance indicator
            if score >= 0.8:
                relevance = "🔥 Highly relevant"
            elif score >= 0.6:
                relevance = "✨ Very relevant"
            elif score >= 0.4:
                relevance = "👍 Relevant"
            else:
                relevance = "📝 Mentioned"
            
            lines.append(f"{i}. **{title}** {relevance}")
            
            # Show best chunk preview
            if doc['chunks']:
                best_chunk = max(doc['chunks'], key=lambda x: x['score'])
                preview = best_chunk['text'][:150]
                if len(best_chunk['text']) > 150:
                    preview += "..."
                lines.append(f"   > {preview}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _analyze_vault_structure(self, context: ContextPyramid) -> Dict[str, Any]:
        """Analyze vault structure from context items."""
        
        folders = set()
        tags = set()
        types = set()
        
        for item in context.items:
            # Extract folder path
            path_parts = item.source_path.split('/')
            if len(path_parts) > 1:
                folders.add('/'.join(path_parts[:-1]))
            
            # Extract tags from content
            tag_matches = re.findall(r'#(\w+)', item.content)
            tags.update(tag_matches)
            
            # Track context types
            types.add(item.context_type)
        
        return {
            'folders': list(folders)[:10],
            'tags': list(tags)[:15],
            'context_types': list(types),
            'total_items': len(context.items)
        }
    
    def _format_structure_analysis(self, analysis: Dict[str, Any]) -> str:
        """Format structure analysis for LLM."""
        
        lines = []
        
        if analysis['folders']:
            lines.append(f"Folders: {', '.join(analysis['folders'])}")
        
        if analysis['tags']:
            lines.append(f"Tags: {', '.join(f'#{tag}' for tag in analysis['tags'])}")
        
        lines.append(f"Content types: {', '.join(analysis['context_types'])}")
        lines.append(f"Total items: {analysis['total_items']}")
        
        return "\n".join(lines)
    
    def _count_recommendations(self, response_text: str) -> int:
        """Count number of specific recommendations in response."""
        # Look for numbered lists or bullet points
        numbered_items = re.findall(r'^\d+\.', response_text, re.MULTILINE)
        bullet_items = re.findall(r'^[\-\*]', response_text, re.MULTILINE)
        
        return max(len(numbered_items), len(bullet_items))
    
    def _format_context_simple(self, context: ContextPyramid) -> str:
        """Simple context formatting for LLM."""
        if not context.items:
            return "No relevant context found."
        
        sections = []
        for item in context.items:
            sections.append(f"\n--- {item.source_path} ---\n{item.content}")
        
        return f"CONTEXT FROM YOUR VAULT:\n{''.join(sections)}"