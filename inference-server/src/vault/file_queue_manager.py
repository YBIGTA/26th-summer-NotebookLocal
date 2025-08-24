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
from sqlalchemy.orm import Session
from sqlalchemy import text, and_

from ..database.connection import get_db
from ..database.models import VaultFile, Document

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
    
    def __init__(self):
        self._processing_lock = Lock()
        self._is_processing = False
        self._supported_extensions = {'.md', '.pdf', '.txt', '.docx'}
        self._ignore_patterns = {'.obsidian', 'node_modules', '.git', '__pycache__'}
        
    def _get_db(self) -> Session:
        """Get database session - using next() to get single session."""
        return next(get_db())
    
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
        Scan vault directory and update database with file changes.
        
        Returns:
            Dictionary with scan results and change statistics
        """
        if not os.path.exists(vault_path):
            raise ValueError(f"Vault path does not exist: {vault_path}")
            
        vault_path = Path(vault_path)
        changes = {
            "new_files": [],
            "modified_files": [],
            "deleted_files": [],
            "total_scanned": 0,
            "errors": []
        }
        
        db = self._get_db()
        
        try:
            with self._processing_lock:
                logger.info(f"🔍 Scanning vault directory: {vault_path}")
                
                # Get existing files from database
                existing_files = {f.vault_path: f for f in db.query(VaultFile).all()}
                current_files = set()
                
                # Scan directory recursively
                for file_path in vault_path.rglob('*'):
                    if not file_path.is_file():
                        continue
                        
                    if not self._should_process_file(file_path):
                        continue
                    
                    relative_path = str(file_path.relative_to(vault_path))
                    current_files.add(relative_path)
                    changes["total_scanned"] += 1
                    
                    try:
                        # Get file stats and hash
                        stat = file_path.stat()
                        modified_time = datetime.fromtimestamp(stat.st_mtime)
                        file_size = stat.st_size
                        content_hash = self._calculate_content_hash(str(file_path))
                        
                        if not content_hash:
                            changes["errors"].append(f"Failed to hash {relative_path}")
                            continue
                            
                        existing_file = existing_files.get(relative_path)
                        
                        if existing_file is None:
                            # New file
                            vault_file = VaultFile(
                                vault_path=relative_path,
                                file_type=file_path.suffix[1:].lower() if file_path.suffix else None,
                                content_hash=content_hash,
                                file_size=file_size,
                                modified_at=modified_time,
                                processing_status='unprocessed'
                            )
                            db.add(vault_file)
                            changes["new_files"].append(relative_path)
                            logger.info(f"➕ New file: {relative_path}")
                            
                        elif (existing_file.content_hash != content_hash or
                              existing_file.modified_at != modified_time or
                              force_rescan):
                            # Modified file
                            was_processed = existing_file.processing_status == 'processed'
                            
                            existing_file.content_hash = content_hash
                            existing_file.file_size = file_size
                            existing_file.modified_at = modified_time
                            existing_file.updated_at = datetime.now()
                            
                            # Reset processing status if content changed
                            if existing_file.content_hash != content_hash and was_processed:
                                existing_file.processing_status = 'unprocessed'
                                existing_file.error_message = None
                                logger.info(f"🔄 Content changed, reset status: {relative_path}")
                            
                            changes["modified_files"].append(relative_path)
                            
                    except Exception as e:
                        error_msg = f"Error processing file {relative_path}: {e}"
                        logger.error(error_msg)
                        changes["errors"].append(error_msg)
                        continue
                
                # Find deleted files
                for vault_path_str in existing_files.keys():
                    if vault_path_str not in current_files:
                        vault_file = existing_files[vault_path_str]
                        
                        # If file had associated document, we should clean that up too
                        if vault_file.doc_uid:
                            document = db.query(Document).filter(
                                Document.doc_uid == vault_file.doc_uid
                            ).first()
                            if document:
                                logger.info(f"🗑️ Cleaning up document for deleted file: {vault_path_str}")
                                db.delete(document)
                        
                        db.delete(vault_file)
                        changes["deleted_files"].append(vault_path_str)
                        logger.info(f"🗑️ Deleted file: {vault_path_str}")
                
                # Commit all changes
                db.commit()
                logger.info(f"✅ Scan completed: {changes['total_scanned']} files processed")
                
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Scan failed: {e}")
            raise
        finally:
            db.close()
            
        return {
            "success": True,
            "message": f"Scan completed: {changes['total_scanned']} files processed",
            "changes": changes
        }
    
    async def queue_files_for_processing(self, file_paths: List[str]) -> Dict[str, any]:
        """
        Queue specific files for processing with database update.
        
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
        
        db = self._get_db()
        
        try:
            with self._processing_lock:
                logger.info(f"📋 Queueing {len(file_paths)} files for processing")
                
                for file_path in file_paths:
                    vault_file = db.query(VaultFile).filter(
                        VaultFile.vault_path == file_path
                    ).first()
                    
                    if not vault_file:
                        result["not_found"].append(file_path)
                        continue
                    
                    if vault_file.processing_status in ['queued', 'processing']:
                        result["already_queued"].append(file_path)
                        continue
                    
                    # Update status to queued
                    vault_file.processing_status = 'queued'
                    vault_file.error_message = None
                    vault_file.updated_at = datetime.now()
                    
                    result["queued_files"].append(file_path)
                    logger.info(f"📋 Queued: {file_path}")
                
                db.commit()
                logger.info(f"✅ Queued {len(result['queued_files'])} files successfully")
                
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Queue operation failed: {e}")
            raise
        finally:
            db.close()
            
        return result
    
    async def get_queue_status(self) -> QueueStatus:
        """Get current queue processing status."""
        db = self._get_db()
        
        try:
            # Count files by status
            status_counts = db.execute(text("""
                SELECT processing_status, COUNT(*) as count
                FROM vault_files 
                GROUP BY processing_status
            """)).fetchall()
            
            counts = {row[0]: row[1] for row in status_counts}
            
            # Count completed today
            completed_today = db.execute(text("""
                SELECT COUNT(*) 
                FROM vault_files 
                WHERE processing_status = 'processed' 
                AND DATE(updated_at) = DATE(NOW())
            """)).scalar() or 0
            
            return QueueStatus(
                total_queued=counts.get('queued', 0),
                processing=counts.get('processing', 0),
                completed_today=completed_today,
                failed=counts.get('error', 0),
                is_processing=self._is_processing
            )
            
        finally:
            db.close()
    
    async def get_queued_files(self, limit: int = 100) -> List[VaultFile]:
        """Get files that are queued for processing."""
        db = self._get_db()
        
        try:
            files = db.query(VaultFile).filter(
                VaultFile.processing_status == 'queued'
            ).limit(limit).all()
            
            return files
            
        finally:
            db.close()
    
    async def mark_file_processing(self, file_path: str) -> bool:
        """Mark a file as currently processing."""
        db = self._get_db()
        
        try:
            vault_file = db.query(VaultFile).filter(
                VaultFile.vault_path == file_path
            ).first()
            
            if not vault_file or vault_file.processing_status != 'queued':
                return False
            
            vault_file.processing_status = 'processing'
            vault_file.updated_at = datetime.now()
            db.commit()
            
            logger.info(f"🔄 Processing: {file_path}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error marking file as processing: {e}")
            return False
        finally:
            db.close()
    
    async def mark_file_processed(self, file_path: str, doc_uid: Optional[str] = None) -> bool:
        """Mark a file as successfully processed."""
        db = self._get_db()
        
        try:
            vault_file = db.query(VaultFile).filter(
                VaultFile.vault_path == file_path
            ).first()
            
            if not vault_file:
                return False
            
            vault_file.processing_status = 'processed'
            vault_file.error_message = None
            vault_file.updated_at = datetime.now()
            
            if doc_uid:
                vault_file.doc_uid = doc_uid
                
            db.commit()
            
            logger.info(f"✅ Processed: {file_path}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error marking file as processed: {e}")
            return False
        finally:
            db.close()
    
    async def mark_file_error(self, file_path: str, error_message: str) -> bool:
        """Mark a file as failed processing."""
        db = self._get_db()
        
        try:
            vault_file = db.query(VaultFile).filter(
                VaultFile.vault_path == file_path
            ).first()
            
            if not vault_file:
                return False
            
            vault_file.processing_status = 'error'
            vault_file.error_message = error_message[:1000]  # Truncate long errors
            vault_file.updated_at = datetime.now()
            
            db.commit()
            
            logger.error(f"❌ Processing failed: {file_path} - {error_message}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error marking file as error: {e}")
            return False
        finally:
            db.close()
    
    def is_processing(self) -> bool:
        """Check if queue manager is currently processing files."""
        return self._is_processing
    
    def set_processing_state(self, is_processing: bool):
        """Set the processing state (used by processing workers)."""
        with self._processing_lock:
            self._is_processing = is_processing