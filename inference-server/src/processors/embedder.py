"""Universal embedding utilities using modular model routing."""

from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class Embedder:
    """Generate embeddings using Universal Model Router."""

    def __init__(self, router=None) -> None:
        if router is None:
            raise ValueError("Universal Router is required - no fallback available")
        self.router = router

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts using configured embedding model."""
        if not self.router:
            raise Exception("Universal Router not available - cannot generate embeddings")
        
        return self.router.embed(texts)
