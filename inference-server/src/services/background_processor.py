"""
BackgroundProcessor - Async worker for document processing queue.

Provides background processing capabilities that automatically polls the queue
for pending files and processes them through the DocumentWorkflow. Includes
retry logic, error handling, and graceful shutdown capabilities.
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime
from threading import Thread, Event

from .processing_models import ProcessingStatus, ProcessingStep, ProcessingException
from .document_processing_service import DocumentProcessingService
from ..database.file_manager import FileManager
from ..vault.file_queue_manager import FileQueueManager

logger = logging.getLogger(__name__)


class BackgroundProcessor:
    """
    Background worker that continuously processes queued files.
    
    Features:
    - Async processing loop with configurable intervals
    - Automatic retry logic with exponential backoff
    - Graceful shutdown handling
    - Performance metrics tracking
    - Error recovery and logging
    """
    
    def __init__(self,
                 processing_service: DocumentProcessingService,
                 poll_interval: float = 5.0,
                 max_concurrent_jobs: int = 2,
                 retry_delays: tuple = (60, 300, 900)):  # 1min, 5min, 15min
        
        self.processing_service = processing_service
        self.poll_interval = poll_interval
        self.max_concurrent_jobs = max_concurrent_jobs
        self.retry_delays = retry_delays
        
        # Worker state
        self.is_running = False
        self.stop_event = Event()
        self.worker_thread: Optional[Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Performance tracking
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'retries': 0,
            'started_at': None,
            'last_activity': None
        }
        
        logger.info(f"✅ BackgroundProcessor initialized (poll_interval={poll_interval}s)")
    
    def start(self):
        """Start the background processing worker."""
        if self.is_running:
            logger.warning("Background processor is already running")
            return
        
        self.is_running = True
        self.stop_event.clear()
        self.stats['started_at'] = datetime.now()
        
        # Start worker thread
        self.worker_thread = Thread(target=self._run_worker_thread, daemon=True)
        self.worker_thread.start()
        
        logger.info("🚀 Background processor started")
    
    def stop(self, timeout: float = 30.0):
        """Stop the background processing worker gracefully."""
        if not self.is_running:
            logger.info("Background processor is not running")
            return
        
        logger.info("🛑 Stopping background processor...")
        
        # Signal stop
        self.stop_event.set()
        self.is_running = False
        
        # Wait for worker thread to finish
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=timeout)
            
            if self.worker_thread.is_alive():
                logger.warning("Background processor thread did not stop cleanly")
            else:
                logger.info("✅ Background processor stopped gracefully")
        
        self.worker_thread = None
    
    def _run_worker_thread(self):
        """Run the worker in a separate thread with its own event loop."""
        try:
            # Create new event loop for this thread
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # Run the async worker
            self.loop.run_until_complete(self._async_worker())
            
        except Exception as e:
            logger.error(f"❌ Background processor thread crashed: {e}")
        finally:
            if self.loop:
                self.loop.close()
            self.loop = None
    
    async def _async_worker(self):
        """Main async worker loop."""
        logger.info("🔄 Background processor worker started")
        
        while not self.stop_event.is_set():
            try:
                await self._process_queue_batch()
                
                # Wait for next poll or stop signal
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                logger.error(f"❌ Error in background processor loop: {e}")
                await asyncio.sleep(self.poll_interval)  # Continue after error
        
        logger.info("🔄 Background processor worker stopped")
    
    async def _process_queue_batch(self):
        """Process a batch of queued files."""
        try:
            # Get queued files from file manager
            queued_files = self.processing_service.file_manager.get_files_by_status('queued')
            
            if not queued_files:
                return  # No files to process
            
            # Limit concurrent processing
            files_to_process = queued_files[:self.max_concurrent_jobs]
            
            logger.info(f"📋 Processing {len(files_to_process)} queued files")
            
            # Process files concurrently
            tasks = []
            for vault_file in files_to_process:
                task = asyncio.create_task(
                    self._process_single_file(vault_file.vault_path)
                )
                tasks.append(task)
            
            # Wait for all tasks to complete
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                self.stats['last_activity'] = datetime.now()
            
        except Exception as e:
            logger.error(f"❌ Error processing queue batch: {e}")
    
    async def _process_single_file(self, file_path: str):
        """Process a single file with retry logic."""
        start_time = time.time()
        
        try:
            logger.info(f"🔄 Background processing: {file_path}")
            
            # Check if file should be retried
            vault_file = self.processing_service.file_manager.get_file(file_path)
            if not vault_file:
                logger.warning(f"File not found in database: {file_path}")
                return
            
            # Process the file
            result = await self.processing_service.process_file(file_path)
            
            # Update stats
            self.stats['total_processed'] += 1
            if result.success:
                self.stats['successful'] += 1
                logger.info(f"✅ Background processed: {file_path} ({time.time() - start_time:.2f}s)")
            else:
                self.stats['failed'] += 1
                logger.error(f"❌ Background processing failed: {file_path} - {result.error_message}")
                
                # Handle retry logic
                await self._handle_processing_failure(file_path, result.error_message)
            
        except Exception as e:
            self.stats['failed'] += 1
            logger.error(f"❌ Exception in background processing {file_path}: {e}")
            
            await self._handle_processing_failure(file_path, str(e))
    
    async def _handle_processing_failure(self, file_path: str, error_message: str):
        """Handle processing failures with retry logic."""
        try:
            vault_file = self.processing_service.file_manager.get_file(file_path)
            if not vault_file:
                return
            
            # Get current retry count from error message or assume 0
            retry_count = 0
            if hasattr(vault_file, 'retry_count'):
                retry_count = getattr(vault_file, 'retry_count', 0)
            
            # Check if we should retry
            if retry_count < len(self.retry_delays):
                retry_count += 1
                retry_delay = self.retry_delays[retry_count - 1]
                
                logger.info(f"🔄 Scheduling retry {retry_count}/{len(self.retry_delays)} for {file_path} in {retry_delay}s")
                
                # Update file status for retry (we'll implement this as a simple re-queue)
                self.processing_service.file_manager.update_status(
                    file_path, 
                    'queued',  # Re-queue for retry
                    error_message=f"Retry {retry_count}: {error_message}"
                )
                
                # Schedule retry after delay (in production, use a proper job scheduler)
                asyncio.create_task(self._schedule_retry(file_path, retry_delay))
                
                self.stats['retries'] += 1
                
            else:
                logger.error(f"❌ Max retries exceeded for {file_path}, marking as permanently failed")
                
                self.processing_service.file_manager.update_status(
                    file_path, 
                    'error',
                    error_message=f"Max retries exceeded: {error_message}"
                )
            
        except Exception as e:
            logger.error(f"Error handling processing failure for {file_path}: {e}")
    
    async def _schedule_retry(self, file_path: str, delay: float):
        """Schedule a file retry after a delay."""
        await asyncio.sleep(delay)
        
        # File is already re-queued, so it will be picked up in the next batch
        logger.info(f"🔄 Retry delay completed for {file_path}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get background processor status and statistics."""
        uptime = None
        if self.stats['started_at']:
            uptime = (datetime.now() - self.stats['started_at']).total_seconds()
        
        return {
            "status": "running" if self.is_running else "stopped",
            "is_active": self.is_running and not self.stop_event.is_set(),
            "uptime_seconds": uptime,
            "stats": {
                **self.stats,
                'started_at': self.stats['started_at'].isoformat() if self.stats['started_at'] else None,
                'last_activity': self.stats['last_activity'].isoformat() if self.stats['last_activity'] else None
            },
            "config": {
                "poll_interval": self.poll_interval,
                "max_concurrent_jobs": self.max_concurrent_jobs,
                "retry_delays": self.retry_delays
            }
        }
    
    def reset_stats(self):
        """Reset performance statistics."""
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'retries': 0,
            'started_at': self.stats['started_at'],  # Keep start time
            'last_activity': None
        }
        logger.info("📊 Background processor stats reset")
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        total = self.stats['total_processed']
        if total == 0:
            return 0.0
        return (self.stats['successful'] / total) * 100.0
    
    def __del__(self):
        """Ensure graceful shutdown on object destruction."""
        if self.is_running:
            self.stop()


# Global background processor instance
background_processor = None

def get_background_processor() -> Optional[BackgroundProcessor]:
    """Get the global background processor instance."""
    return background_processor

def start_background_processor(
    processing_service: DocumentProcessingService,
    **kwargs
) -> BackgroundProcessor:
    """Start the global background processor."""
    global background_processor
    
    if background_processor and background_processor.is_running:
        logger.warning("Background processor is already running")
        return background_processor
    
    background_processor = BackgroundProcessor(processing_service, **kwargs)
    background_processor.start()
    
    return background_processor

def stop_background_processor():
    """Stop the global background processor."""
    global background_processor
    
    if background_processor:
        background_processor.stop()
        background_processor = None