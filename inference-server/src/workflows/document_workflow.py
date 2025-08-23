"""LangGraph-powered document processing workflow."""

from typing import Dict, Union
from pathlib import Path
import logging
import time
import traceback

from langgraph.graph import END, StateGraph

from ..processors.pdf_processor import PDFProcessor, PageData
from ..processors.image_processor import ImageProcessor
from ..processors.text_processor import TextProcessor, ChunkData
from ..processors.embedder import Embedder
from ..storage.vector_store import SimpleVectorStore, WeaviateVectorStore
from ..storage.hybrid_store import HybridStore

logger = logging.getLogger(__name__)


class DocumentWorkflow:
    """Process a PDF and populate both PostgreSQL and vector store."""

    def __init__(
        self,
        store: Union[SimpleVectorStore, WeaviateVectorStore, HybridStore],
        embedder: Embedder | None = None,
        router = None,
    ) -> None:
        if embedder is None:
            raise ValueError("Embedder is required for DocumentWorkflow")
        if router is None:
            raise ValueError("Router is required for DocumentWorkflow (needed for ImageProcessor)")

        self.pdf_processor = PDFProcessor()
        self.image_processor = ImageProcessor(router=router)
        self.text_processor = TextProcessor()
        self.embedder = embedder
        self.store = store

        workflow = StateGraph(dict)
        workflow.add_node("extract", self._extract)
        workflow.add_node("prepare", self._prepare)
        workflow.add_node("embed_store", self._embed_store)
        workflow.add_edge("extract", "prepare")
        workflow.add_edge("prepare", "embed_store")
        workflow.add_edge("embed_store", END)
        workflow.set_entry_point("extract")
        self.graph = workflow.compile()

    # ------------------------------------------------------------------
    def _extract(self, state: Dict) -> Dict:
        """Step 1: Extract text and images from PDF (page-by-page)"""
        start_time = time.time()
        pdf_path = state["pdf_path"]
        
        logger.info(f"🔍 STEP 1: Starting page-by-page PDF extraction for: {pdf_path}")
        logger.info(f"📄 File size: {Path(pdf_path).stat().st_size / 1024 / 1024:.2f} MB")
        
        try:
            # Use new page-based extraction
            pages = self.pdf_processor.extract_pages(pdf_path)
            
            # Calculate totals for logging
            total_text = sum(len(page.text) for page in pages)
            total_images = sum(len(page.images) for page in pages)
            
            logger.info(f"✅ STEP 1 COMPLETED:")
            logger.info(f"   📄 Pages processed: {len(pages)}")
            logger.info(f"   📝 Total text extracted: {total_text:,} characters")
            logger.info(f"   🖼️  Total images found: {total_images}")
            logger.info(f"   ⏱️  Time taken: {time.time() - start_time:.2f}s")
            
            # Log per-page breakdown
            for i, page in enumerate(pages[:5]):  # Show first 5 pages
                logger.info(f"   📄 Page {page.page_number}: {len(page.text):,} chars, {len(page.images)} images")
            if len(pages) > 5:
                logger.info(f"   📄 ... and {len(pages) - 5} more pages")
            
            if total_text == 0:
                logger.warning("⚠️  No text extracted from PDF!")
            
            # Store pages data in state
            state.update({"pages": pages, "total_text": total_text, "total_images": total_images})
            return state
            
        except Exception as e:
            logger.error(f"❌ STEP 1 FAILED: Page-based PDF extraction error")
            logger.error(f"   Error: {str(e)}")
            logger.error(f"   Traceback: {traceback.format_exc()}")
            state.update({"pages": [], "total_text": 0, "total_images": 0, "error": str(e)})
            return state

    # ------------------------------------------------------------------
    async def _prepare(self, state: Dict) -> Dict:
        """Step 2: Process each page individually (text + images) then chunk"""
        start_time = time.time()
        
        logger.info(f"⚙️  STEP 2: Starting page-by-page integration and chunking")
        
        # Skip if previous step failed
        if state.get("error"):
            logger.error("❌ STEP 2 SKIPPED: Previous step failed")
            state.update({"chunk_data": []})
            return state
            
        try:
            # Get pages from previous step
            pages = state.get("pages", [])
            total_text = state.get("total_text", 0)
            
            logger.info(f"📝 Processing {len(pages)} pages with {total_text:,} total characters")
            
            # Process each page individually: images → descriptions → merge → chunk
            all_chunk_data = []
            total_merged_text = 0
            total_images_processed = 0
            
            for page_idx, page in enumerate(pages, 1):
                page_start_time = time.time()
                logger.info(f"🔄 Processing page {page_idx}/{len(pages)} (Page {page.page_number})")
                
                # Step 2a: Generate descriptions for images on this specific page
                page_descriptions = []
                if page.images:
                    logger.info(f"   🖼️  Found {len(page.images)} image(s) on page {page.page_number}")
                    page_descriptions = await self.image_processor.describe(page.images)
                    logger.info(f"   📝 Generated {len(page_descriptions)} description(s)")
                    total_images_processed += len(page.images)
                else:
                    logger.info(f"   🖼️  No images on page {page.page_number}")
                
                # Step 2b: Merge image descriptions with page text
                merged_page_text = page.merge_with_image_descriptions(page_descriptions)
                total_merged_text += len(merged_page_text)
                
                logger.info(f"   📄 Original text: {len(page.text):,} chars")
                logger.info(f"   📄 Merged text: {len(merged_page_text):,} chars")
                
                # Step 2c: Create temporary page with merged text for chunking
                merged_page = PageData(
                    page_number=page.page_number,
                    text=merged_page_text,
                    images=[]  # Images already processed into text
                )
                
                # Step 2d: Chunk the merged page text
                page_chunks = self.text_processor.process_pages([merged_page])
                logger.info(f"   ✂️  Created {len(page_chunks)} chunks from merged page")
                
                all_chunk_data.extend(page_chunks)
                
                page_time = time.time() - page_start_time
                logger.info(f"   ✅ Page {page.page_number} completed in {page_time:.2f}s")
            
            # Final statistics
            chunk_count = len(all_chunk_data)
            if chunk_count > 0:
                avg_chunk_size = sum(len(chunk.text) for chunk in all_chunk_data) / chunk_count
                pages_with_chunks = len(set(chunk.page_number for chunk in all_chunk_data))
                
                logger.info(f"✅ STEP 2 COMPLETED:")
                logger.info(f"   📄 Pages processed: {len(pages)}")
                logger.info(f"   📄 Pages with chunks: {pages_with_chunks}")
                logger.info(f"   ✂️  Total chunks created: {chunk_count}")
                logger.info(f"   📊 Average chunk size: {avg_chunk_size:.0f} chars")
                logger.info(f"   🖼️  Images processed: {total_images_processed}")
                logger.info(f"   📝 Total merged text: {total_merged_text:,} chars")
                logger.info(f"   ⏱️  Total time: {time.time() - start_time:.2f}s")
                
                # Log chunk distribution by page (first 5 pages)
                page_chunks = {}
                for chunk in all_chunk_data:
                    page_chunks[chunk.page_number] = page_chunks.get(chunk.page_number, 0) + 1
                
                logger.info(f"   📄 Chunk distribution by page:")
                for page_num in sorted(page_chunks.keys())[:5]:
                    logger.info(f"      Page {page_num}: {page_chunks[page_num]} chunks")
                if len(page_chunks) > 5:
                    remaining = len(page_chunks) - 5
                    logger.info(f"      ... and {remaining} more pages")
                    
            else:
                logger.warning("⚠️  No chunks created from any pages!")
            
            state.update({"chunk_data": all_chunk_data})
            return state
            
        except Exception as e:
            logger.error(f"❌ STEP 2 FAILED: Page-by-page integration error")
            logger.error(f"   Error: {str(e)}")
            logger.error(f"   Traceback: {traceback.format_exc()}")
            state.update({"chunk_data": [], "error": str(e)})
            return state

    # ------------------------------------------------------------------
    def _embed_store(self, state: Dict) -> Dict:
        """Step 3: Generate embeddings and store in databases"""
        start_time = time.time()
        
        logger.info(f"💾 STEP 3: Starting embedding generation and storage")
        
        # Skip if previous step failed
        if state.get("error"):
            logger.error("❌ STEP 3 SKIPPED: Previous step failed")
            state["result"] = {"chunks": 0, "images": 0, "status": "failed", "error": state["error"]}
            return state
        
        try:
            chunk_data_list = state.get("chunk_data", [])
            
            logger.info(f"🔢 Total items to embed: {len(chunk_data_list)} chunks (with integrated images)")
            
            if not chunk_data_list:
                logger.warning("⚠️  No content to embed - document appears empty")
                state["result"] = {"chunks": 0, "images": 0, "status": "empty"}
                return state
            
            if isinstance(self.store, HybridStore):
                logger.info("🗃️  Using page-aware hybrid storage (PostgreSQL + Weaviate)")
                
                # Show what we're about to store
                pdf_path = state["pdf_path"]
                title = Path(pdf_path).stem
                pages = state.get("pages", [])
                page_count = len(pages)
                
                logger.info(f"📄 Document title: {title}")
                logger.info(f"📁 File path: {pdf_path}")
                logger.info(f"📄 Total pages: {page_count}")
                
                result = self.store.store_document_with_pages(
                    file_path=pdf_path,
                    chunks=chunk_data_list,
                    descriptions=[],  # No separate descriptions - already integrated
                    title=title,
                    source_type="pdf",
                    lang="auto",
                    tags=None,
                    page_count=page_count
                )
                
                # Log actual storage results
                logger.info(f"✅ STEP 3 COMPLETED - Page-Aware Hybrid Storage:")
                logger.info(f"   📄 Document ID: {result.get('doc_uid', 'N/A')}")
                logger.info(f"   💾 Text chunks stored: {result.get('chunks', 0)}")
                logger.info(f"   🖼️  Image descriptions stored: {result.get('images', 0)}")
                logger.info(f"   📊 Total items stored: {result.get('total_items', 0)}")
                logger.info(f"   ⏱️  Time taken: {time.time() - start_time:.2f}s")
                
                state["result"] = result
                
            else:
                logger.info("🧠 Using vector store only (fallback - page info will be lost)")
                
                # Convert ChunkData back to plain text for vector store
                chunk_texts = [chunk.text for chunk in chunk_data_list]
                
                # Generate embeddings
                logger.info("⚙️  Generating embeddings...")
                embeddings = self.embedder.embed(chunk_texts)
                logger.info(f"🔢 Generated {len(embeddings)} embeddings (dim: {len(embeddings[0]) if embeddings else 0})")
                
                # Store in vector database
                self.store.add_texts(chunk_texts, embeddings)
                
                logger.info(f"✅ STEP 3 COMPLETED - Vector Store:")
                logger.info(f"   📄 Chunks stored: {len(chunk_data_list)} (with integrated images)")
                logger.info(f"   ⏱️  Time taken: {time.time() - start_time:.2f}s")
                
                state["result"] = {"chunks": len(chunk_data_list), "images": 0, "status": "success"}
            
            return state
            
        except Exception as e:
            logger.error(f"❌ STEP 3 FAILED: Embedding/storage error")
            logger.error(f"   Error: {str(e)}")
            logger.error(f"   Traceback: {traceback.format_exc()}")
            state["result"] = {"chunks": 0, "images": 0, "status": "failed", "error": str(e)}
            return state

    # ------------------------------------------------------------------
    async def run(self, pdf_path: str) -> Dict[str, int]:
        """Execute the workflow for ``pdf_path``."""
        
        logger.info(f"🚀 STARTING DOCUMENT PROCESSING WORKFLOW")
        logger.info(f"📁 File: {pdf_path}")
        
        workflow_start_time = time.time()
        
        try:
            final_state = await self.graph.ainvoke({"pdf_path": pdf_path})
            
            total_time = time.time() - workflow_start_time
            result = final_state.get("result", {})
            
            logger.info(f"🎉 WORKFLOW COMPLETED:")
            logger.info(f"   ⏱️  Total time: {total_time:.2f}s")
            logger.info(f"   📊 Final result: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"💥 WORKFLOW FAILED:")
            logger.error(f"   Error: {str(e)}")
            logger.error(f"   Traceback: {traceback.format_exc()}")
            return {"chunks": 0, "images": 0, "status": "failed", "error": str(e)}
