"""
Unified Document Processing API Routes

Provides clean, unified endpoints for document processing using the
DocumentProcessingService. Simplifies document workflow management
and provides real-time status tracking.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import tempfile
import os
import logging

from src.services.document_processing_service import get_document_processing_service
from src.services.processing_models import ProcessingResult, BatchProcessingResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

# Request/Response Models
class ProcessFileRequest(BaseModel):
    file_path: str
    priority: Optional[bool] = False

class ProcessVaultRequest(BaseModel):
    vault_path: str
    force_reprocess: Optional[bool] = False

class ProcessingStatusResponse(BaseModel):
    job_id: str
    status: str
    progress_percentage: int
    current_step: Optional[str]
    estimated_time_remaining: Optional[int]
    step_details: Optional[str]
    file_path: str

class QueueStatusResponse(BaseModel):
    total_queued: int
    processing: int
    completed_today: int
    failed_today: int
    worker_active: bool
    average_processing_time: float
    queue_health: str


@router.post("/upload-and-process")
async def upload_and_process_file(
    file: UploadFile = File(...),
    priority: bool = Form(False)
):
    """
    Upload a file and process it immediately.
    
    This is the simplest endpoint - upload a file and get it processed
    through the complete workflow in one API call.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Validate file type
    allowed_extensions = {'.pdf', '.txt', '.md', '.docx'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type: {file_ext}. Allowed: {', '.join(allowed_extensions)}"
        )
    
    processing_service = get_document_processing_service()
    
    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        logger.info(f"📤 Uploaded file saved to: {tmp_file_path}")
        
        # Process the file
        result = await processing_service.process_file(tmp_file_path)
        
        # Clean up temporary file
        try:
            os.unlink(tmp_file_path)
        except:
            pass  # Ignore cleanup errors
        
        return {
            "message": "File uploaded and processed",
            "original_filename": file.filename,
            "result": result.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Error in upload-and-process: {e}")
        
        # Clean up temporary file on error
        try:
            if 'tmp_file_path' in locals():
                os.unlink(tmp_file_path)
        except:
            pass
        
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.post("/process-file")
async def process_single_file(request: ProcessFileRequest):
    """
    Process a single file by file path.
    
    Use this when you have a file already on the server filesystem
    that you want to process through the document workflow.
    """
    processing_service = get_document_processing_service()
    
    try:
        # Validate file exists
        if not os.path.exists(request.file_path):
            raise HTTPException(status_code=404, detail=f"File not found: {request.file_path}")
        
        # Process the file
        result = await processing_service.process_file(request.file_path)
        
        return {
            "message": f"File processing {'completed' if result.success else 'failed'}",
            "result": result.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing file {request.file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.post("/process-vault")
async def process_vault_directory(request: ProcessVaultRequest):
    """
    Process all files in a vault directory.
    
    Scans the vault directory for supported files and processes them
    through the complete document workflow. Returns batch results.
    """
    processing_service = get_document_processing_service()
    
    try:
        # Validate vault path exists
        if not os.path.exists(request.vault_path):
            raise HTTPException(status_code=404, detail=f"Vault path not found: {request.vault_path}")
        
        if not os.path.isdir(request.vault_path):
            raise HTTPException(status_code=400, detail=f"Path is not a directory: {request.vault_path}")
        
        # Process vault directory
        batch_result = await processing_service.process_vault_directory(request.vault_path)
        
        return {
            "message": f"Vault processing completed: {batch_result.successful_files}/{batch_result.total_files} files processed successfully",
            "result": batch_result.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing vault {request.vault_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Vault processing failed: {str(e)}")


@router.get("/status/{job_id}")
async def get_processing_status(job_id: str):
    """
    Get real-time processing status for a specific job.
    
    Returns detailed information about job progress, current step,
    and estimated time remaining.
    """
    processing_service = get_document_processing_service()
    
    status = processing_service.get_processing_status(job_id)
    
    if not status:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    
    return status


@router.get("/queue-status")
async def get_queue_status():
    """
    Get overall processing queue status.
    
    Returns information about queue health, processing statistics,
    and system performance metrics.
    """
    processing_service = get_document_processing_service()
    
    queue_status = processing_service.get_queue_status()
    
    return queue_status.to_dict()


@router.get("/health")
async def get_service_health():
    """
    Check document processing service health.
    
    Returns basic health information about the document processing
    components and their status.
    """
    processing_service = get_document_processing_service()
    
    try:
        # Check if core components are available
        has_workflow = processing_service.document_workflow is not None
        has_file_manager = processing_service.file_manager is not None
        has_queue_manager = processing_service.queue_manager is not None
        
        # Get queue status for additional health info
        queue_status = processing_service.get_queue_status()
        
        overall_health = "healthy" if (has_workflow and has_file_manager and has_queue_manager) else "unhealthy"
        
        return {
            "status": overall_health,
            "components": {
                "document_workflow": "available" if has_workflow else "not_available",
                "file_manager": "available" if has_file_manager else "not_available",
                "queue_manager": "available" if has_queue_manager else "not_available"
            },
            "queue_info": {
                "total_queued": queue_status.total_queued,
                "processing": queue_status.processing,
                "worker_active": queue_status.worker_active
            },
            "service_info": {
                "active_jobs": len(processing_service.active_jobs),
                "completed_jobs": len(processing_service.completed_jobs)
            }
        }
        
    except Exception as e:
        logger.error(f"Error checking service health: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@router.post("/cleanup")
async def cleanup_old_jobs(
    max_age_hours: int = Query(24, ge=1, le=168, description="Maximum age of jobs to keep (1-168 hours)")
):
    """
    Clean up old completed jobs.
    
    Removes old completed jobs from memory to prevent memory bloat.
    Only affects in-memory job tracking, not database records.
    """
    processing_service = get_document_processing_service()
    
    try:
        jobs_before = len(processing_service.completed_jobs)
        processing_service.cleanup_old_jobs(max_age_hours)
        jobs_after = len(processing_service.completed_jobs)
        
        cleaned_count = jobs_before - jobs_after
        
        return {
            "message": f"Cleanup completed: removed {cleaned_count} old jobs",
            "jobs_before": jobs_before,
            "jobs_after": jobs_after,
            "max_age_hours": max_age_hours
        }
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


# Add some utility endpoints for debugging/monitoring

@router.get("/files/by-status")
async def get_files_by_status(
    status: str = Query(..., description="File processing status to filter by"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of files to return")
):
    """Get files by processing status (for debugging/monitoring)."""
    processing_service = get_document_processing_service()
    
    try:
        files = processing_service.file_manager.get_files_by_status(status)
        
        # Limit results and convert to dict
        limited_files = files[:limit]
        
        return {
            "status": status,
            "total_count": len(files),
            "returned_count": len(limited_files),
            "files": [
                {
                    "file_id": str(file.file_id),
                    "vault_path": file.vault_path,
                    "file_type": file.file_type,
                    "file_size": file.file_size,
                    "processing_status": file.processing_status,
                    "doc_uid": str(file.doc_uid) if file.doc_uid else None,
                    "error_message": file.error_message,
                    "modified_at": file.modified_at.isoformat() if file.modified_at else None,
                    "updated_at": file.updated_at.isoformat() if file.updated_at else None
                }
                for file in limited_files
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting files by status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get files: {str(e)}")


@router.get("/stats")
async def get_processing_stats():
    """Get processing statistics and performance metrics."""
    processing_service = get_document_processing_service()
    
    try:
        # File counts by status
        file_stats = {}
        for status in ['unprocessed', 'queued', 'processing', 'processed', 'error']:
            file_stats[status] = processing_service.file_manager.get_file_count(status)
        
        # Job stats
        job_stats = {
            "active_jobs": len(processing_service.active_jobs),
            "completed_jobs": len(processing_service.completed_jobs)
        }
        
        # Queue status
        queue_status = processing_service.get_queue_status()
        
        return {
            "file_stats": file_stats,
            "job_stats": job_stats,
            "queue_stats": queue_status.to_dict(),
            "total_files": sum(file_stats.values())
        }
        
    except Exception as e:
        logger.error(f"Error getting processing stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/processing-metrics")
async def get_processing_metrics():
    """Get detailed processing performance metrics."""
    processing_service = get_document_processing_service()
    
    try:
        # Get files with processing times
        processed_files = processing_service.file_manager.get_files_by_status('processed')
        failed_files = processing_service.file_manager.get_files_by_status('error')
        
        # Calculate performance metrics
        processing_times = [f.processing_time_seconds for f in processed_files if f.processing_time_seconds]
        chunks_created = [f.chunks_created for f in processed_files if f.chunks_created]
        images_processed = [f.images_processed for f in processed_files if f.images_processed]
        retry_counts = [f.retry_count for f in failed_files if f.retry_count]
        
        metrics = {
            "processing_performance": {
                "total_processed": len(processed_files),
                "total_failed": len(failed_files),
                "avg_processing_time_seconds": sum(processing_times) / len(processing_times) if processing_times else 0,
                "min_processing_time_seconds": min(processing_times) if processing_times else 0,
                "max_processing_time_seconds": max(processing_times) if processing_times else 0
            },
            "content_metrics": {
                "total_chunks_created": sum(chunks_created) if chunks_created else 0,
                "avg_chunks_per_file": sum(chunks_created) / len(chunks_created) if chunks_created else 0,
                "total_images_processed": sum(images_processed) if images_processed else 0,
                "avg_images_per_file": sum(images_processed) / len(images_processed) if images_processed else 0
            },
            "error_metrics": {
                "total_retries": sum(retry_counts) if retry_counts else 0,
                "avg_retries_per_failed_file": sum(retry_counts) / len(retry_counts) if retry_counts else 0,
                "files_with_retries": len([r for r in retry_counts if r > 0])
            }
        }
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error getting processing metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.get("/processing-history")
async def get_processing_history(
    hours: int = Query(24, ge=1, le=168, description="Hours of history to retrieve"),
    status: Optional[str] = Query(None, description="Filter by processing status")
):
    """Get processing history for the specified time period."""
    processing_service = get_document_processing_service()
    
    try:
        from datetime import datetime, timedelta
        
        # Calculate cutoff time
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Get files processed in the time period
        with processing_service.file_manager.db.session() as session:
            from src.database.models import VaultFile
            
            query = session.query(VaultFile).filter(
                VaultFile.processing_completed_at >= cutoff_time
            )
            
            if status:
                query = query.filter(VaultFile.processing_status == status)
            
            files = query.order_by(VaultFile.processing_completed_at.desc()).all()
        
        history_data = []
        for file in files:
            history_data.append({
                "file_path": file.vault_path,
                "status": file.processing_status,
                "started_at": file.processing_started_at.isoformat() if file.processing_started_at else None,
                "completed_at": file.processing_completed_at.isoformat() if file.processing_completed_at else None,
                "processing_time_seconds": file.processing_time_seconds,
                "chunks_created": file.chunks_created,
                "images_processed": file.images_processed,
                "retry_count": file.retry_count,
                "error_message": file.error_message,
                "doc_uid": str(file.doc_uid) if file.doc_uid else None
            })
        
        return {
            "time_period_hours": hours,
            "filter_status": status,
            "total_files": len(history_data),
            "history": history_data
        }
        
    except Exception as e:
        logger.error(f"Error getting processing history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")


@router.post("/background-worker/start")
async def start_background_worker():
    """Start the background processing worker."""
    from src.services.background_processor import start_background_processor
    
    try:
        processing_service = get_document_processing_service()
        worker = start_background_processor(processing_service)
        
        return {
            "message": "Background worker started successfully",
            "status": worker.get_status()
        }
        
    except Exception as e:
        logger.error(f"Error starting background worker: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start worker: {str(e)}")


@router.post("/background-worker/stop")
async def stop_background_worker():
    """Stop the background processing worker."""
    from src.services.background_processor import stop_background_processor
    
    try:
        stop_background_processor()
        
        return {"message": "Background worker stopped successfully"}
        
    except Exception as e:
        logger.error(f"Error stopping background worker: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop worker: {str(e)}")


@router.get("/background-worker/status")
async def get_background_worker_status():
    """Get background worker status and statistics."""
    from src.services.background_processor import get_background_processor
    
    try:
        worker = get_background_processor()
        
        if not worker:
            return {
                "status": "not_initialized",
                "message": "Background worker has not been started"
            }
        
        return worker.get_status()
        
    except Exception as e:
        logger.error(f"Error getting background worker status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")