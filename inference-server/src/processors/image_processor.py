from typing import List
import io
import base64
import time
from PIL import Image
from openai import OpenAI

from config import OPENAI_API_KEY, VISION_MODEL
from src.utils.logger import UnifiedLogger

class ImageProcessor:
    """Generate descriptions for images using OpenAI vision models."""

    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def describe(self, images: List[Image.Image]) -> List[str]:
        if not images:
            UnifiedLogger.processing_step("No images to process")
            return []
        
        with UnifiedLogger.time_operation(f"Process {len(images)} images", 
                                        {"model": VISION_MODEL, "image_count": len(images)}):
            descriptions: List[str] = []
            
            for i, img in enumerate(images, 1):
                with UnifiedLogger.time_operation(f"Process image {i}/{len(images)}"):
                    try:
                        # Prepare image
                        buffered = io.BytesIO()
                        img.save(buffered, format="PNG")
                        img_bytes = buffered.getvalue()
                        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                        
                        # Log API request details
                        request_details = {
                            "image_size": f"{img.size[0]}x{img.size[1]}",
                            "image_size_kb": f"{len(img_bytes) / 1024:.1f}KB",
                            "model": VISION_MODEL,
                            "max_tokens": 500
                        }
                        
                        start_time = time.time()
                        UnifiedLogger.api_request("OpenAI", "vision", request_details)
                        
                        # Call OpenAI Vision API
                        response = self.client.chat.completions.create(
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
                        
                        duration = time.time() - start_time
                        description = response.choices[0].message.content
                        
                        # Log API response details
                        response_details = {
                            "prompt_tokens": response.usage.prompt_tokens,
                            "completion_tokens": response.usage.completion_tokens,
                            "total_tokens": response.usage.total_tokens,
                            "description_length": len(description),
                            "description_preview": description[:100] + "..." if len(description) > 100 else description
                        }
                        
                        UnifiedLogger.api_response("OpenAI", "vision", duration, response_details)
                        descriptions.append(description)
                        
                    except Exception as e:
                        UnifiedLogger.log(f"❌ Image {i} processing failed: {str(e)}", level="ERROR")
                        descriptions.append(f"[Image {i} processing failed: {str(e)}]")
            
            successful_count = len([d for d in descriptions if not d.startswith("[Image")])
            UnifiedLogger.processing_step("Image processing completed", {
                "successful": successful_count,
                "total": len(images),
                "success_rate": f"{successful_count/len(images)*100:.1f}%"
            })
            
            return descriptions