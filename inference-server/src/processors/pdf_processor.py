from typing import List, Tuple
from PIL import Image
import io
import time
import logging
import warnings
from dataclasses import dataclass

# Suppress font warnings for PDFs
warnings.filterwarnings("ignore", message=".*FontBBox.*")
warnings.filterwarnings("ignore", message=".*cannot be parsed as 4 floats.*")

logger = logging.getLogger(__name__)


@dataclass
class PageData:
    """Data structure for a single PDF page."""
    page_number: int
    text: str
    images: List[Image.Image]
    
    def __post_init__(self):
        """Ensure images is always a list."""
        if self.images is None:
            self.images = []
    
    def merge_with_image_descriptions(self, descriptions: List[str]) -> str:
        """Merge page text with image descriptions appended at the end."""
        merged_text = self.text
        
        if descriptions and any(desc.strip() for desc in descriptions):
            # Filter out empty descriptions
            valid_descriptions = [desc.strip() for desc in descriptions if desc.strip()]
            
            if valid_descriptions:
                merged_text += "\n\nImages on this page:\n"
                for i, desc in enumerate(valid_descriptions, 1):
                    merged_text += f"Image {i}: {desc}\n"
        
        return merged_text

# Try importing pymupdf first (better text extraction), fallback to pdfplumber
try:
    import fitz  # pymupdf
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

import pdfplumber


class PDFProcessor:
    """Extract text and images from PDF files."""

    def extract(self, pdf_path: str) -> Tuple[str, List[Image.Image]]:
        """Extract text and images from PDF (legacy method - concatenates all pages)."""
        pages = self.extract_pages(pdf_path)
        
        # Concatenate all page text and images for backward compatibility
        all_text = "\n".join(page.text for page in pages)
        all_images = []
        for page in pages:
            all_images.extend(page.images)
        
        return all_text, all_images
    
    def extract_pages(self, pdf_path: str) -> List[PageData]:
        """Extract text and images from PDF, organized by page."""
        
        logger.info(f"Starting page-by-page PDF extraction: {pdf_path}")
        from pathlib import Path
        file_size = Path(pdf_path).stat().st_size
        logger.info(f"PDF file size: {file_size/1024/1024:.2f} MB")
        
        start_time = time.time()
        
        # Try pymupdf first (best text extraction)
        if HAS_PYMUPDF:
            logger.info("Using PyMuPDF library for page-by-page extraction")
            try:
                pages = self._extract_pages_with_pymupdf(pdf_path)
                total_time = time.time() - start_time
                
                total_text = sum(len(page.text) for page in pages)
                total_images = sum(len(page.images) for page in pages)
                
                logger.info(f"PyMuPDF page extraction completed in {total_time:.2f}s")
                logger.info(f"  Pages processed: {len(pages)}")
                logger.info(f"  Total text extracted: {total_text:,} characters")
                logger.info(f"  Total images extracted: {total_images} images")
                return pages
            except Exception as e:
                logger.warning(f"PyMuPDF page extraction failed: {e}, falling back to pdfplumber")
        else:
            logger.info("PyMuPDF not available, using pdfplumber for page extraction")
        
        # Fallback to pdfplumber with error handling
        logger.info("Using pdfplumber library for page-by-page extraction")
        pages = self._extract_pages_with_pdfplumber(pdf_path)
        total_time = time.time() - start_time
        
        total_text = sum(len(page.text) for page in pages)
        total_images = sum(len(page.images) for page in pages)
        
        logger.info(f"Pdfplumber page extraction completed in {total_time:.2f}s")
        logger.info(f"  Pages processed: {len(pages)}")
        logger.info(f"  Total text extracted: {total_text:,} characters")
        logger.info(f"  Total images extracted: {total_images} images")
        return pages
    
    def _extract_with_pymupdf(self, pdf_path: str) -> Tuple[str, List[Image.Image]]:
        """Extract using PyMuPDF (legacy method)."""
        pages = self._extract_pages_with_pymupdf(pdf_path)
        all_text = "\n".join(page.text for page in pages)
        all_images = []
        for page in pages:
            all_images.extend(page.images)
        return all_text, all_images
    
    def _extract_pages_with_pymupdf(self, pdf_path: str) -> List[PageData]:
        """Extract using PyMuPDF, organized by page."""
        pages: List[PageData] = []
        
        doc = fitz.open(pdf_path)
        
        try:
            logger.info(f"Processing {doc.page_count} pages with PyMuPDF")
            
            for page_num in range(doc.page_count):
                page_start_time = time.time()
                page = doc[page_num]
                
                logger.info(f"Processing page {page_num + 1}/{doc.page_count}")
                
                # Extract text with better Unicode support
                text = page.get_text()
                logger.info(f"  Text extracted: {len(text):,} characters")
                
                # Extract images
                page_images: List[Image.Image] = []
                image_list = page.get_images()
                
                logger.info(f"  Found {len(image_list)} image(s) on page")
                
                for img_index, img in enumerate(image_list):
                    try:
                        xref = img[0]
                        pix = fitz.Pixmap(doc, xref)
                        if pix.n - pix.alpha < 4:  # GRAY or RGB
                            img_bytes = pix.tobytes("png")
                            pil_image = Image.open(io.BytesIO(img_bytes))
                            page_images.append(pil_image)
                            logger.info(f"  Extracted image {img_index + 1}: {pil_image.size[0]}x{pil_image.size[1]} pixels")
                        pix = None  # Release memory
                    except Exception as e:
                        logger.warning(f"  Failed to extract image {img_index + 1} from page {page_num + 1}: {e}")
                        continue
                
                page_data = PageData(
                    page_number=page_num + 1,
                    text=text,
                    images=page_images
                )
                pages.append(page_data)
                
                page_time = time.time() - page_start_time
                logger.info(f"  Page {page_num + 1} completed in {page_time:.2f}s")
                    
        finally:
            doc.close()
        
        return pages
    
    def _extract_with_pdfplumber(self, pdf_path: str) -> Tuple[str, List[Image.Image]]:
        """Extract using pdfplumber (legacy method)."""
        pages = self._extract_pages_with_pdfplumber(pdf_path)
        all_text = "\n".join(page.text for page in pages)
        all_images = []
        for page in pages:
            all_images.extend(page.images)
        return all_text, all_images
    
    def _extract_pages_with_pdfplumber(self, pdf_path: str) -> List[PageData]:
        """Extract using pdfplumber, organized by page."""
        pages: List[PageData] = []
        
        # Suppress font warnings during processing
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    logger.info(f"Processing {len(pdf.pages)} pages with pdfplumber")
                    
                    for page_num, page in enumerate(pdf.pages):
                        page_start_time = time.time()
                        
                        logger.info(f"Processing page {page_num + 1}/{len(pdf.pages)}")
                        
                        # Extract text with error handling
                        page_text = ""
                        try:
                            text = page.extract_text()
                            page_text = text or ""
                            logger.info(f"  Text extracted: {len(page_text):,} characters")
                        except Exception as e:
                            logger.warning(f"  Text extraction failed for page {page_num + 1}: {e}")
                            page_text = ""
                        
                        # Extract images with error handling
                        page_images: List[Image.Image] = []
                        try:
                            page_image_list = page.images
                            logger.info(f"  Found {len(page_image_list)} image(s) on page")
                            
                            for img_index, img in enumerate(page_image_list):
                                try:
                                    base_image = pdf.extract_image(img["object_id"])
                                    image_bytes = base_image["image"]
                                    pil_image = Image.open(io.BytesIO(image_bytes))
                                    page_images.append(pil_image)
                                    logger.info(f"  Extracted image {img_index + 1}: {pil_image.size[0]}x{pil_image.size[1]} pixels")
                                except Exception as e:
                                    logger.warning(f"  Failed to extract image {img_index + 1} from page {page_num + 1}: {e}")
                                    continue
                        except Exception as e:
                            logger.warning(f"  Image extraction failed for page {page_num + 1}: {e}")
                        
                        page_data = PageData(
                            page_number=page_num + 1,
                            text=page_text,
                            images=page_images
                        )
                        pages.append(page_data)
                        
                        page_time = time.time() - page_start_time
                        logger.info(f"  Page {page_num + 1} completed in {page_time:.2f}s")
                            
            except Exception as e:
                logger.error(f"PDF processing failed: {e}")
                raise
        
        return pages