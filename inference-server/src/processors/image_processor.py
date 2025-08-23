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
        
        # Use a focused prompt for document image processing
        focused_prompt = """Briefly describe the key information in this image. Focus on:
- Text content (headings, labels, captions)
- Data (numbers, values, statistics)
- Main visual elements (charts, diagrams, tables)
- Purpose/context of the image
Keep it concise and factual. Maximum 2-3 sentences."""
        
        descriptions = await self.router.vision(images, focused_prompt)
        logger.info(f"Universal Router vision processing completed: {len(descriptions)} descriptions")
        return descriptions
    
