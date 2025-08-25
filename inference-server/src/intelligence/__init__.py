"""
Intelligence layer for context-aware vault assistance.

This module provides the core intelligence capabilities:
- Context pyramid building for relevance-ranked information
- Intent detection from natural language
- Five core engines: UNDERSTAND, NAVIGATE, TRANSFORM, SYNTHESIZE, MAINTAIN

Note: Orchestration is now handled by LangGraph workflows in src.workflows.intelligence_workflow
"""

from .context_engine import ContextEngine
from .intent_detector import IntentDetector

__all__ = [
    "ContextEngine",
    "IntentDetector"
]