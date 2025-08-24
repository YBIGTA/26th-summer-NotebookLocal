"""
IntentDetector - Classify user intent from natural language.

Detects user intent and routes to appropriate capability:
- UNDERSTAND: Answer questions using vault as ground truth
- NAVIGATE: Find connections and forgotten knowledge  
- TRANSFORM: Edit and restructure content
- SYNTHESIZE: Extract patterns across multiple notes
- MAINTAIN: Vault health and organization
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import re

from ..llm.core.router import LLMRouter
from ..llm.models.requests import ChatRequest, Message
from ..llm.utils.config_loader import ConfigLoader
from .prompt_manager import PromptManager

logger = logging.getLogger(__name__)

class IntentType(Enum):
    """The five core intent types."""
    UNDERSTAND = "understand"      # Answer questions using vault content
    NAVIGATE = "navigate"          # Find and discover content
    TRANSFORM = "transform"        # Edit and restructure content
    SYNTHESIZE = "synthesize"      # Extract patterns and insights
    MAINTAIN = "maintain"          # Vault health and organization

@dataclass 
class DetectedIntent:
    """Result of intent detection."""
    intent_type: IntentType
    confidence: float
    sub_capability: str
    parameters: Dict[str, Any]
    reasoning: str

class IntentDetector:
    """Detect user intent from natural language using LLM and patterns."""
    
    def __init__(self, llm_router: LLMRouter):
        self.llm_router = llm_router
        
        # Load routing config for intent detection
        self.config_loader = ConfigLoader()
        self.routing_config = self.config_loader.load_config('configs/routing.yaml')
        self.intent_config = self.routing_config['intelligence']['intent_detection']
        
        # Initialize prompt manager for configurable templates
        self.prompt_manager = PromptManager(self.config_loader)
        
        # Pattern-based intent detection (fast fallback)
        self.intent_patterns = {
            IntentType.UNDERSTAND: [
                r'\b(what|who|when|where|why|how)\b',
                r'\b(explain|tell me|describe|clarify)\b',
                r'\b(mean|means|definition|concept)\b',
                r'\b(according to|based on|mentioned in)\b',
                r'\?',  # Questions often have question marks
            ],
            IntentType.NAVIGATE: [
                r'\b(find|search|look for|locate)\b',
                r'\b(show me|list|browse)\b', 
                r'\b(related|similar|connected)\b',
                r'\b(forgot|remember|written before)\b',
                r'\b(next|should read|recommend)\b',
            ],
            IntentType.TRANSFORM: [
                r'\b(rewrite|edit|change|modify)\b',
                r'\b(improve|better|clearer|fix)\b',
                r'\b(reorganize|restructure|format)\b',
                r'\b(messy|unclear|confusing)\b',
                r'\b(make it|turn this|convert)\b',
            ],
            IntentType.SYNTHESIZE: [
                r'\b(summarize|summary|main points)\b',
                r'\b(patterns|themes|trends|insights)\b',
                r'\b(compare|contrast|differences)\b',
                r'\b(timeline|evolution|progress)\b',
                r'\b(report|overview|analysis)\b',
            ],
            IntentType.MAINTAIN: [
                r'\b(broken|fix|repair|check)\b',
                r'\b(clean up|organize|tidy)\b',
                r'\b(duplicate|missing|orphan)\b',
                r'\b(health|status|problems)\b',
                r'\b(inconsistent|conflict)\b',
            ]
        }
        
        # Sub-capability mapping
        self.sub_capabilities = {
            IntentType.UNDERSTAND: {
                'question_answer': ['what', 'who', 'when', 'where', 'why', 'how', '?'],
                'explanation': ['explain', 'describe', 'clarify', 'mean'],
                'verification': ['correct', 'true', 'accurate', 'verify'],
                'definition': ['definition', 'concept', 'means']
            },
            IntentType.NAVIGATE: {
                'search': ['find', 'search', 'look for', 'locate'],
                'discover': ['forgot', 'remember', 'written before', 'related'],
                'recommend': ['next', 'should read', 'recommend', 'suggest'],
                'browse': ['show me', 'list', 'browse', 'explore']
            },
            IntentType.TRANSFORM: {
                'rewrite': ['rewrite', 'rephrase', 'different', 'better'],
                'restructure': ['reorganize', 'restructure', 'arrange'],
                'format': ['format', 'style', 'convert', 'turn into'],
                'improve': ['improve', 'clearer', 'fix', 'enhance']
            },
            IntentType.SYNTHESIZE: {
                'summarize': ['summarize', 'summary', 'main points', 'key points'],
                'analyze': ['patterns', 'themes', 'trends', 'insights'],
                'compare': ['compare', 'contrast', 'differences', 'similarities'],
                'timeline': ['timeline', 'evolution', 'progress', 'history']
            },
            IntentType.MAINTAIN: {
                'health_check': ['health', 'status', 'problems', 'issues'],
                'fix_links': ['broken', 'fix', 'repair', 'links'],
                'organize': ['clean up', 'organize', 'tidy', 'structure'],
                'find_duplicates': ['duplicate', 'similar notes', 'redundant']
            }
        }
    
    async def detect_intent(
        self,
        message: str,
        current_note_path: Optional[str] = None,
        conversation_history: List[str] = None
    ) -> DetectedIntent:
        """
        Detect user intent from natural language message.
        
        Uses both pattern matching (fast) and LLM analysis (accurate).
        """
        logger.info(f"🧠 Detecting intent for: '{message[:50]}...'")
        
        # First try pattern-based detection (fast)
        pattern_result = self._detect_intent_by_patterns(message)
        
        # Use config threshold for pattern confidence - NO FALLBACKS
        if 'confidence_threshold' not in self.intent_config:
            raise ValueError("confidence_threshold not configured in intent_detection")
        if 'use_llm_fallback' not in self.intent_config:
            raise ValueError("use_llm_fallback not configured in intent_detection")
            
        confidence_threshold = self.intent_config['confidence_threshold']
        use_llm_fallback = self.intent_config['use_llm_fallback']
        
        # If pattern detection is confident enough, use it
        if pattern_result.confidence >= confidence_threshold:
            logger.info(f"✅ High-confidence pattern detection: {pattern_result.intent_type.value}")
            return pattern_result
        
        # Otherwise use LLM for more nuanced understanding (if enabled)
        if use_llm_fallback:
            try:
                llm_result = await self._detect_intent_with_llm(message, current_note_path, conversation_history)
                
                # Combine pattern and LLM results for final decision
                final_result = self._combine_detection_results(pattern_result, llm_result)
                logger.info(f"🎯 Final intent: {final_result.intent_type.value} (confidence: {final_result.confidence:.2f})")
                return final_result
                
            except Exception as e:
                logger.error(f"LLM intent detection failed: {e}")
                # Fallback to pattern result
                logger.info(f"🔄 Falling back to pattern detection: {pattern_result.intent_type.value}")
                return pattern_result
        else:
            # LLM fallback disabled, use pattern result
            logger.info(f"📋 Pattern-only detection: {pattern_result.intent_type.value}")
            return pattern_result
    
    def _detect_intent_by_patterns(self, message: str) -> DetectedIntent:
        """Fast pattern-based intent detection."""
        message_lower = message.lower()
        scores = {intent: 0 for intent in IntentType}
        
        # Score each intent type based on pattern matches
        for intent_type, patterns in self.intent_patterns.items():
            for pattern in patterns:
                matches = len(re.findall(pattern, message_lower))
                scores[intent_type] += matches
        
        # Find best match
        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]
        total_matches = sum(scores.values())
        
        # Calculate confidence
        confidence = best_score / max(1, total_matches) if total_matches > 0 else 0.1
        
        # Detect sub-capability
        sub_capability = self._detect_sub_capability(best_intent, message_lower)
        
        return DetectedIntent(
            intent_type=best_intent,
            confidence=confidence,
            sub_capability=sub_capability,
            parameters={},
            reasoning=f"Pattern match: {best_score} matches out of {total_matches}"
        )
    
    def _detect_sub_capability(self, intent_type: IntentType, message_lower: str) -> str:
        """Detect specific sub-capability within intent type."""
        if intent_type not in self.sub_capabilities:
            return 'general'
        
        capability_scores = {}
        
        for capability, keywords in self.sub_capabilities[intent_type].items():
            score = 0
            for keyword in keywords:
                if keyword in message_lower:
                    score += 1
            capability_scores[capability] = score
        
        # Return capability with highest score, or 'general' if no matches
        best_capability = max(capability_scores, key=capability_scores.get)
        return best_capability if capability_scores[best_capability] > 0 else 'general'
    
    async def _detect_intent_with_llm(
        self,
        message: str,
        current_note_path: Optional[str],
        conversation_history: List[str]
    ) -> DetectedIntent:
        """Use LLM for nuanced intent detection."""
        
        # Get intent detection prompts from template system
        intent_prompts = self.prompt_manager.get_intent_detection_prompt(
            prompt_type="classification_prompt",
            message=message,
            current_note_path=current_note_path,
            conversation_history=' '.join(conversation_history[-3:]) if conversation_history else None
        )
        
        system_prompt = intent_prompts['system_prompt']
        user_template = intent_prompts['user_template']
        
        # Render user template with variables
        user_content = self.prompt_manager._render_template(user_template, {
            'message': message,
            'current_note_path': current_note_path,
            'conversation_history': ' '.join(conversation_history[-3:]) if conversation_history else None
        })

        try:
            # Get LLM response with config-based model (use chat_default)
            llm_model = self.routing_config['rules']['chat_default']
            
            request = ChatRequest(
                messages=[
                    Message(role="system", content=system_prompt),
                    Message(role="user", content=user_content)
                ],
                model=llm_model,
                temperature=0.1,  # Low temperature for consistent classification
                max_tokens=200
            )
            
            response = await self.llm_router.route(request)
            
            if response.choices and len(response.choices) > 0:
                response_text = response.choices[0].message.content.strip()
                
                # Parse JSON response
                import json
                try:
                    result_data = json.loads(response_text)
                    
                    # Validate required fields - NO FALLBACKS
                    if 'intent' not in result_data:
                        raise ValueError("LLM response missing required 'intent' field")
                    if 'confidence' not in result_data:
                        raise ValueError("LLM response missing required 'confidence' field")
                    if 'sub_capability' not in result_data:
                        raise ValueError("LLM response missing required 'sub_capability' field")
                    
                    return DetectedIntent(
                        intent_type=IntentType(result_data['intent'].lower()),
                        confidence=float(result_data['confidence']),
                        sub_capability=result_data['sub_capability'],
                        parameters=result_data.get('parameters', {}),  # parameters can be empty dict
                        reasoning=result_data.get('reasoning', '')     # reasoning can be empty string
                    )
                    
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.error(f"Failed to parse LLM intent response: {e}")
                    logger.error(f"Response was: {response_text}")
                    raise
            else:
                raise Exception("No response from LLM")
                
        except Exception as e:
            logger.error(f"LLM intent detection failed: {e}")
            raise
    
    def _combine_detection_results(self, pattern_result: DetectedIntent, llm_result: DetectedIntent) -> DetectedIntent:
        """Combine pattern and LLM detection for final decision."""
        
        # If both agree, use LLM result with boosted confidence
        if pattern_result.intent_type == llm_result.intent_type:
            return DetectedIntent(
                intent_type=llm_result.intent_type,
                confidence=min(0.95, llm_result.confidence + 0.1),
                sub_capability=llm_result.sub_capability,
                parameters=llm_result.parameters,
                reasoning=f"Pattern + LLM agreement: {llm_result.reasoning}"
            )
        
        # If they disagree, use the one with higher confidence
        if llm_result.confidence > pattern_result.confidence:
            return llm_result
        else:
            return pattern_result
    
    def get_intent_suggestions(self, partial_message: str) -> List[Dict[str, Any]]:
        """Provide intent-based suggestions as user types."""
        suggestions = []
        
        # Quick pattern analysis of partial message
        message_lower = partial_message.lower()
        
        # Suggest likely completions based on detected patterns
        if any(word in message_lower for word in ['what', 'who', 'when', 'where', 'why', 'how']):
            suggestions.append({
                'intent': 'UNDERSTAND',
                'completion': 'did I conclude about this?',
                'description': 'Ask questions about your vault content'
            })
        
        if any(word in message_lower for word in ['find', 'search', 'look']):
            suggestions.append({
                'intent': 'NAVIGATE', 
                'completion': 'everything about [topic]',
                'description': 'Discover related content'
            })
        
        if any(word in message_lower for word in ['make', 'improve', 'fix', 'edit']):
            suggestions.append({
                'intent': 'TRANSFORM',
                'completion': 'this clearer and more professional',
                'description': 'Edit and improve content'
            })
        
        if any(word in message_lower for word in ['summarize', 'themes', 'patterns']):
            suggestions.append({
                'intent': 'SYNTHESIZE',
                'completion': 'the main themes in my research',
                'description': 'Extract insights across notes'
            })
        
        if any(word in message_lower for word in ['check', 'broken', 'clean']):
            suggestions.append({
                'intent': 'MAINTAIN',
                'completion': 'my vault for issues',
                'description': 'Maintain vault health'
            })
        
        return suggestions[:3]  # Limit to top 3 suggestions