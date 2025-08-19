from typing import List
import io
import base64
from PIL import Image
from openai import OpenAI

from config import OPENAI_API_KEY, VISION_MODEL


class ImageProcessor:
    """Generate descriptions for images using OpenAI vision models."""

    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def describe(self, images: List[Image.Image]) -> List[str]:
        descriptions: List[str] = []
        for img in images:
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_bytes = buffered.getvalue()
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            
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
            descriptions.append(response.choices[0].message.content)
        return descriptions
