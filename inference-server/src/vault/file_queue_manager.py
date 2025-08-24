"""
File Queue Manager - Simple queue with locking for file processing synchronization

Features:
- Thread-safe queue operations with database locking
- File change detection and DB synchronization
- Concurrent processing control
- Simple implementation for low-concurrent scenarios
"""

import asyncio
import logging
import hashlib
import os
from datetime import datetime
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from threading import Lock
from pathlib import Path
from ..database.file_manager import FileManager, file_manager
from ..database.models import VaultFile

logger = logging.getLogger(__name__)

@dataclass
class FileChangeEvent:
    file_path: str
    event_type: str  # 'created', 'modified', 'deleted'
    timestamp: datetime
    content_hash: Optional[str] = None
    file_size: Optional[int] = None

@dataclass
class QueueStatus:
    total_queued: int
    processing: int
    completed_today: int
    failed: int
    is_processing: bool

class FileQueueManager:
    """Simple file queue manager with database synchronization and locking."""
    
    def __init__(self, file_manager: FileManager = None):
        self._processing_lock = Lock()
        self._is_processing = False
        self._supported_extensions = {'.md', '.pdf', '.txt', '.docx'}
        self.file_manager = file_manager or file_manager
        self._ignore_patterns = {'.obsidian', 'node_modules', '.git', '__pycache__'}
        
# Removed old database connection method - now using FileManager
    
    def _calculate_content_hash(self, file_path: str) -> Optional[str]:
        """Calculate MD5 hash of file content."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return None
    
    def _should_process_file(self, file_path: Path) -> bool:
        """Check if file should be processed based on extension and patterns."""
        # Skip hidden files
        if file_path.name.startswith('.'):
            return False
            
        # Skip files in ignored directories
        for part in file_path.parts:
            if part in self._ignore_patterns:
                return False
                
        # Check extension
        return file_path.suffix.lower() in self._supported_extensions
    
    async def scan_vault_directory(self, vault_path: str, force_rescan: bool = False) -> Dict[str, any]:
        """
        Scan vault directory and update database with file changes using FileManager.
        
        Returns:
            Dictionary with scan results and change statistics
        """
        try:
            with self._processing_lock:
                logger.info(f"🔍 Scanning vault directory: {vault_path}")
                
                # Use FileManager's scan method - much cleaner!
                scan_result = self.file_manager.scan_vault_directory(
                    vault_root=vault_path,
                    file_extensions=[ext for ext in self._supported_extensions]
                )
                
                if 'error' in scan_result:
                    raise Exception(scan_result['error'])
                
                changes = {
                    "new_files": scan_result.get('new_file_paths', []),
                    "modified_files": scan_result.get('updated_file_paths', []),
                    "deleted_files": scan_result.get('removed_file_paths', []),
                    "total_scanned": scan_result.get('total_files', 0),
                    "errors": []
                }
                
                logger.info(f"✅ Scan completed: {changes['total_scanned']} files processed")
                
                return {
                    "success": True,
                    "message": f"Scan completed: {changes['total_scanned']} files processed",
                    "changes": changes
                }
                
        except Exception as e:
            logger.error(f"❌ Scan failed: {e}")
            raise
    
    async def queue_files_for_processing(self, file_paths: List[str]) -> Dict[str, any]:
        """
        Queue specific files for processing using FileManager.
        
        Args:
            file_paths: List of relative file paths to queue
            
        Returns:
            Dictionary with queueing results
        """
        result = {
            "queued_files": [],
            "failed_files": [],
            "already_queued": [],
            "not_found": []
        }
        
        try:
            with self._processing_lock:
                logger.info(f"📋 Queueing {len(file_paths)} files for processing")
                
                for file_path in file_paths:
                    vault_file = self.file_manager.get_file(file_path)
                    
                    if not vault_file:
                        result["not_found"].append(file_path)
                        continue
                    
                    if vault_file.processing_status in ['queued', 'processing']:
                        result["already_queued"].append(file_path)
                        continue
                    
                    # Update status to queued using FileManager
                    updated_file = self.file_manager.update_status(
                        path=file_path,
                        status='queued'
                    )
                    
                    if updated_file:
                        result["queued_files"].append(file_path)
                        logger.info(f"📋 Queued: {file_path}")
                    else:
                        result["failed_files"].append(file_path)
                
                logger.info(f"✅ Queued {len(result['queued_files'])} files successfully")
                
        except Exception as e:
            logger.error(f"❌ Queue operation failed: {e}")
            raise
            
        return result
    
    async def get_queue_status(self) -> QueueStatus:
        """Get current queue processing status using FileManager."""
        try:
            total_queued = self.file_manager.get_file_count('queued')
            processing = self.file_manager.get_file_count('processing')
            failed = self.file_manager.get_file_count('error')
            
            # TODO: Implement completed_today count in FileManager
            # For now, use 0 as placeholder
            completed_today = 0
            
            return QueueStatus(
                total_queued=total_queued,
                processing=processing,
                completed_today=completed_today,
                failed=failed,
                is_processing=self._is_processing
            )
        except Exception as e:
            logger.error(f"Error getting queue status: {e}")
            return QueueStatus(0, 0, 0, 0, False)
    
    async def get_queued_files(self, limit: int = 100) -> List[VaultFile]:
        """Get files that are queued for processing."""
        try:
            files = self.file_manager.list_files(
                status='queued',
                limit=limit
            )
            return files
        except Exception as e:
            logger.error(f"Error getting queued files: {e}")
            return []
    
    async def mark_file_processing(self, file_path: str) -> bool:
        """Mark a file as currently processing."""
        try:
            vault_file = self.file_manager.get_file(file_path)
            
            if not vault_file or vault_file.processing_status != 'queued':
                return False
            
            updated_file = self.file_manager.update_status(
                path=file_path,
                status='processing'
            )
            
            if updated_file:
                logger.info(f"🔄 Processing: {file_path}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error marking file as processing: {e}")
            return False
    
    async def mark_file_processed(self, file_path: str, doc_uid: Optional[str] = None) -> bool:
        """Mark a file as successfully processed."""
        try:
            updated_file = self.file_manager.update_status(
                path=file_path,
                status='processed',
                doc_uid=doc_uid
            )
            
            if updated_file:
                logger.info(f"✅ Processed: {file_path}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error marking file as processed: {e}")
            return False
    
    async def mark_file_error(self, file_path: str, error_message: str) -> bool:
        """Mark a file as failed processing."""
        try:
            # Truncate long errors
            truncated_error = error_message[:1000] if len(error_message) > 1000 else error_message
            
            updated_file = self.file_manager.update_status(
                path=file_path,
                status='error',
                error_message=truncated_error
            )
            
            if updated_file:
                logger.error(f"❌ Processing failed: {file_path} - {error_message}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error marking file as error: {e}")
            return False
    
    def is_processing(self) -> bool:
        """Check if queue manager is currently processing files."""
        return self._is_processing
    
    def set_processing_state(self, is_processing: bool):
        """Set the processing state (used by processing workers)."""
        with self._processing_lock:
            self._is_processing = is_processing