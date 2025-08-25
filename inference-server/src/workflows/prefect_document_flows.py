"""
Prefect-enhanced document processing flows.

Provides robust workflow orchestration with fault tolerance, monitoring, 
and advanced scheduling capabilities built on top of existing DocumentWorkflow.
"""

import logging
import time
import asyncio
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
from datetime import datetime, timedelta

from prefect import flow, task, get_run_logger
from prefect.task_runners import SequentialTaskRunner
from prefect.blocks.system import Secret
from prefect.artifacts import create_markdown_artifact

from ..workflows.document_workflow import DocumentWorkflow
from ..services.processing_models import (
    ProcessingStatus, ProcessingStep, ProcessingProgress, ProcessingResult,
    BatchProcessingResult
)
from ..database.file_manager import FileManager
from ..vault.file_queue_manager import FileQueueManager
from ..storage.hybrid_store import HybridStore
from ..processors.embedder import Embedder
from ..llm.core.router import LLMRouter

logger = logging.getLogger(__name__)


@task(
    name="extract_document_content",
    description="Extract text and images from PDF document",
    tags=["document", "extraction"],
    retries=2,
    retry_delay_seconds=30
)
def extract_document_content(pdf_path: str, workflow: DocumentWorkflow) -> Dict[str, Any]:
    """
    Task: Extract content from document using existing workflow extraction step.
    
    Args:
        pdf_path: Path to PDF file
        workflow: DocumentWorkflow instance
        
    Returns:
        Extraction results with pages data
    """
    task_logger = get_run_logger()
    task_logger.info(f"🔍 Starting content extraction for: {pdf_path}")
    
    start_time = time.time()
    
    try:
        # Use the existing workflow's extraction logic
        state = {"pdf_path": pdf_path}
        result = workflow._extract(state)
        
        extraction_time = time.time() - start_time
        
        if result.get("error"):
            task_logger.error(f"❌ Extraction failed: {result['error']}")
            raise Exception(f"Content extraction failed: {result['error']}")
        
        task_logger.info(f"✅ Extraction completed in {extraction_time:.2f}s")
        task_logger.info(f"   📄 Pages: {len(result.get('pages', []))}")
        task_logger.info(f"   📝 Text: {result.get('total_text', 0):,} chars")
        task_logger.info(f"   🖼️  Images: {result.get('total_images', 0)}")
        
        return {
            "success": True,
            "pages": result.get("pages", []),
            "total_text": result.get("total_text", 0),
            "total_images": result.get("total_images", 0),
            "extraction_time": extraction_time,
            "file_size_mb": Path(pdf_path).stat().st_size / 1024 / 1024
        }
        
    except Exception as e:
        task_logger.error(f"❌ Content extraction failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "extraction_time": time.time() - start_time
        }


@task(
    name="process_and_chunk_content",
    description="Process images and chunk text content",
    tags=["document", "processing"],
    retries=2,
    retry_delay_seconds=60
)
async def process_and_chunk_content(
    extraction_result: Dict[str, Any], 
    pdf_path: str,
    workflow: DocumentWorkflow
) -> Dict[str, Any]:
    """
    Task: Process images and chunk content using existing workflow logic.
    
    Args:
        extraction_result: Results from extraction task
        pdf_path: Path to PDF file
        workflow: DocumentWorkflow instance
        
    Returns:
        Processing results with chunked data
    """
    task_logger = get_run_logger()
    task_logger.info(f"⚙️ Starting content processing and chunking")
    
    start_time = time.time()
    
    try:
        if not extraction_result.get("success"):
            raise Exception(f"Cannot process - extraction failed: {extraction_result.get('error')}")
        
        # Use the existing workflow's preparation logic
        state = {
            "pdf_path": pdf_path,
            "pages": extraction_result["pages"],
            "total_text": extraction_result["total_text"],
            "total_images": extraction_result["total_images"]
        }
        
        result = await workflow._prepare(state)
        
        processing_time = time.time() - start_time
        
        if result.get("error"):
            task_logger.error(f"❌ Processing failed: {result['error']}")
            raise Exception(f"Content processing failed: {result['error']}")
        
        chunk_data = result.get("chunk_data", [])
        
        task_logger.info(f"✅ Processing completed in {processing_time:.2f}s")
        task_logger.info(f"   ✂️  Chunks created: {len(chunk_data)}")
        
        if chunk_data:
            avg_chunk_size = sum(len(chunk.text) for chunk in chunk_data) / len(chunk_data)
            task_logger.info(f"   📊 Average chunk size: {avg_chunk_size:.0f} chars")
        
        return {
            "success": True,
            "chunk_data": chunk_data,
            "chunk_count": len(chunk_data),
            "processing_time": processing_time
        }
        
    except Exception as e:
        task_logger.error(f"❌ Content processing failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "processing_time": time.time() - start_time
        }


@task(
    name="embed_and_store_content",
    description="Generate embeddings and store in databases",
    tags=["document", "storage"],
    retries=3,
    retry_delay_seconds=120
)
def embed_and_store_content(
    processing_result: Dict[str, Any],
    pdf_path: str,
    workflow: DocumentWorkflow
) -> Dict[str, Any]:
    """
    Task: Generate embeddings and store content using existing workflow logic.
    
    Args:
        processing_result: Results from processing task
        pdf_path: Path to PDF file
        workflow: DocumentWorkflow instance
        
    Returns:
        Storage results
    """
    task_logger = get_run_logger()
    task_logger.info(f"💾 Starting embedding generation and storage")
    
    start_time = time.time()
    
    try:
        if not processing_result.get("success"):
            raise Exception(f"Cannot store - processing failed: {processing_result.get('error')}")
        
        # Use the existing workflow's storage logic
        state = {
            "pdf_path": pdf_path,
            "chunk_data": processing_result["chunk_data"],
            "pages": []  # This would come from extraction in real workflow
        }
        
        result = workflow._embed_store(state)
        
        storage_time = time.time() - start_time
        final_result = result.get("result", {})
        
        if final_result.get("status") == "failed":
            task_logger.error(f"❌ Storage failed: {final_result.get('error')}")
            raise Exception(f"Storage failed: {final_result.get('error')}")
        
        task_logger.info(f"✅ Storage completed in {storage_time:.2f}s")
        task_logger.info(f"   📄 Document ID: {final_result.get('doc_uid', 'N/A')}")
        task_logger.info(f"   💾 Chunks stored: {final_result.get('chunks', 0)}")
        task_logger.info(f"   📊 Total items: {final_result.get('total_items', 0)}")
        
        return {
            "success": True,
            "doc_uid": final_result.get("doc_uid"),
            "chunks_stored": final_result.get("chunks", 0),
            "images_stored": final_result.get("images", 0),
            "total_items": final_result.get("total_items", 0),
            "storage_time": storage_time
        }
        
    except Exception as e:
        task_logger.error(f"❌ Storage failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "storage_time": time.time() - start_time
        }


@task(
    name="update_file_manager_status",
    description="Update file status in FileManager",
    tags=["database", "status"],
    retries=2,
    retry_delay_seconds=30
)
def update_file_manager_status(
    pdf_path: str,
    storage_result: Dict[str, Any],
    file_manager: FileManager,
    processing_time: float
) -> Dict[str, Any]:
    """
    Task: Update file status in FileManager database.
    
    Args:
        pdf_path: Path to processed file
        storage_result: Results from storage task
        file_manager: FileManager instance
        processing_time: Total processing time
        
    Returns:
        Status update results
    """
    task_logger = get_run_logger()
    task_logger.info(f"📋 Updating file status in database")
    
    try:
        if storage_result.get("success"):
            # Update to processed status
            processing_result_data = {
                'chunks_created': storage_result.get('chunks_stored', 0),
                'images_processed': storage_result.get('images_stored', 0),
                'processing_time': processing_time,
                'total_items': storage_result.get('total_items', 0)
            }
            
            file_manager.update_status(
                pdf_path,
                'processed',
                doc_uid=str(storage_result.get('doc_uid')) if storage_result.get('doc_uid') else None,
                processing_result=processing_result_data
            )
            
            task_logger.info(f"✅ File marked as processed")
            
        else:
            # Update to error status
            file_manager.update_status(
                pdf_path,
                'error',
                error_message=storage_result.get('error', 'Unknown error')
            )
            
            task_logger.error(f"❌ File marked as error")
        
        return {
            "success": True,
            "status": "processed" if storage_result.get("success") else "error"
        }
        
    except Exception as e:
        task_logger.error(f"❌ Failed to update file status: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@flow(
    name="process_single_document",
    description="Process a single document with fault tolerance and monitoring",
    version="1.0",
    task_runner=SequentialTaskRunner(),
    log_prints=True
)
async def process_single_document_flow(
    pdf_path: str,
    workflow: DocumentWorkflow,
    file_manager: FileManager
) -> ProcessingResult:
    """
    Prefect flow: Process a single document with enhanced error handling.
    
    Args:
        pdf_path: Path to PDF document
        workflow: DocumentWorkflow instance
        file_manager: FileManager instance
        
    Returns:
        ProcessingResult with comprehensive results
    """
    flow_logger = get_run_logger()
    flow_logger.info(f"🚀 Starting document processing flow for: {pdf_path}")
    
    flow_start_time = time.time()
    
    # Create processing artifact
    artifact_content = f"""
# Document Processing Report

**File:** `{pdf_path}`
**Started:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Flow Run:** {flow_logger.extra.get('flow_run_id', 'unknown')}

## Processing Steps
    """
    
    try:
        # Step 1: Extract content
        flow_logger.info("📋 Step 1: Extracting document content")
        extraction_result = await extract_document_content.submit(pdf_path, workflow)
        
        if not extraction_result.get("success"):
            raise Exception(f"Extraction failed: {extraction_result.get('error')}")
        
        artifact_content += f"""
### ✅ Content Extraction
- **Pages:** {extraction_result.get('total_text', 0):,} 
- **Text Characters:** {extraction_result.get('total_text', 0):,}
- **Images Found:** {extraction_result.get('total_images', 0)}
- **Time:** {extraction_result.get('extraction_time', 0):.2f}s
- **File Size:** {extraction_result.get('file_size_mb', 0):.2f} MB
        """
        
        # Step 2: Process and chunk
        flow_logger.info("📋 Step 2: Processing and chunking content")
        processing_result = await process_and_chunk_content.submit(
            extraction_result, pdf_path, workflow
        )
        
        if not processing_result.get("success"):
            raise Exception(f"Processing failed: {processing_result.get('error')}")
        
        artifact_content += f"""
### ✅ Content Processing & Chunking
- **Chunks Created:** {processing_result.get('chunk_count', 0)}
- **Time:** {processing_result.get('processing_time', 0):.2f}s
        """
        
        # Step 3: Embed and store
        flow_logger.info("📋 Step 3: Generating embeddings and storing")
        storage_result = await embed_and_store_content.submit(
            processing_result, pdf_path, workflow
        )
        
        if not storage_result.get("success"):
            raise Exception(f"Storage failed: {storage_result.get('error')}")
        
        artifact_content += f"""
### ✅ Embedding & Storage
- **Document ID:** `{storage_result.get('doc_uid', 'N/A')}`
- **Chunks Stored:** {storage_result.get('chunks_stored', 0)}
- **Images Stored:** {storage_result.get('images_stored', 0)}
- **Total Items:** {storage_result.get('total_items', 0)}
- **Time:** {storage_result.get('storage_time', 0):.2f}s
        """
        
        # Step 4: Update file manager
        flow_logger.info("📋 Step 4: Updating file status")
        total_processing_time = time.time() - flow_start_time
        
        status_update = await update_file_manager_status.submit(
            pdf_path, storage_result, file_manager, total_processing_time
        )
        
        artifact_content += f"""
### ✅ Status Update
- **Database Status:** {status_update.get('status', 'unknown')}
- **Total Processing Time:** {total_processing_time:.2f}s

## Final Results
- **Status:** ✅ Success
- **Chunks:** {storage_result.get('chunks_stored', 0)}
- **Images:** {storage_result.get('images_stored', 0)}
- **Document ID:** `{storage_result.get('doc_uid', 'N/A')}`
        """
        
        # Create success artifact
        await create_markdown_artifact(
            key=f"document-processing-{Path(pdf_path).stem}",
            markdown=artifact_content,
            description=f"Processing report for {Path(pdf_path).name}"
        )
        
        # Create success result
        result = ProcessingResult(
            file_path=pdf_path,
            success=True,
            doc_uid=storage_result.get('doc_uid'),
            chunks_created=storage_result.get('chunks_stored', 0),
            images_processed=storage_result.get('images_stored', 0),
            processing_time=total_processing_time,
            error_message=None,
            retry_count=0
        )
        
        flow_logger.info(f"✅ Document processing completed successfully in {total_processing_time:.2f}s")
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        total_processing_time = time.time() - flow_start_time
        
        flow_logger.error(f"❌ Document processing failed: {error_msg}")
        
        # Update error artifact
        artifact_content += f"""
## ❌ Processing Failed
- **Error:** {error_msg}
- **Total Time:** {total_processing_time:.2f}s
        """
        
        await create_markdown_artifact(
            key=f"document-processing-{Path(pdf_path).stem}-error",
            markdown=artifact_content,
            description=f"Error report for {Path(pdf_path).name}"
        )
        
        # Try to update file manager status to error
        try:
            file_manager.update_status(pdf_path, 'error', error_message=error_msg)
        except Exception as status_error:
            flow_logger.error(f"Failed to update error status: {status_error}")
        
        # Create error result
        result = ProcessingResult(
            file_path=pdf_path,
            success=False,
            doc_uid=None,
            chunks_created=0,
            images_processed=0,
            processing_time=total_processing_time,
            error_message=error_msg,
            retry_count=0
        )
        
        return result


@flow(
    name="process_vault_directory",
    description="Batch process all files in a vault directory",
    version="1.0",
    task_runner=SequentialTaskRunner(),
    log_prints=True
)
async def process_vault_directory_flow(
    vault_path: str,
    workflow: DocumentWorkflow,
    file_manager: FileManager,
    queue_manager: FileQueueManager,
    max_concurrent: int = 3
) -> BatchProcessingResult:
    """
    Prefect flow: Batch process vault directory with parallel execution.
    
    Args:
        vault_path: Path to vault directory
        workflow: DocumentWorkflow instance
        file_manager: FileManager instance
        queue_manager: FileQueueManager instance
        max_concurrent: Maximum concurrent document processing
        
    Returns:
        BatchProcessingResult with batch summary
    """
    flow_logger = get_run_logger()
    flow_logger.info(f"🗂️ Starting vault directory processing: {vault_path}")
    
    batch_start_time = time.time()
    batch_id = f"batch_{int(time.time())}"
    
    try:
        # Scan vault directory
        flow_logger.info("📂 Scanning vault directory for files")
        scan_result = await queue_manager.scan_vault_directory(vault_path)
        
        if not scan_result.get('success'):
            raise Exception(f"Vault scan failed: {scan_result.get('message', 'Unknown error')}")
        
        changes = scan_result.get('changes', {})
        files_to_process = (changes.get('new_files', []) + 
                          changes.get('modified_files', []))
        
        if not files_to_process:
            flow_logger.info("📁 No files to process")
            return BatchProcessingResult(
                batch_id=batch_id,
                vault_path=vault_path,
                total_files=0,
                successful_files=0,
                failed_files=0,
                processing_time=time.time() - batch_start_time,
                file_results=[]
            )
        
        flow_logger.info(f"📋 Processing {len(files_to_process)} files")
        
        # Create batch artifact
        batch_artifact = f"""
# Batch Processing Report

**Vault:** `{vault_path}`
**Batch ID:** `{batch_id}`
**Started:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Files to Process:** {len(files_to_process)}

## File List
{chr(10).join(f"- `{file}`" for file in files_to_process[:20])}
{"..." if len(files_to_process) > 20 else ""}

## Processing Progress
        """
        
        # Process files with limited concurrency
        file_results = []
        successful_files = 0
        failed_files = 0
        
        # Use semaphore to limit concurrent processing to protect GPU resources
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(file_path: str) -> ProcessingResult:
            async with semaphore:
                # Convert relative path to absolute
                if not Path(file_path).is_absolute():
                    full_path = str(Path(vault_path) / file_path)
                else:
                    full_path = file_path
                
                return await process_single_document_flow(full_path, workflow, file_manager)
        
        # Process all files concurrently (but limited by semaphore)
        results = await asyncio.gather(
            *[process_with_semaphore(file_path) for file_path in files_to_process],
            return_exceptions=True
        )
        
        # Process results
        for i, result in enumerate(results):
            file_path = files_to_process[i]
            
            if isinstance(result, Exception):
                flow_logger.error(f"❌ Exception processing {file_path}: {result}")
                failed_files += 1
                
                error_result = ProcessingResult(
                    file_path=file_path,
                    success=False,
                    doc_uid=None,
                    chunks_created=0,
                    images_processed=0,
                    processing_time=0.0,
                    error_message=str(result),
                    retry_count=0
                )
                file_results.append(error_result)
                
            else:
                file_results.append(result)
                if result.success:
                    successful_files += 1
                else:
                    failed_files += 1
        
        total_processing_time = time.time() - batch_start_time
        
        # Complete batch artifact
        batch_artifact += f"""
## Final Results
- **Total Files:** {len(files_to_process)}
- **Successful:** {successful_files}
- **Failed:** {failed_files}
- **Success Rate:** {successful_files / len(files_to_process) * 100:.1f}%
- **Total Processing Time:** {total_processing_time:.2f}s
- **Average Time per File:** {total_processing_time / len(files_to_process):.2f}s

### Successful Files
{chr(10).join(f"- ✅ `{r.file_path}` ({r.chunks_created} chunks)" for r in file_results if r.success)}

### Failed Files  
{chr(10).join(f"- ❌ `{r.file_path}` - {r.error_message}" for r in file_results if not r.success)}
        """
        
        await create_markdown_artifact(
            key=f"batch-processing-{batch_id}",
            markdown=batch_artifact,
            description=f"Batch processing report for {vault_path}"
        )
        
        batch_result = BatchProcessingResult(
            batch_id=batch_id,
            vault_path=vault_path,
            total_files=len(files_to_process),
            successful_files=successful_files,
            failed_files=failed_files,
            processing_time=total_processing_time,
            file_results=file_results
        )
        
        flow_logger.info(f"✅ Batch processing completed: {successful_files}/{len(files_to_process)} successful")
        
        return batch_result
        
    except Exception as e:
        error_msg = str(e)
        total_processing_time = time.time() - batch_start_time
        
        flow_logger.error(f"❌ Batch processing failed: {error_msg}")
        
        return BatchProcessingResult(
            batch_id=batch_id,
            vault_path=vault_path,
            total_files=0,
            successful_files=0,
            failed_files=1,
            processing_time=total_processing_time,
            file_results=[ProcessingResult(
                file_path=vault_path,
                success=False,
                doc_uid=None,
                chunks_created=0,
                images_processed=0,
                processing_time=total_processing_time,
                error_message=error_msg,
                retry_count=0
            )]
        )


class PrefectDocumentProcessor:
    """
    Prefect-enhanced document processing service.
    
    Provides the same interface as DocumentProcessingService but uses
    Prefect flows for enhanced monitoring, error handling, and scheduling.
    """
    
    def __init__(self,
                 document_workflow: DocumentWorkflow,
                 file_manager: FileManager,
                 queue_manager: FileQueueManager = None):
        
        self.document_workflow = document_workflow
        self.file_manager = file_manager
        self.queue_manager = queue_manager
        
        logger.info("✅ PrefectDocumentProcessor initialized")
    
    async def process_file(self, file_path: str) -> ProcessingResult:
        """
        Process single file using Prefect flow.
        
        Args:
            file_path: Path to file to process
            
        Returns:
            ProcessingResult
        """
        logger.info(f"🚀 Processing file with Prefect: {file_path}")
        
        return await process_single_document_flow(
            file_path, 
            self.document_workflow,
            self.file_manager
        )
    
    async def process_vault_directory(self, 
                                    vault_path: str, 
                                    max_concurrent: int = 2) -> BatchProcessingResult:
        """
        Process vault directory using Prefect flow.
        
        Args:
            vault_path: Path to vault directory
            max_concurrent: Maximum concurrent processing (limited for GPU)
            
        Returns:
            BatchProcessingResult
        """
        logger.info(f"🗂️ Processing vault directory with Prefect: {vault_path}")
        
        return await process_vault_directory_flow(
            vault_path,
            self.document_workflow,
            self.file_manager,
            self.queue_manager,
            max_concurrent
        )


# Global Prefect processor instance
prefect_processor = None

def get_prefect_document_processor() -> PrefectDocumentProcessor:
    """Get or create the global Prefect document processor."""
    global prefect_processor
    
    if prefect_processor is None:
        raise Exception("PrefectDocumentProcessor not initialized - call initialize_prefect_processor first")
    
    return prefect_processor

def initialize_prefect_document_processor(
    document_workflow: DocumentWorkflow,
    file_manager: FileManager,
    queue_manager: FileQueueManager = None
) -> PrefectDocumentProcessor:
    """Initialize the global Prefect document processor."""
    global prefect_processor
    
    prefect_processor = PrefectDocumentProcessor(
        document_workflow=document_workflow,
        file_manager=file_manager,
        queue_manager=queue_manager
    )
    
    logger.info("✅ PrefectDocumentProcessor initialized")
    return prefect_processor