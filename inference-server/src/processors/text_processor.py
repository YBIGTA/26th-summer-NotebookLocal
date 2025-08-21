from typing import List, NamedTuple
from config import CHUNK_SIZE, CHUNK_OVERLAP
from ..utils.helpers import chunk_text
from .pdf_processor import PageData


class ChunkData(NamedTuple):
    """Data structure for a text chunk with metadata."""
    text: str
    page_number: int
    chunk_index: int  # Index within the page
    

class TextProcessor:
    """Chunk and clean text."""

    def process(self, text: str) -> List[str]:
        """Legacy method - process entire text at once."""
        return [t.strip() for t in chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP) if t.strip()]
    
    def process_pages(self, pages: List[PageData]) -> List[ChunkData]:
        """Process pages individually, creating chunks with page metadata."""
        all_chunks: List[ChunkData] = []
        
        for page in pages:
            if not page.text.strip():
                continue
                
            # Chunk text within this page
            page_chunks = chunk_text(page.text, CHUNK_SIZE, CHUNK_OVERLAP)
            
            # Create ChunkData with page information
            for chunk_index, chunk_content in enumerate(page_chunks):
                cleaned_text = chunk_content.strip()
                if cleaned_text:
                    chunk_data = ChunkData(
                        text=cleaned_text,
                        page_number=page.page_number,
                        chunk_index=chunk_index
                    )
                    all_chunks.append(chunk_data)
        
        return all_chunks
