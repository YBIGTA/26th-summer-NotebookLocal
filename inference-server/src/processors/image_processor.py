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
        
        # Keep OpenAI client for fallback
        try:
            from config import OPENAI_API_KEY
            self.fallback_client = OpenAI(api_key=OPENAI_API_KEY)
        except Exception as e:
            logger.warning(f"Failed to initialize fallback OpenAI client: {e}")
            self.fallback_client = None

    def describe(self, images: List[Image.Image]) -> List[str]:
        if not images:
            logger.info("No images to process")
            return []
        
        logger.info(f"Starting image description for {len(images)} image(s)")
        
        # Try Universal Router first
        if self.router:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                descriptions = loop.run_until_complete(self.router.vision(images))
                logger.info(f"Universal Router vision processing completed: {len(descriptions)} descriptions")
                return descriptions
            except Exception as e:
                logger.error(f"Universal Router vision processing failed: {e}")
                logger.info("Falling back to direct OpenAI processing")
        
        # Fallback to direct OpenAI processing
        return self._fallback_describe(images)
    
    def _fallback_describe(self, images: List[Image.Image]) -> List[str]:
        """Fallback image processing using direct OpenAI API (temporary during transition)."""
        logger.warning("Using fallback OpenAI vision processing - modular routing failed")
        
        if not self.fallback_client:
            raise Exception("No fallback client available and Universal Router failed")
        
        from config import VISION_MODEL
        descriptions: List[str] = []
        
        for i, img in enumerate(images, 1):
            try:
                start_time = time.time()
                logger.info(f"Processing image {i}/{len(images)} with fallback")
                
                # Prepare image
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_bytes = buffered.getvalue()
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                
                # Log request details
                logger.info(f"Fallback OpenAI Vision API Request:")
                logger.info(f"  Model: {VISION_MODEL}")
                logger.info(f"  Image size: {img.size[0]}x{img.size[1]} pixels")
                logger.info(f"  Image data size: {len(img_bytes)/1024:.1f} KB")
                
                # Call OpenAI Vision API
                api_start = time.time()
                response = self.fallback_client.chat.completions.create(
                    model=VISION_MODEL,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe this image in detail, focusing on any text, diagrams, charts, or educational content."},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                        ]
                    }],
                    max_tokens=500
                )
                api_time = time.time() - api_start
                
                # Log response details
                description = response.choices[0].message.content
                logger.info(f"Fallback Vision API Response:")
                logger.info(f"  API call time: {api_time:.2f}s")
                logger.info(f"  Response length: {len(description)} chars")
                logger.info(f"  Response preview: {description[:100]}...")
                
                descriptions.append(description)
                
                total_time = time.time() - start_time
                logger.info(f"Image {i} completed in {total_time:.2f}s")
                
            except Exception as e:
                logger.error(f"Error processing image {i}: {str(e)}")
                descriptions.append(f"[Image {i} processing failed: {str(e)}]")
        
        logger.info(f"Fallback image processing completed: {len([d for d in descriptions if not d.startswith('[Image')])} successful, {len(descriptions)} total")
        return descriptions