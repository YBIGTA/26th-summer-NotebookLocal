"""
DocumentProcessingService - Orchestration layer around existing DocumentWorkflow.

Provides unified interface for document processing while leveraging the existing
DocumentWorkflow class that already handles the complete processing pipeline.
"""

import asyncio
import logging
import uuid
import time
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

from .processing_models import (
    ProcessingStatus, ProcessingStep, ProcessingProgress, ProcessingResult,
    BatchProcessingResult, ProcessingJobInfo, QueueStatus, ProcessingException
)
from ..database.file_manager import FileManager, file_manager
from ..vault.file_queue_manager import FileQueueManager
from ..workflows.document_workflow import DocumentWorkflow
from ..storage.hybrid_store import HybridStore
from ..processors.embedder import Embedder
from ..llm.core.router import LLMRouter

logger = logging.getLogger(__name__)


class DocumentProcessingService:
    """
    Orchestration service that wraps the existing DocumentWorkflow.
    
    Provides:
    - Job tracking and status management
    - Batch processing capabilities  
    - Error handling and retries
    - Real-time progress reporting
    - Integration with FileManager
    """
    
    def __init__(self,
                 document_workflow: DocumentWorkflow = None,
                 file_manager: FileManager = None,
                 queue_manager: FileQueueManager = None):
        
        self.document_workflow = document_workflow
        self.file_manager = file_manager or file_manager
        self.queue_manager = queue_manager or FileQueueManager(self.file_manager)
        
        # Job tracking
        self.active_jobs: Dict[str, ProcessingJobInfo] = {}
        self.completed_jobs: Dict[str, ProcessingJobInfo] = {}
        
        logger.info("✅ DocumentProcessingService initialized")
    
    async def process_file(self, file_path: str) -> ProcessingResult:
        """
        Process a single file using the existing DocumentWorkflow.
        
        Args:
            file_path: Absolute path to the file to process
            
        Returns:
            ProcessingResult with processing details
        """
        if not self.document_workflow:
            raise ProcessingException("DocumentWorkflow not initialized", file_path)
        
        job_id = str(uuid.uuid4())
        start_time = time.time()
        
        logger.info(f"🚀 Processing file: {file_path} (job: {job_id})")
        
        # Create job tracking
        progress = ProcessingProgress(
            status=ProcessingStatus.QUEUED,
            current_step=ProcessingStep.EXTRACTING,
            progress_percentage=0,
            estimated_time_remaining=None,
            step_details="Starting document processing workflow"
        )
        
        job_info = ProcessingJobInfo(
            job_id=job_id,
            file_path=file_path,
            queued_at=datetime.now(),
            started_at=datetime.now(),
            completed_at=None,
            progress=progress
        )
        
        self.active_jobs[job_id] = job_info
        
        try:
            # Add/update file in FileManager
            vault_file = self.file_manager.get_file(file_path)
            if not vault_file:
                # Get file stats
                file_path_obj = Path(file_path)
                if file_path_obj.exists():
                    stat = file_path_obj.stat()
                    file_size = stat.st_size
                    modified_at = datetime.fromtimestamp(stat.st_mtime)
                else:
                    file_size = 0
                    modified_at = datetime.now()
                
                vault_file = self.file_manager.add_file(
                    path=file_path,
                    file_size=file_size,
                    modified_at=modified_at
                )
            
            # Update status to processing
            self.file_manager.update_status(file_path, 'processing')
            job_info.progress.status = ProcessingStatus.PROCESSING
            job_info.progress.progress_percentage = 10
            
            # Use the existing DocumentWorkflow - it handles everything!
            logger.info(f"📋 Running DocumentWorkflow for: {file_path}")
            workflow_result = await self.document_workflow.run(file_path)
            
            # Parse workflow result
            success = workflow_result.get('status') != 'failed'
            doc_uid = workflow_result.get('doc_uid')
            chunks_created = workflow_result.get('chunks', 0)
            images_processed = workflow_result.get('images', 0)
            error_message = workflow_result.get('error')
            
            processing_time = time.time() - start_time
            
            if success:
                # Update file status to processed with enhanced tracking
                processing_result_data = {
                    'chunks_created': chunks_created,
                    'images_processed': images_processed,
                    'processing_time': processing_time
                }
                
                self.file_manager.update_status(
                    file_path, 
                    'processed',
                    doc_uid=str(doc_uid) if doc_uid else None,
                    processing_result=processing_result_data
                )
                
                # Update job progress
                job_info.progress.status = ProcessingStatus.COMPLETED
                job_info.progress.progress_percentage = 100
                job_info.progress.step_details = "Processing completed successfully"
                job_info.completed_at = datetime.now()
                
                logger.info(f"✅ Successfully processed {file_path} in {processing_time:.2f}s")
                
            else:
                # Update file status to error
                self.file_manager.update_status(
                    file_path, 
                    'error',
                    error_message=error_message
                )
                
                # Update job progress
                job_info.progress.status = ProcessingStatus.FAILED
                job_info.progress.step_details = error_message or "Processing failed"
                job_info.completed_at = datetime.now()
                
                logger.error(f"❌ Failed to process {file_path}: {error_message}")
            
            # Create result
            result = ProcessingResult(
                file_path=file_path,
                success=success,
                doc_uid=doc_uid,
                chunks_created=chunks_created,
                images_processed=images_processed,
                processing_time=processing_time,
                error_message=error_message,
                retry_count=job_info.retry_count
            )
            
            # Move to completed jobs
            self.completed_jobs[job_id] = self.active_jobs.pop(job_id)
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = str(e)
            
            logger.error(f"❌ Exception processing {file_path}: {error_msg}")
            
            # Update file and job status
            self.file_manager.update_status(file_path, 'error', error_message=error_msg)
            
            job_info.progress.status = ProcessingStatus.FAILED
            job_info.progress.step_details = error_msg
            job_info.completed_at = datetime.now()
            
            result = ProcessingResult(
                file_path=file_path,
                success=False,
                doc_uid=None,
                chunks_created=0,
                images_processed=0,
                processing_time=processing_time,
                error_message=error_msg,
                retry_count=job_info.retry_count
            )
            
            # Move to completed jobs
            self.completed_jobs[job_id] = self.active_jobs.pop(job_id)
            
            return result
    
    async def process_vault_directory(self, vault_path: str) -> BatchProcessingResult:
        """
        Process all files in a vault directory.
        
        Args:
            vault_path: Path to vault directory to scan and process
            
        Returns:
            BatchProcessingResult with batch processing summary
        """
        batch_id = str(uuid.uuid4())
        start_time = time.time()
        
        logger.info(f"🗂️ Starting batch processing for: {vault_path} (batch: {batch_id})")
        
        try:
            # Scan vault directory using existing queue manager
            scan_result = await self.queue_manager.scan_vault_directory(vault_path)
            
            if not scan_result.get('success'):
                raise Exception(f"Vault scan failed: {scan_result.get('message', 'Unknown error')}")
            
            changes = scan_result.get('changes', {})
            files_to_process = (changes.get('new_files', []) + 
                              changes.get('modified_files', []))
            
            if not files_to_process:
                logger.info(f"📁 No files to process in: {vault_path}")
                return BatchProcessingResult(
                    batch_id=batch_id,
                    vault_path=vault_path,
                    total_files=0,
                    successful_files=0,
                    failed_files=0,
                    processing_time=time.time() - start_time,
                    file_results=[]
                )
            
            logger.info(f"📋 Processing {len(files_to_process)} files from vault scan")
            
            # Process each file
            file_results = []
            successful_files = 0
            failed_files = 0
            
            for i, file_path in enumerate(files_to_process, 1):
                logger.info(f"🔄 Processing file {i}/{len(files_to_process)}: {file_path}")
                
                # Convert relative path to absolute if needed
                if not Path(file_path).is_absolute():
                    full_path = str(Path(vault_path) / file_path)
                else:
                    full_path = file_path
                
                try:
                    result = await self.process_file(full_path)
                    file_results.append(result)
                    
                    if result.success:
                        successful_files += 1
                    else:
                        failed_files += 1
                        
                except Exception as e:
                    logger.error(f"❌ Error processing {file_path}: {e}")
                    failed_files += 1
                    
                    error_result = ProcessingResult(
                        file_path=full_path,
                        success=False,
                        doc_uid=None,
                        chunks_created=0,
                        images_processed=0,
                        processing_time=0.0,
                        error_message=str(e),
                        retry_count=0
                    )
                    file_results.append(error_result)
            
            processing_time = time.time() - start_time
            
            batch_result = BatchProcessingResult(
                batch_id=batch_id,
                vault_path=vault_path,
                total_files=len(files_to_process),
                successful_files=successful_files,
                failed_files=failed_files,
                processing_time=processing_time,
                file_results=file_results
            )
            
            logger.info(f"✅ Batch processing completed: {successful_files}/{len(files_to_process)} successful in {processing_time:.2f}s")
            
            return batch_result
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = str(e)
            
            logger.error(f"❌ Batch processing failed for {vault_path}: {error_msg}")
            
            return BatchProcessingResult(
                batch_id=batch_id,
                vault_path=vault_path,
                total_files=0,
                successful_files=0,
                failed_files=1,
                processing_time=processing_time,
                file_results=[ProcessingResult(
                    file_path=vault_path,
                    success=False,
                    doc_uid=None,
                    chunks_created=0,
                    images_processed=0,
                    processing_time=processing_time,
                    error_message=error_msg,
                    retry_count=0
                )]
            )
    
    def get_processing_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get real-time processing status for a job."""
        if job_id in self.active_jobs:
            return self.active_jobs[job_id].to_dict()
        
        if job_id in self.completed_jobs:
            return self.completed_jobs[job_id].to_dict()
        
        return None
    
    def get_queue_status(self) -> QueueStatus:
        """Get overall processing queue status."""
        try:
            total_queued = self.file_manager.get_file_count('queued')
            processing = len(self.active_jobs)
            
            # Today's stats
            completed_today = len([job for job in self.completed_jobs.values()
                                 if job.completed_at and 
                                 job.completed_at.date() == datetime.now().date()])
            
            failed_today = len([job for job in self.completed_jobs.values()
                               if job.completed_at and 
                               job.completed_at.date() == datetime.now().date() and
                               job.progress.status == ProcessingStatus.FAILED])
            
            # Average processing time
            recent_jobs = [job for job in self.completed_jobs.values()
                          if job.started_at and job.completed_at]
            
            if recent_jobs:
                avg_time = sum(
                    (job.completed_at - job.started_at).total_seconds()
                    for job in recent_jobs
                ) / len(recent_jobs)
            else:
                avg_time = 0.0
            
            return QueueStatus(
                total_queued=total_queued,
                processing=processing,
                completed_today=completed_today,
                failed_today=failed_today,
                worker_active=True,  # Service is active if it exists
                average_processing_time=avg_time
            )
            
        except Exception as e:
            logger.error(f"Error getting queue status: {e}")
            return QueueStatus(
                total_queued=0,
                processing=0,
                completed_today=0,
                failed_today=0,
                worker_active=False,
                average_processing_time=0.0
            )
    
    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Clean up old completed jobs to prevent memory bloat."""
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        
        old_jobs = [
            job_id for job_id, job in self.completed_jobs.items()
            if job.completed_at and job.completed_at.timestamp() < cutoff_time
        ]
        
        for job_id in old_jobs:
            del self.completed_jobs[job_id]
        
        if old_jobs:
            logger.info(f"🧹 Cleaned up {len(old_jobs)} old completed jobs")


# Global service instance  
document_processing_service = None

def get_document_processing_service() -> DocumentProcessingService:
    """Get or create the global document processing service instance."""
    global document_processing_service
    
    if document_processing_service is None:
        document_processing_service = DocumentProcessingService()
    
    return document_processing_service

def initialize_document_processing_service(
    document_workflow: DocumentWorkflow,
    file_manager: FileManager = None,
    queue_manager: FileQueueManager = None
) -> DocumentProcessingService:
    """Initialize the global document processing service with proper dependencies."""
    global document_processing_service
    
    document_processing_service = DocumentProcessingService(
        document_workflow=document_workflow,
        file_manager=file_manager,
        queue_manager=queue_manager
    )
    
    logger.info("✅ DocumentProcessingService initialized with full dependencies")
    return document_processing_service