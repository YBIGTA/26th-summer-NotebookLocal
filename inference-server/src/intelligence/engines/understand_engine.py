"""
UnderstandEngine - Answer questions using vault content as ground truth.

Core behaviors:
- Never invent information not in the vault
- Always cite which notes information comes from
- Understand questions in context of current work
- Detect when information is missing and say so
"""

import logging
import time
from typing import Dict, List, Any

from .base_engine import BaseEngine, EngineResponse
from ..context_engine import ContextPyramid, ContextEngine
from ..intent_detector import DetectedIntent

logger = logging.getLogger(__name__)

class UnderstandEngine(BaseEngine):
    """Answer questions using vault content as authoritative source."""
    
    def __init__(self, llm_router):
        super().__init__(llm_router, "UnderstandEngine")
    
    async def process(
        self,
        message: str,
        intent: DetectedIntent,
        context: ContextPyramid
    ) -> EngineResponse:
        """Process UNDERSTAND intent to answer questions from vault content."""
        
        start_time = time.time()
        self.logger.info(f"🤔 Processing UNDERSTAND query: {intent.sub_capability}")
        
        try:
            # Build specialized prompt based on sub-capability
            system_prompt = self._build_system_prompt(intent.sub_capability)
            
            # Format context for LLM
            context_text = self._format_context_simple(context)
            
            # Build user message with context
            user_message = f"""Question: {message}

{context_text}

Please answer the question using ONLY the information provided in the context above. If the information is not available in the context, clearly state that."""

            # Query LLM with appropriate model for understanding
            response_text = await self._query_llm(
                system_prompt=system_prompt,
                user_message=user_message,
                model_preference="claude-3-5-sonnet-20241022",  # Use stronger model for understanding
                temperature=0.2,  # Low temperature for factual accuracy
                max_tokens=800
            )
            
            # Calculate confidence and extract sources
            confidence = self._estimate_confidence(context, intent, len(response_text))
            sources = self._extract_source_citations(response_text, context)
            
            # Generate follow-up suggestions
            suggestions = self._generate_understand_suggestions(intent, context, response_text)
            
            processing_time = time.time() - start_time
            
            return EngineResponse(
                content=response_text,
                confidence=confidence,
                metadata={
                    'sub_capability': intent.sub_capability,
                    'context_items_used': len(context.items),
                    'answer_type': self._classify_answer_type(response_text),
                    'has_citations': len(sources) > 0
                },
                suggested_actions=suggestions,
                processing_time=processing_time
            )
            
        except Exception as e:
            self.logger.error(f"Error in UnderstandEngine: {e}")
            
            return EngineResponse(
                content=f"I encountered an error while trying to understand your question: {str(e)}",
                confidence=0.0,
                metadata={'error': str(e), 'sub_capability': intent.sub_capability},
                suggested_actions=["Try rephrasing your question", "Check if relevant files are processed"],
                processing_time=time.time() - start_time
            )
    
    def _build_system_prompt(self, sub_capability: str) -> str:
        """Build system prompt based on sub-capability."""
        
        base_prompt = """You are an intelligent assistant that helps users understand information from their Obsidian vault. 

CRITICAL RULES:
1. ONLY use information from the provided context
2. NEVER invent or hallucinate information
3. If information is not in the context, clearly state "I don't see information about [topic] in your notes"
4. Always cite which specific notes contain the information
5. Maintain the user's voice and terminology from their notes"""

        sub_prompts = {
            'question_answer': """
Your specialty is answering direct questions factually and precisely. 
- Give clear, direct answers
- Quote relevant passages when helpful
- Indicate certainty level if information is partial""",

            'explanation': """
Your specialty is explaining concepts and ideas from the user's notes.
- Break down complex topics into understandable parts
- Connect related concepts from different notes
- Provide comprehensive explanations using multiple sources""",

            'verification': """
Your specialty is verifying information against the user's vault.
- Check claims against note content
- Identify contradictions between notes
- Indicate confidence in verification results""",

            'definition': """
Your specialty is defining terms and concepts from the user's notes.
- Provide clear definitions based on how the user uses terms
- Include examples from their notes when available  
- Note if a term is defined differently in different contexts"""
        }
        
        specific_prompt = sub_prompts.get(sub_capability, sub_prompts['question_answer'])
        
        return base_prompt + specific_prompt
    
    def _format_context_simple(self, context: ContextPyramid) -> str:
        """Simple context formatting if ContextEngine method not available."""
        if not context.items:
            return "No relevant context found."
        
        sections = []
        for item in context.items:
            sections.append(f"\n--- {item.source_path} ---\n{item.content}")
        
        return f"CONTEXT FROM YOUR VAULT:\n{''.join(sections)}"
    
    def _classify_answer_type(self, response_text: str) -> str:
        """Classify the type of answer provided."""
        
        response_lower = response_text.lower()
        
        if "i don't see" in response_lower or "not found" in response_lower:
            return "information_not_found"
        elif "according to" in response_lower or "from your notes" in response_lower:
            return "vault_based_answer"
        elif "?" in response_text:
            return "clarifying_question"
        elif len(response_text.split('\n')) > 3:
            return "detailed_explanation"
        else:
            return "simple_answer"
    
    def _generate_understand_suggestions(
        self,
        intent: DetectedIntent,
        context: ContextPyramid,
        response: str
    ) -> List[str]:
        """Generate suggestions specific to UNDERSTAND capability."""
        
        suggestions = []
        
        # Based on sub-capability
        if intent.sub_capability == 'question_answer':
            suggestions.extend([
                "Ask a follow-up question for more detail",
                "Find related notes about this topic",
                "Explore connections to other concepts"
            ])
        elif intent.sub_capability == 'explanation':
            suggestions.extend([
                "Ask for examples or specific cases",
                "Request comparison with related concepts",
                "Summarize key takeaways"
            ])
        elif intent.sub_capability == 'verification':
            suggestions.extend([
                "Check for contradictory information",
                "Find additional sources on this topic",
                "Update notes if verification reveals issues"
            ])
        
        # Based on context quality
        if context.truncated:
            suggestions.append("Use a more specific query for complete context")
        
        if len(context.items) < 2:
            suggestions.append("Process more related files for better answers")
        
        # Based on response characteristics
        response_lower = response.lower()
        if "i don't see" in response_lower:
            suggestions.extend([
                "Try different keywords for your question",
                "Check if relevant notes are processed"
            ])
        
        return suggestions[:3]
    
    def _format_context_simple(self, context: ContextPyramid) -> str:
        """Simple context formatting for LLM."""
        if not context.items:
            return "No relevant context found."
        
        sections = []
        for item in context.items:
            sections.append(f"\n--- {item.source_path} ---\n{item.content}")
        
        return f"CONTEXT FROM YOUR VAULT:\n{''.join(sections)}"