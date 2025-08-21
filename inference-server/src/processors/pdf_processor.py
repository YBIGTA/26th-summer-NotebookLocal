from typing import List, Tuple
from PIL import Image
import io
import warnings

# Suppress font warnings for Korean PDFs
warnings.filterwarnings("ignore", message=".*FontBBox.*")
warnings.filterwarnings("ignore", message=".*cannot be parsed as 4 floats.*")

from src.utils.logger import UnifiedLogger

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
        
        with UnifiedLogger.time_operation(f"PDF extraction: {pdf_path}"):
            # Try pymupdf first (best for Korean fonts)
            if HAS_PYMUPDF:
                UnifiedLogger.processing_step("Using PyMuPDF library")
                try:
                    result = self._extract_with_pymupdf(pdf_path)
                    text, images = result
                    UnifiedLogger.processing_step("PyMuPDF extraction completed", {
                        "text_length": len(text),
                        "image_count": len(images)
                    })
                    return result
                except Exception as e:
                    UnifiedLogger.log(f"⚠️  PyMuPDF extraction failed: {e}, falling back to pdfplumber", level="WARNING")
            else:
                UnifiedLogger.processing_step("PyMuPDF not available, using pdfplumber")
            
            # Fallback to pdfplumber with error handling
            UnifiedLogger.processing_step("Using pdfplumber library")
            result = self._extract_with_pdfplumber(pdf_path)
            text, images = result
            UnifiedLogger.processing_step("Pdfplumber extraction completed", {
                "text_length": len(text),
                "image_count": len(images)
            })
            return result
    
    def _extract_with_pymupdf(self, pdf_path: str) -> Tuple[str, List[Image.Image]]:
        """Extract using PyMuPDF (better for Korean fonts)."""
        text_parts: List[str] = []
        images: List[Image.Image] = []
        
        doc = fitz.open(pdf_path)
        UnifiedLogger.processing_step(f"PDF opened", {"page_count": doc.page_count})
        
        try:
            for page_num in range(doc.page_count):
                with UnifiedLogger.time_operation(f"Process page {page_num + 1}/{doc.page_count}"):
                    page = doc[page_num]
                    
                    # Extract text with better Unicode support
                    text = page.get_text()
                    text_parts.append(text)
                    
                    # Extract images
                    image_list = page.get_images()
                    page_images = 0
                    
                    for img_index, img in enumerate(image_list):
                        try:
                            xref = img[0]
                            pix = fitz.Pixmap(doc, xref)
                            if pix.n - pix.alpha < 4:  # GRAY or RGB
                                img_bytes = pix.tobytes("png")
                                pil_image = Image.open(io.BytesIO(img_bytes))
                                images.append(pil_image)
                                page_images += 1
                            pix = None  # Release memory
                        except Exception as e:
                            UnifiedLogger.log(f"Failed to extract image {img_index + 1}: {e}", level="WARNING")
                            continue
                    
                    UnifiedLogger.processing_step(f"Page {page_num + 1} processed", {
                        "text_chars": len(text),
                        "images_found": len(image_list),
                        "images_extracted": page_images
                    })
                    
        finally:
            doc.close()
        
        total_text = "\n".join(text_parts)
        UnifiedLogger.processing_step("PyMuPDF Summary", {
            "pages_processed": doc.page_count,
            "total_text_chars": len(total_text),
            "total_images": len(images)
        })
        
        return total_text, images
    
    def _extract_with_pdfplumber(self, pdf_path: str) -> Tuple[str, List[Image.Image]]:
        """Extract using pdfplumber with Korean font error handling."""
        text_parts: List[str] = []
        images: List[Image.Image] = []
        
        # Suppress font warnings during processing
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    UnifiedLogger.processing_step(f"PDF opened", {"page_count": len(pdf.pages)})
                    
                    for page_num, page in enumerate(pdf.pages):
                        with UnifiedLogger.time_operation(f"Process page {page_num + 1}/{len(pdf.pages)}"):
                            # Extract text with error handling for Korean fonts
                            try:
                                text = page.extract_text()
                                text_parts.append(text or "")
                            except Exception as e:
                                UnifiedLogger.log(f"Text extraction failed for page {page_num + 1}: {e}", level="WARNING")
                                text_parts.append("")
                            
                            # Extract images with error handling
                            page_images = 0
                            try:
                                page_image_list = page.images
                                
                                for img_index, img in enumerate(page_image_list):
                                    try:
                                        base_image = pdf.extract_image(img["object_id"])
                                        image_bytes = base_image["image"]
                                        pil_image = Image.open(io.BytesIO(image_bytes))
                                        images.append(pil_image)
                                        page_images += 1
                                    except Exception as e:
                                        UnifiedLogger.log(f"Failed to extract image {img_index + 1}: {e}", level="WARNING")
                                        continue
                            except Exception as e:
                                UnifiedLogger.log(f"Image extraction failed for page {page_num + 1}: {e}", level="WARNING")
                            
                            UnifiedLogger.processing_step(f"Page {page_num + 1} processed", {
                                "text_chars": len(text or ""),
                                "images_extracted": page_images
                            })
                            
            except Exception as e:
                UnifiedLogger.log(f"PDF processing failed: {e}", level="ERROR")
                raise
        
        total_text = "\n".join(text_parts)
        UnifiedLogger.processing_step("Pdfplumber Summary", {
            "pages_processed": len(pdf.pages),
            "total_text_chars": len(total_text),
            "total_images": len(images)
        })
        
        return total_text, images