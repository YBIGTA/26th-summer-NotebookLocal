"""
Capability Engines - The five core intelligence capabilities.

Each engine is specialized for a specific type of user intent:
- UnderstandEngine: Answer questions using vault as ground truth
- NavigateEngine: Find connections and forgotten knowledge
- TransformEngine: Edit content while preserving structure  
- SynthesizeEngine: Extract patterns across multiple notes
- MaintainEngine: Vault health and organization
"""

from .base_engine import BaseEngine, EngineResponse
from .understand_engine import UnderstandEngine
from .navigate_engine import NavigateEngine
from .transform_engine import TransformEngine
from .synthesize_engine import SynthesizeEngine
from .maintain_engine import MaintainEngine

__all__ = [
    "BaseEngine",
    "EngineResponse", 
    "UnderstandEngine",
    "NavigateEngine",
    "TransformEngine", 
    "SynthesizeEngine",
    "MaintainEngine"
]