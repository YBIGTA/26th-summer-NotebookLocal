from typing import List
from config import CHUNK_SIZE, CHUNK_OVERLAP
from ..utils.helpers import chunk_text


class TextProcessor:
    """Chunk and clean text."""

    def process(self, text: str) -> List[str]:
        return [t.strip() for t in chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP) if t.strip()]
