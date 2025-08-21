"""Universal embedding utilities using modular model routing."""

from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class Embedder:
    """Generate embeddings using Universal Model Router."""

    def __init__(self, router=None) -> None:
        self.router = router
        if not router:
            # Import here to avoid circular imports
            from ..llm.core.router import LLMRouter
            try:
                self.router = LLMRouter()
            except Exception as e:
                logger.error(f"Failed to initialize Universal Router: {e}")
                self.router = None

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts using configured embedding model."""
        if not self.router:
            raise Exception("Universal Router not available - cannot generate embeddings")
        
        try:
            return self.router.embed(texts)
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            # Fallback to hardcoded OpenAI for now during transition
            return self._fallback_embed(texts)
    
    def _fallback_embed(self, texts: List[str]) -> List[List[float]]:
        """Fallback embedding using hardcoded OpenAI (temporary during transition)."""
        logger.warning("Using fallback OpenAI embeddings - modular routing failed")
        
        try:
            from config import OPENAI_API_KEY, EMBEDDING_MODEL
            try:
                from langchain_openai import OpenAIEmbeddings
            except Exception:
                from langchain.embeddings.openai import OpenAIEmbeddings
            
            client = OpenAIEmbeddings(
                model=EMBEDDING_MODEL, openai_api_key=OPENAI_API_KEY
            )
            return client.embed_documents(texts)
        except Exception as e:
            logger.error(f"Fallback embedding also failed: {e}")
            raise Exception(f"All embedding methods failed: {e}")
