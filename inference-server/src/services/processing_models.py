"""
Data models and types for document processing service.

Defines the data structures used throughout the document processing pipeline
for status tracking, progress reporting, and result management.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime


class ProcessingStatus(Enum):
    """Processing status enum for document workflow tracking."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class ProcessingStep(Enum):
    """Individual steps in the document processing workflow."""
    EXTRACTING = "extracting"
    PROCESSING_IMAGES = "processing_images"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    STORING = "storing"


@dataclass
class ProcessingProgress:
    """Real-time processing progress information."""
    status: ProcessingStatus
    current_step: Optional[ProcessingStep]
    progress_percentage: int  # 0-100
    estimated_time_remaining: Optional[int]  # seconds
    step_details: Optional[str]  # Additional step-specific info
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "current_step": self.current_step.value if self.current_step else None,
            "progress_percentage": self.progress_percentage,
            "estimated_time_remaining": self.estimated_time_remaining,
            "step_details": self.step_details
        }


@dataclass
class ProcessingResult:
    """Result of document processing operation."""
    file_path: str
    success: bool
    doc_uid: Optional[str]  # Document ID if successful
    chunks_created: int
    images_processed: int
    processing_time: float  # seconds
    error_message: Optional[str]
    retry_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "success": self.success,
            "doc_uid": str(self.doc_uid) if self.doc_uid else None,
            "chunks_created": self.chunks_created,
            "images_processed": self.images_processed,
            "processing_time": self.processing_time,
            "error_message": self.error_message,
            "retry_count": self.retry_count
        }


@dataclass
class BatchProcessingResult:
    """Result of batch vault processing operation."""
    batch_id: str
    vault_path: str
    total_files: int
    successful_files: int
    failed_files: int
    processing_time: float
    file_results: List[ProcessingResult]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "vault_path": self.vault_path,
            "total_files": self.total_files,
            "successful_files": self.successful_files,
            "failed_files": self.failed_files,
            "processing_time": self.processing_time,
            "success_rate": self.successful_files / max(self.total_files, 1),
            "file_results": [result.to_dict() for result in self.file_results]
        }


@dataclass
class ProcessingJobInfo:
    """Information about a processing job for tracking."""
    job_id: str
    file_path: str
    queued_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    progress: ProcessingProgress
    retry_count: int = 0
    max_retries: int = 3
    
    @property
    def is_expired(self) -> bool:
        """Check if job has been queued too long (>1 hour)."""
        if not self.started_at and self.queued_at:
            return (datetime.now() - self.queued_at).total_seconds() > 3600
        return False
    
    @property
    def should_retry(self) -> bool:
        """Check if job should be retried after failure."""
        return self.retry_count < self.max_retries
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "file_path": self.file_path,
            "queued_at": self.queued_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.progress.to_dict(),
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "is_expired": self.is_expired,
            "should_retry": self.should_retry
        }


@dataclass
class QueueStatus:
    """Overall processing queue status."""
    total_queued: int
    processing: int
    completed_today: int
    failed_today: int
    worker_active: bool
    average_processing_time: float  # seconds
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_queued": self.total_queued,
            "processing": self.processing,
            "completed_today": self.completed_today,
            "failed_today": self.failed_today,
            "worker_active": self.worker_active,
            "average_processing_time": self.average_processing_time,
            "queue_health": "healthy" if self.worker_active and self.total_queued < 100 else "warning"
        }


class ProcessingException(Exception):
    """Custom exception for document processing errors."""
    
    def __init__(self, message: str, file_path: str, step: Optional[ProcessingStep] = None, retry_count: int = 0):
        super().__init__(message)
        self.file_path = file_path
        self.step = step
        self.retry_count = retry_count
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": str(self),
            "file_path": self.file_path,
            "step": self.step.value if self.step else None,
            "retry_count": self.retry_count,
            "timestamp": self.timestamp.isoformat()
        }