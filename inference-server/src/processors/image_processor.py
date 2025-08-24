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
        if router is None:
            raise ValueError("Universal Router is required - no fallback available")
        self.router = router
        

    async def describe(self, images: List[Image.Image]) -> List[str]:
        if not images:
            logger.info("No images to process")
            return []
        
        logger.info(f"Starting image description for {len(images)} image(s)")
        
        if not self.router:
            raise Exception("Universal Router not available - cannot process images")
        
        # Ultra-concise prompt to minimize context usage
        focused_prompt = """Summarize this image in 1-2 short sentences. Include only: key text, important numbers/data, and document type (chart/table/diagram/text). Be extremely brief."""
        
        descriptions = await self.router.vision(images, focused_prompt)
        logger.info(f"Universal Router vision processing completed: {len(descriptions)} descriptions")
        return descriptions
    
