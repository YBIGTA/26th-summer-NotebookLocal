"""LangGraph-powered document processing workflow."""

from typing import Dict, Union
from pathlib import Path
import logging
import time
import traceback

from langgraph.graph import END, StateGraph

from ..processors.pdf_processor import PDFProcessor
from ..processors.image_processor import ImageProcessor
from ..processors.text_processor import TextProcessor
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
    ) -> None:

        self.pdf_processor = PDFProcessor()
        self.image_processor = ImageProcessor()
        self.text_processor = TextProcessor()
        self.embedder = embedder or Embedder()
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
        """Step 1: Extract text and images from PDF"""
        start_time = time.time()
        pdf_path = state["pdf_path"]
        
        logger.info(f"🔍 STEP 1: Starting PDF extraction for: {pdf_path}")
        logger.info(f"📄 File size: {Path(pdf_path).stat().st_size / 1024 / 1024:.2f} MB")
        
        try:
            text, images = self.pdf_processor.extract(pdf_path)
            
            # Log actual results
            text_length = len(text) if text else 0
            image_count = len(images) if images else 0
            
            logger.info(f"✅ STEP 1 COMPLETED:")
            logger.info(f"   📝 Text extracted: {text_length:,} characters")
            logger.info(f"   🖼️  Images found: {image_count}")
            logger.info(f"   ⏱️  Time taken: {time.time() - start_time:.2f}s")
            
            if text_length == 0:
                logger.warning("⚠️  No text extracted from PDF!")
            
            state.update({"text": text, "images": images})
            return state
            
        except Exception as e:
            logger.error(f"❌ STEP 1 FAILED: PDF extraction error")
            logger.error(f"   Error: {str(e)}")
            logger.error(f"   Traceback: {traceback.format_exc()}")
            state.update({"text": "", "images": [], "error": str(e)})
            return state

    # ------------------------------------------------------------------
    def _prepare(self, state: Dict) -> Dict:
        """Step 2: Process text into chunks and generate image descriptions"""
        start_time = time.time()
        
        logger.info(f"⚙️  STEP 2: Starting text processing and image description")
        
        # Skip if previous step failed
        if state.get("error"):
            logger.error("❌ STEP 2 SKIPPED: Previous step failed")
            state.update({"chunks": [], "descriptions": []})
            return state
            
        try:
            # Process text into chunks
            text = state.get("text", "")
            logger.info(f"📝 Processing {len(text):,} characters into chunks")
            
            chunks = self.text_processor.process(text)
            chunk_count = len(chunks)
            avg_chunk_size = sum(len(chunk) for chunk in chunks) / chunk_count if chunk_count > 0 else 0
            
            logger.info(f"✂️  Created {chunk_count} text chunks (avg size: {avg_chunk_size:.0f} chars)")
            
            # Process images
            images = state.get("images", [])
            descriptions = []
            
            if images:
                logger.info(f"🖼️  Processing {len(images)} images for descriptions")
                descriptions = self.image_processor.describe(images)
                logger.info(f"📝 Generated {len(descriptions)} image descriptions")
            else:
                logger.info("🖼️  No images to process")
            
            logger.info(f"✅ STEP 2 COMPLETED:")
            logger.info(f"   📄 Text chunks: {chunk_count}")
            logger.info(f"   🖼️  Image descriptions: {len(descriptions)}")
            logger.info(f"   ⏱️  Time taken: {time.time() - start_time:.2f}s")
            
            state.update({"chunks": chunks, "descriptions": descriptions})
            return state
            
        except Exception as e:
            logger.error(f"❌ STEP 2 FAILED: Text processing error")
            logger.error(f"   Error: {str(e)}")
            logger.error(f"   Traceback: {traceback.format_exc()}")
            state.update({"chunks": [], "descriptions": [], "error": str(e)})
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
            chunks = state.get("chunks", [])
            descriptions = state.get("descriptions", [])
            combined = chunks + descriptions
            
            logger.info(f"🔢 Total items to embed: {len(combined)} ({len(chunks)} chunks + {len(descriptions)} descriptions)")
            
            if not combined:
                logger.warning("⚠️  No content to embed - document appears empty")
                state["result"] = {"chunks": 0, "images": 0, "status": "empty"}
                return state
            
            if isinstance(self.store, HybridStore):
                logger.info("🗃️  Using hybrid storage (PostgreSQL + Weaviate)")
                
                # Show what we're about to store
                pdf_path = state["pdf_path"]
                title = Path(pdf_path).stem
                logger.info(f"📄 Document title: {title}")
                logger.info(f"📁 File path: {pdf_path}")
                
                result = self.store.store_document(
                    file_path=pdf_path,
                    chunks=combined,
                    title=title,
                    source_type="pdf",
                    lang="auto",
                    tags=None,
                    page_count=None
                )
                
                # Log actual storage results
                logger.info(f"✅ STEP 3 COMPLETED - Hybrid Storage:")
                logger.info(f"   📄 Document ID: {result.get('document_id', 'N/A')}")
                logger.info(f"   💾 PostgreSQL chunks: {result.get('chunks_stored', 0)}")
                logger.info(f"   🧠 Weaviate vectors: {result.get('vectors_stored', 0)}")
                logger.info(f"   ⏱️  Time taken: {time.time() - start_time:.2f}s")
                
                state["result"] = result
                
            else:
                logger.info("🧠 Using vector store only")
                
                # Generate embeddings
                logger.info("⚙️  Generating embeddings...")
                embeddings = self.embedder.embed(combined)
                logger.info(f"🔢 Generated {len(embeddings)} embeddings (dim: {len(embeddings[0]) if embeddings else 0})")
                
                # Store in vector database
                self.store.add_texts(combined, embeddings)
                
                logger.info(f"✅ STEP 3 COMPLETED - Vector Store:")
                logger.info(f"   📄 Chunks stored: {len(chunks)}")
                logger.info(f"   🖼️  Images stored: {len(descriptions)}")
                logger.info(f"   ⏱️  Time taken: {time.time() - start_time:.2f}s")
                
                state["result"] = {"chunks": len(chunks), "images": len(descriptions), "status": "success"}
            
            return state
            
        except Exception as e:
            logger.error(f"❌ STEP 3 FAILED: Embedding/storage error")
            logger.error(f"   Error: {str(e)}")
            logger.error(f"   Traceback: {traceback.format_exc()}")
            state["result"] = {"chunks": 0, "images": 0, "status": "failed", "error": str(e)}
            return state

    # ------------------------------------------------------------------
    def run(self, pdf_path: str) -> Dict[str, int]:
        """Execute the workflow for ``pdf_path``."""
        
        logger.info(f"🚀 STARTING DOCUMENT PROCESSING WORKFLOW")
        logger.info(f"📁 File: {pdf_path}")
        
        workflow_start_time = time.time()
        
        try:
            final_state = self.graph.invoke({"pdf_path": pdf_path})
            
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
