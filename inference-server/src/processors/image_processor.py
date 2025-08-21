from typing import List
import io
import base64
import time
import logging
from PIL import Image
from openai import OpenAI

logger = logging.getLogger(__name__)

class ImageProcessor:
    """Generate descriptions for images using Universal Model Router."""

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
        

    def describe(self, images: List[Image.Image]) -> List[str]:
        if not images:
            logger.info("No images to process")
            return []
        
        logger.info(f"Starting image description for {len(images)} image(s)")
        
        if not self.router:
            raise Exception("Universal Router not available - cannot process images")
        
        import asyncio
        loop = asyncio.get_event_loop()
        descriptions = loop.run_until_complete(self.router.vision(images))
        logger.info(f"Universal Router vision processing completed: {len(descriptions)} descriptions")
        return descriptions
    
