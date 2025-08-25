"""
FileManager - Clean interface for all vault file operations.

Provides intuitive methods for managing vault files:
- Get files by path, status, or other criteria  
- Add new files with validation
- Update file status and metadata
- Bulk operations for processing
"""

import logging
import os
import hashlib
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from .manager import DatabaseManager, db_manager as global_db_manager
from .models import VaultFile, Document

logger = logging.getLogger(__name__)


class FileManager:
    """Manage vault file operations with clean, consistent interface."""
    
    def __init__(self, db_manager: DatabaseManager = None):
        self.db = db_manager if db_manager is not None else global_db_manager
        logger.info(f"FileManager initialized with db_manager: {self.db is not None}")
    
    def get_file_by_id(self, file_id: str) -> Optional[VaultFile]:
        """
        Get vault file by its database ID.
        
        Args:
            file_id: Database file ID
            
        Returns:
            VaultFile instance or None if not found
        """
        with self.db.session() as session:
            return session.query(VaultFile).filter(
                VaultFile.file_id == file_id
            ).first()
    
    def get_file(self, path: str) -> Optional[VaultFile]:
        """
        Get single file by vault path.
        
        Args:
            path: Vault-relative file path (e.g., "notes/my-note.md")
            
        Returns:
            VaultFile instance or None if not found
        """
        if self.db is None:
            logger.error("FileManager database manager is None")
            return None
        
        with self.db.session() as session:
            return session.query(VaultFile).filter(
                VaultFile.vault_path == path
            ).first()
    
    def get_files_by_status(self, status: str) -> List[VaultFile]:
        """
        Get all files with specific processing status.
        
        Args:
            status: 'unprocessed', 'queued', 'processing', 'processed', 'error'
        """
        with self.db.session() as session:
            return session.query(VaultFile).filter(
                VaultFile.processing_status == status
            ).order_by(VaultFile.created_at).all()
    
    def get_processed_files(self) -> List[VaultFile]:
        """Get all successfully processed files."""
        return self.get_files_by_status('processed')
    
    def get_files_for_processing(self) -> List[VaultFile]:
        """Get files ready for processing (unprocessed or queued)."""
        with self.db.session() as session:
            return session.query(VaultFile).filter(
                VaultFile.processing_status.in_(['unprocessed', 'queued'])
            ).order_by(VaultFile.created_at).all()
    
    def list_files(self, 
                   file_type: str = None, 
                   status: str = None,
                   limit: int = None,
                   offset: int = 0) -> List[VaultFile]:
        """
        List files with optional filters.
        
        Args:
            file_type: Filter by file extension (e.g., 'md', 'pdf')
            status: Filter by processing status
            limit: Maximum number of files to return
            offset: Number of files to skip
        """
        with self.db.session() as session:
            query = session.query(VaultFile)
            
            if file_type:
                query = query.filter(VaultFile.file_type == file_type)
            
            if status:
                query = query.filter(VaultFile.processing_status == status)
            
            query = query.order_by(VaultFile.updated_at.desc())
            
            if limit:
                query = query.offset(offset).limit(limit)
            
            return query.all()
    
    def add_file(self, 
                 path: str, 
                 content: str = None,
                 file_size: int = None,
                 modified_at: datetime = None,
                 content_hash: str = None) -> VaultFile:
        """
        Add new file to vault tracking.
        
        Args:
            path: Vault-relative file path
            content: File content (optional)
            file_size: Size in bytes
            modified_at: Last modification time
            content_hash: MD5/SHA hash for change detection
            
        Returns:
            Created VaultFile instance
        """
        # Extract file type from extension
        file_type = Path(path).suffix.lstrip('.').lower() if '.' in path else None
        
        with self.db.session() as session:
            # Check if file already exists
            existing = session.query(VaultFile).filter(
                VaultFile.vault_path == path
            ).first()
            
            if existing:
                logger.warning(f"File already exists: {path}")
                return existing
            
            vault_file = VaultFile(
                vault_path=path,
                file_type=file_type,
                file_size=file_size,
                modified_at=modified_at or datetime.utcnow(),
                content_hash=content_hash,
                processing_status='unprocessed'
            )
            
            session.add(vault_file)
            session.flush()  # Get ID without committing
            
            logger.info(f"Added file to vault tracking: {path}")
            return vault_file
    
    def update_file_content(self, 
                           path: str, 
                           content_hash: str = None,
                           file_size: int = None,
                           modified_at: datetime = None) -> Optional[VaultFile]:
        """
        Update file content metadata (triggers reprocessing).
        
        Args:
            path: File path to update
            content_hash: New content hash
            file_size: New file size
            modified_at: New modification time
        """
        with self.db.session() as session:
            vault_file = session.query(VaultFile).filter(
                VaultFile.vault_path == path
            ).first()
            
            if not vault_file:
                logger.warning(f"File not found for update: {path}")
                return None
            
            # Update metadata
            if content_hash:
                vault_file.content_hash = content_hash
            if file_size is not None:
                vault_file.file_size = file_size
            if modified_at:
                vault_file.modified_at = modified_at
            
            # Reset processing status to trigger reprocessing
            vault_file.processing_status = 'unprocessed'
            vault_file.error_message = None
            
            logger.info(f"Updated file content: {path}")
            return vault_file
    
    def update_status(self, 
                     path: str, 
                     status: str, 
                     error_message: str = None,
                     doc_uid: str = None,
                     processing_result: dict = None) -> Optional[VaultFile]:
        """
        Update file processing status with enhanced tracking.
        
        Args:
            path: File path
            status: New processing status
            error_message: Error details (for 'error' status)
            doc_uid: Linked document ID (for 'processed' status)
            processing_result: Dict with processing metrics (chunks_created, images_processed, etc.)
        """
        valid_statuses = ['unprocessed', 'queued', 'processing', 'processed', 'error']
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")
        
        with self.db.session() as session:
            vault_file = session.query(VaultFile).filter(
                VaultFile.vault_path == path
            ).first()
            
            if not vault_file:
                logger.warning(f"File not found for status update: {path}")
                return None
            
            vault_file.processing_status = status
            
            # Handle status-specific updates
            if status == 'processing':
                vault_file.processing_started_at = datetime.utcnow()
                vault_file.processing_progress = 0
                
            elif status == 'processed':
                vault_file.processing_completed_at = datetime.utcnow()
                vault_file.processing_progress = 100
                vault_file.error_message = None  # Clear any previous errors
                
                # Update processing results if provided
                if processing_result:
                    vault_file.chunks_created = processing_result.get('chunks_created')
                    vault_file.images_processed = processing_result.get('images_processed')
                    processing_time = processing_result.get('processing_time')
                    if processing_time:
                        vault_file.processing_time_seconds = int(processing_time)
                
            elif status == 'error':
                vault_file.processing_completed_at = datetime.utcnow()
                vault_file.processing_progress = 0
                vault_file.retry_count = (vault_file.retry_count or 0) + 1
                vault_file.last_error = error_message
                
            if error_message:
                vault_file.error_message = error_message
            elif status not in ['error', 'queued']:  # Don't clear errors for queued (retry) status
                vault_file.error_message = None
                
            if doc_uid:
                vault_file.doc_uid = doc_uid
            
            logger.info(f"Updated file status: {path} -> {status}")
            return vault_file
    
    def remove_file(self, path: str) -> bool:
        """
        Remove file from vault tracking.
        
        Args:
            path: File path to remove
            
        Returns:
            True if file was removed, False if not found
        """
        with self.db.session() as session:
            vault_file = session.query(VaultFile).filter(
                VaultFile.vault_path == path
            ).first()
            
            if not vault_file:
                logger.warning(f"File not found for removal: {path}")
                return False
            
            session.delete(vault_file)
            logger.info(f"Removed file from vault tracking: {path}")
            return True
    
    def get_file_count(self, status: str = None) -> int:
        """Get count of files, optionally filtered by status."""
        with self.db.session() as session:
            query = session.query(VaultFile)
            
            if status:
                query = query.filter(VaultFile.processing_status == status)
            
            return query.count()
    
    def get_files_with_content(self, query: str, limit: int = 10) -> List[VaultFile]:
        """
        Get files that likely contain content matching query.
        
        This is a simple text search - for semantic search use ContextManager.
        """
        with self.db.session() as session:
            # Simple filename/path matching
            return session.query(VaultFile).filter(
                VaultFile.vault_path.ilike(f'%{query}%')
            ).filter(
                VaultFile.processing_status == 'processed'
            ).limit(limit).all()
    
    def batch_update_status(self, file_paths: List[str], status: str) -> int:
        """
        Update status for multiple files at once.
        
        Returns:
            Number of files updated
        """
        with self.db.session() as session:
            updated = session.query(VaultFile).filter(
                VaultFile.vault_path.in_(file_paths)
            ).update(
                {VaultFile.processing_status: status},
                synchronize_session=False
            )
            
            logger.info(f"Batch updated {updated} files to status: {status}")
            return updated
    
    # ========================================
    # Content Storage and Retrieval Methods
    # ========================================
    
    def store_file_content(self, 
                          vault_path: str, 
                          content: str, 
                          vault_root: str) -> Dict[str, Any]:
        """
        Store file content and update metadata.
        
        Args:
            vault_path: Vault-relative path (e.g., 'notes/file.md')
            content: File content to store
            vault_root: Absolute path to vault root directory
            
        Returns:
            Dict with file info and storage status
        """
        try:
            # Calculate content metadata
            content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
            file_size = len(content.encode('utf-8'))
            
            # Get file modification time from filesystem
            full_path = os.path.join(vault_root, vault_path)
            modified_at = None
            if os.path.exists(full_path):
                modified_at = datetime.fromtimestamp(os.path.getmtime(full_path))
            
            # Get or create vault file record
            vault_file = self.get_file(vault_path)
            if not vault_file:
                vault_file = self.add_file(
                    path=vault_path,
                    file_size=file_size,
                    modified_at=modified_at,
                    content_hash=content_hash
                )
            else:
                # Update existing file
                self.update_file_content(
                    path=vault_path,
                    content_hash=content_hash,
                    file_size=file_size,
                    modified_at=modified_at
                )
            
            # TODO: Store content in dedicated content store
            # For now, we rely on hybrid_store for content storage
            # Could add separate content table or file-based storage
            
            logger.info(f"Stored content for file: {vault_path} ({file_size} bytes)")
            
            return {
                'file_id': vault_file.file_id,
                'vault_path': vault_path,
                'file_size': file_size,
                'content_hash': content_hash,
                'modified_at': modified_at.isoformat() if modified_at else None,
                'status': 'stored'
            }
            
        except Exception as e:
            logger.error(f"Error storing file content {vault_path}: {e}")
            return {
                'vault_path': vault_path,
                'status': 'error',
                'error': str(e)
            }
    
    def get_file_content(self, vault_path: str, vault_root: str) -> Optional[str]:
        """
        Get file content from filesystem.
        
        Args:
            vault_path: Vault-relative path
            vault_root: Absolute path to vault root
            
        Returns:
            File content as string, or None if not found
        """
        try:
            full_path = os.path.join(vault_root, vault_path)
            
            if not os.path.exists(full_path):
                logger.warning(f"File not found: {full_path}")
                return None
            
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            logger.debug(f"Retrieved content for: {vault_path} ({len(content)} chars)")
            return content
            
        except Exception as e:
            logger.error(f"Error reading file content {vault_path}: {e}")
            return None
    
    def scan_vault_directory(self, vault_root: str, file_extensions: List[str] = None) -> Dict[str, Any]:
        """
        Scan vault directory for files and sync with database.
        
        Args:
            vault_root: Absolute path to vault root
            file_extensions: List of extensions to include (e.g., ['.md', '.txt'])
            
        Returns:
            Summary of scan results
        """
        if file_extensions is None:
            file_extensions = ['.md', '.txt', '.pdf', '.docx']
        
        try:
            scanned_files = []
            new_files = []
            updated_files = []
            
            # Walk through vault directory
            for root, dirs, files in os.walk(vault_root):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for file in files:
                    # Skip hidden files
                    if file.startswith('.'):
                        continue
                    
                    file_path = Path(root) / file
                    
                    # Check extension
                    if file_extensions and file_path.suffix.lower() not in file_extensions:
                        continue
                    
                    # Get vault-relative path
                    vault_rel_path = str(file_path.relative_to(vault_root))
                    scanned_files.append(vault_rel_path)
                    
                    # Get file stats
                    stat = file_path.stat()
                    modified_at = datetime.fromtimestamp(stat.st_mtime)
                    file_size = stat.st_size
                    
                    # Check if file exists in database
                    vault_file = self.get_file(vault_rel_path)
                    
                    if not vault_file:
                        # New file
                        self.add_file(
                            path=vault_rel_path,
                            file_size=file_size,
                            modified_at=modified_at
                        )
                        new_files.append(vault_rel_path)
                    else:
                        # Check if file was modified
                        if (vault_file.modified_at is None or 
                            modified_at > vault_file.modified_at or 
                            file_size != vault_file.file_size):
                            
                            self.update_file_content(
                                path=vault_rel_path,
                                file_size=file_size,
                                modified_at=modified_at
                            )
                            updated_files.append(vault_rel_path)
            
            # Mark files no longer on disk as removed
            existing_files = [f.vault_path for f in self.list_files()]
            removed_files = [f for f in existing_files if f not in scanned_files]
            
            for removed_path in removed_files:
                self.remove_file(removed_path)
            
            logger.info(f"Vault scan completed: {len(scanned_files)} files, {len(new_files)} new, {len(updated_files)} updated, {len(removed_files)} removed")
            
            return {
                'total_files': len(scanned_files),
                'new_files': len(new_files),
                'updated_files': len(updated_files),
                'removed_files': len(removed_files),
                'new_file_paths': new_files,
                'updated_file_paths': updated_files,
                'removed_file_paths': removed_files
            }
            
        except Exception as e:
            logger.error(f"Error scanning vault directory {vault_root}: {e}")
            return {
                'error': str(e),
                'total_files': 0
            }
    
    def get_file_with_content(self, vault_path: str, vault_root: str) -> Optional[Dict[str, Any]]:
        """
        Get file metadata and content together.
        
        Args:
            vault_path: Vault-relative path
            vault_root: Absolute path to vault root
            
        Returns:
            Dict with file metadata and content, or None if not found
        """
        vault_file = self.get_file(vault_path)
        if not vault_file:
            return None
        
        content = self.get_file_content(vault_path, vault_root)
        
        return {
            'file_id': vault_file.file_id,
            'vault_path': vault_file.vault_path,
            'file_type': vault_file.file_type,
            'file_size': vault_file.file_size,
            'content_hash': vault_file.content_hash,
            'modified_at': vault_file.modified_at.isoformat() if vault_file.modified_at else None,
            'processing_status': vault_file.processing_status,
            'error_message': vault_file.error_message,
            'content': content
        }


# Global instance for easy access
file_manager = FileManager()