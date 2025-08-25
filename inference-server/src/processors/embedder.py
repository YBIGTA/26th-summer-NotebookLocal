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
        
        logger.info(f"🧠 EMBEDDING: Starting embedding process")
        logger.info(f"   📊 Total texts to embed: {len(texts)}")
        
        if texts:
            avg_length = sum(len(text) for text in texts) / len(texts)
            total_chars = sum(len(text) for text in texts)
            logger.info(f"   📝 Average text length: {avg_length:.0f} chars")
            logger.info(f"   📝 Total characters: {total_chars:,}")
            
            # Show sample texts (first few)
            for i, text in enumerate(texts[:3]):
                preview = text[:100].replace('\n', ' ') + ('...' if len(text) > 100 else '')
                logger.info(f"   📄 Text {i+1}: \"{preview}\"")
            
            if len(texts) > 3:
                logger.info(f"   📄 ... and {len(texts) - 3} more texts")
        
        try:
            import time
            start_time = time.time()
            
            logger.info(f"   🔄 Generating embeddings via router...")
            embeddings = self.router.embed(texts)
            
            embedding_time = time.time() - start_time
            
            if embeddings and len(embeddings) > 0:
                embedding_dim = len(embeddings[0]) if embeddings[0] else 0
                logger.info(f"✅ EMBEDDING COMPLETED:")
                logger.info(f"   🎯 Generated {len(embeddings)} embeddings")
                logger.info(f"   📐 Embedding dimension: {embedding_dim}")
                logger.info(f"   ⏱️  Time taken: {embedding_time:.2f}s")
                logger.info(f"   🚀 Speed: {len(texts)/embedding_time:.1f} texts/sec")
            else:
                logger.warning("⚠️  No embeddings generated!")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"❌ EMBEDDING FAILED:")
            logger.error(f"   Error: {str(e)}")
            raise
