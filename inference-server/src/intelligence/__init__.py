"""
Intelligence layer for context-aware vault assistance.

This module provides the core intelligence capabilities:
- Context pyramid building for relevance-ranked information
- Intent detection from natural language
- Capability routing to specialized engines
- Five core engines: UNDERSTAND, NAVIGATE, TRANSFORM, SYNTHESIZE, MAINTAIN
"""

from .context_engine_clean import ContextEngineClean as ContextEngine
from .intent_detector import IntentDetector
from .capability_router import CapabilityRouter

__all__ = [
    "ContextEngine",
    "IntentDetector", 
    "CapabilityRouter"
]