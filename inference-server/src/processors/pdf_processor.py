from typing import List, Tuple
from PIL import Image
import io
import logging
import warnings

# Suppress font warnings for Korean PDFs
warnings.filterwarnings("ignore", message=".*FontBBox.*")
warnings.filterwarnings("ignore", message=".*cannot be parsed as 4 floats.*")

# Try importing pymupdf first (better for Korean), fallback to pdfplumber
try:
    import fitz  # pymupdf
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

import pdfplumber


class PDFProcessor:
    """Extract text and images from PDF files with Korean font support."""

    def extract(self, pdf_path: str) -> Tuple[str, List[Image.Image]]:
        """Extract text and images from PDF, trying pymupdf first for better Korean support."""
        
        # Try pymupdf first (best for Korean fonts)
        if HAS_PYMUPDF:
            try:
                return self._extract_with_pymupdf(pdf_path)
            except Exception as e:
                logging.warning(f"PyMuPDF extraction failed: {e}, falling back to pdfplumber")
        
        # Fallback to pdfplumber with error handling
        return self._extract_with_pdfplumber(pdf_path)
    
    def _extract_with_pymupdf(self, pdf_path: str) -> Tuple[str, List[Image.Image]]:
        """Extract using PyMuPDF (better for Korean fonts)."""
        text_parts: List[str] = []
        images: List[Image.Image] = []
        
        doc = fitz.open(pdf_path)
        try:
            for page_num in range(doc.page_count):
                page = doc[page_num]
                
                # Extract text with better Unicode support
                text = page.get_text()
                text_parts.append(text)
                
                # Extract images
                image_list = page.get_images()
                for img_index, img in enumerate(image_list):
                    try:
                        xref = img[0]
                        pix = fitz.Pixmap(doc, xref)
                        if pix.n - pix.alpha < 4:  # GRAY or RGB
                            img_bytes = pix.tobytes("png")
                            images.append(Image.open(io.BytesIO(img_bytes)))
                        pix = None  # Release memory
                    except Exception:
                        continue
        finally:
            doc.close()
        
        return "\n".join(text_parts), images
    
    def _extract_with_pdfplumber(self, pdf_path: str) -> Tuple[str, List[Image.Image]]:
        """Extract using pdfplumber with Korean font error handling."""
        text_parts: List[str] = []
        images: List[Image.Image] = []
        
        # Suppress font warnings during processing
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    for page in pdf.pages:
                        try:
                            # Extract text with error handling for Korean fonts
                            text = page.extract_text()
                            text_parts.append(text or "")
                        except Exception as e:
                            logging.warning(f"Text extraction failed for page: {e}")
                            text_parts.append("")
                        
                        # Extract images with error handling
                        try:
                            for img in page.images:
                                try:
                                    base_image = pdf.extract_image(img["object_id"])
                                    image_bytes = base_image["image"]
                                    images.append(Image.open(io.BytesIO(image_bytes)))
                                except Exception:
                                    continue
                        except Exception as e:
                            logging.warning(f"Image extraction failed for page: {e}")
                            continue
            except Exception as e:
                logging.error(f"PDF processing failed: {e}")
                raise
        
        return "\n".join(text_parts), images
