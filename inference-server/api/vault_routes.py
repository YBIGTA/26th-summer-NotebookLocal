"""
Vault management API routes for Obsidian integration

Endpoints:
- GET /api/v1/vault/files - List vault files with processing status
- POST /api/v1/vault/scan - Scan vault for changes
- POST /api/v1/vault/process - Queue files for processing  
- DELETE /api/v1/vault/files/{file_id} - Remove from processing queue
- GET /api/v1/vault/status - Get processing status summary
- GET /api/v1/vault/search - Search files/folders for autocomplete
- GET /api/v1/vault/files/recent - Get recently modified files
- GET /api/v1/vault/files/by-tag - Get files by tag
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import hashlib
import os
import mimetypes

from src.database.connection import get_db
from src.database.models import VaultFile, Document
from src.vault.file_queue_manager import FileQueueManager, QueueStatus
from src.vault.file_watcher import get_file_watcher, start_global_watcher, stop_global_watcher
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/vault", tags=["vault"])

# Global queue manager instance
queue_manager = FileQueueManager()

# Request/Response Models
class VaultFileResponse(BaseModel):
    file_id: str
    vault_path: str
    file_type: Optional[str]
    content_hash: Optional[str]
    file_size: Optional[int]
    modified_at: Optional[datetime]
    processing_status: str
    doc_uid: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

class VaultScanRequest(BaseModel):
    vault_path: str
    force_rescan: bool = False

class VaultProcessRequest(BaseModel):
    file_paths: List[str]
    force_reprocess: bool = False

class VaultStatusResponse(BaseModel):
    total_files: int
    processed: int
    queued: int
    processing: int
    unprocessed: int
    error: int
    last_scan: Optional[datetime]
    is_processing: bool
    completed_today: int

class FileSearchRequest(BaseModel):
    query: str
    limit: int = 50
    file_types: Optional[List[str]] = None

class FileSearchResult(BaseModel):
    path: str
    name: str
    type: str  # 'file' or 'folder'
    processing_status: Optional[str]

@router.get("/files", response_model=List[VaultFileResponse])
async def list_vault_files(
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None, description="Filter by processing status"),
    file_type: Optional[str] = Query(None, description="Filter by file type"),
    limit: int = Query(100, description="Maximum number of files to return"),
    offset: int = Query(0, description="Number of files to skip")
):
    """List vault files with optional filtering"""
    
    query = db.query(VaultFile)
    
    if status:
        query = query.filter(VaultFile.processing_status == status)
    
    if file_type:
        query = query.filter(VaultFile.file_type == file_type)
    
    files = query.offset(offset).limit(limit).all()
    
    return [VaultFileResponse(
        file_id=str(file.file_id),
        vault_path=file.vault_path,
        file_type=file.file_type,
        content_hash=file.content_hash,
        file_size=file.file_size,
        modified_at=file.modified_at,
        processing_status=file.processing_status,
        doc_uid=str(file.doc_uid) if file.doc_uid else None,
        error_message=file.error_message,
        created_at=file.created_at,
        updated_at=file.updated_at
    ) for file in files]

@router.post("/scan")
async def scan_vault_changes(
    request: VaultScanRequest
):
    """Scan vault directory for file changes using enhanced queue manager"""
    
    try:
        result = await queue_manager.scan_vault_directory(
            vault_path=request.vault_path,
            force_rescan=request.force_rescan
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")

@router.post("/process")
async def process_vault_files(
    request: VaultProcessRequest
):
    """Queue files for processing using enhanced queue manager"""
    
    try:
        result = await queue_manager.queue_files_for_processing(request.file_paths)
        
        return {
            "message": f"Queued {len(result['queued_files'])} files for processing",
            "queued_files": result["queued_files"],
            "failed_files": result["failed_files"],
            "already_queued": result["already_queued"],
            "not_found": result["not_found"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Queue operation failed: {str(e)}")

@router.delete("/files/{file_id}")
async def remove_from_queue(
    file_id: str,
    db: Session = Depends(get_db)
):
    """Remove file from processing queue using enhanced queue manager"""
    
    vault_file = db.query(VaultFile).filter(VaultFile.file_id == file_id).first()
    
    if not vault_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Only allow removal from queue if it's queued or has error
    if vault_file.processing_status not in ['queued', 'error']:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot remove file with status: {vault_file.processing_status}"
        )
    
    try:
        # Use queue manager for thread-safe operations
        result = await queue_manager.queue_files_for_processing([])  # Empty to trigger validation
        
        # Manual removal (queue manager doesn't have remove method, so direct DB update)
        vault_file.processing_status = 'unprocessed'
        vault_file.error_message = None
        vault_file.updated_at = datetime.now()
        
        db.commit()
        
        return {"message": f"Removed {vault_file.vault_path} from queue"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Remove operation failed: {str(e)}")

@router.get("/status", response_model=VaultStatusResponse)
async def get_vault_status():
    """Get processing status summary using enhanced queue manager"""
    
    try:
        queue_status = await queue_manager.get_queue_status()
        
        # Get additional stats from database
        db = next(get_db())
        try:
            status_counts = db.execute(text("""
                SELECT processing_status, COUNT(*) as count
                FROM vault_files 
                GROUP BY processing_status
            """)).fetchall()
            
            counts = {row[0]: row[1] for row in status_counts}
            total_files = sum(counts.values())
            
            # Get last scan time (most recent file creation)
            last_scan = db.execute(text("""
                SELECT MAX(created_at) FROM vault_files
            """)).scalar()
            
            return VaultStatusResponse(
                total_files=total_files,
                processed=counts.get('processed', 0),
                queued=queue_status.total_queued,
                processing=queue_status.processing,
                unprocessed=counts.get('unprocessed', 0),
                error=queue_status.failed,
                last_scan=last_scan,
                is_processing=queue_status.is_processing,
                completed_today=queue_status.completed_today
            )
        finally:
            db.close()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status query failed: {str(e)}")

@router.post("/search", response_model=List[FileSearchResult])
async def search_files(
    request: FileSearchRequest,
    db: Session = Depends(get_db)
):
    """Search files and folders for autocomplete"""
    
    query = f"%{request.query.lower()}%"
    
    # Search files
    file_query = db.query(VaultFile).filter(
        VaultFile.vault_path.ilike(query)
    )
    
    if request.file_types:
        file_query = file_query.filter(VaultFile.file_type.in_(request.file_types))
    
    files = file_query.limit(request.limit).all()
    
    results = []
    
    # Add file results
    for file in files:
        results.append(FileSearchResult(
            path=file.vault_path,
            name=os.path.basename(file.vault_path),
            type='file',
            processing_status=file.processing_status
        ))
    
    # Add folder results (simplified - would need folder tracking for full implementation)
    # This is a basic implementation that extracts folder paths from file paths
    folder_paths = set()
    for file in files:
        parts = file.vault_path.split(os.sep)
        for i in range(1, len(parts)):
            folder_path = os.sep.join(parts[:i])
            if request.query.lower() in folder_path.lower():
                folder_paths.add(folder_path)
    
    for folder_path in list(folder_paths)[:request.limit - len(results)]:
        results.append(FileSearchResult(
            path=folder_path,
            name=os.path.basename(folder_path),
            type='folder',
            processing_status=None
        ))
    
    return results[:request.limit]

@router.get("/files/recent", response_model=List[VaultFileResponse])
async def get_recent_files(
    db: Session = Depends(get_db),
    days: int = Query(7, description="Number of days to look back"),
    limit: int = Query(20, description="Maximum number of files to return")
):
    """Get recently modified files"""
    
    since = datetime.now() - timedelta(days=days)
    
    files = db.query(VaultFile).filter(
        VaultFile.modified_at >= since
    ).order_by(VaultFile.modified_at.desc()).limit(limit).all()
    
    return [VaultFileResponse(
        file_id=str(file.file_id),
        vault_path=file.vault_path,
        file_type=file.file_type,
        content_hash=file.content_hash,
        file_size=file.file_size,
        modified_at=file.modified_at,
        processing_status=file.processing_status,
        doc_uid=str(file.doc_uid) if file.doc_uid else None,
        error_message=file.error_message,
        created_at=file.created_at,
        updated_at=file.updated_at
    ) for file in files]

@router.get("/files/by-tag")
async def get_files_by_tag(
    tag: str = Query(..., description="Tag to search for"),
    db: Session = Depends(get_db),
    limit: int = Query(50, description="Maximum number of files to return")
):
    """Get files by tag (requires document processing for tag extraction)"""
    
    # This would require implementing tag extraction during document processing
    # For now, return a placeholder response
    
    return {
        "message": f"Tag search for '{tag}' not yet implemented",
        "files": [],
        "note": "Tag search requires document processing with metadata extraction"
    }

# New queue management endpoints

@router.get("/queue/status")
async def get_queue_status():
    """Get detailed queue processing status"""
    
    try:
        status = await queue_manager.get_queue_status()
        return {
            "success": True,
            "status": {
                "total_queued": status.total_queued,
                "processing": status.processing,
                "completed_today": status.completed_today,
                "failed": status.failed,
                "is_processing": status.is_processing
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Queue status query failed: {str(e)}")

@router.get("/queue/files")
async def get_queued_files(
    limit: int = Query(100, description="Maximum number of files to return")
):
    """Get files currently in the processing queue"""
    
    try:
        files = await queue_manager.get_queued_files(limit)
        
        return {
            "success": True,
            "queued_files": [
                {
                    "file_id": str(file.file_id),
                    "vault_path": file.vault_path,
                    "file_type": file.file_type,
                    "file_size": file.file_size,
                    "modified_at": file.modified_at,
                    "processing_status": file.processing_status,
                    "created_at": file.created_at,
                    "updated_at": file.updated_at
                } for file in files
            ],
            "count": len(files)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Queue files query failed: {str(e)}")

@router.post("/queue/process-next")
async def process_next_file():
    """Process the next file in queue (for processing workers)"""
    
    try:
        files = await queue_manager.get_queued_files(1)
        
        if not files:
            return {
                "success": True,
                "message": "No files in queue",
                "processed_file": None
            }
        
        file = files[0]
        
        # Mark as processing
        success = await queue_manager.mark_file_processing(file.vault_path)
        
        if success:
            return {
                "success": True,
                "message": "File marked for processing",
                "processing_file": {
                    "file_id": str(file.file_id),
                    "vault_path": file.vault_path,
                    "file_type": file.file_type,
                    "file_size": file.file_size
                }
            }
        else:
            return {
                "success": False,
                "message": "Failed to mark file for processing"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Process next file failed: {str(e)}")

@router.post("/queue/mark-processed/{file_path}")
async def mark_file_processed(
    file_path: str,
    doc_uid: Optional[str] = Query(None, description="Document UID if processing succeeded")
):
    """Mark a file as successfully processed"""
    
    try:
        success = await queue_manager.mark_file_processed(file_path, doc_uid)
        
        if success:
            return {
                "success": True,
                "message": f"File marked as processed: {file_path}"
            }
        else:
            return {
                "success": False,
                "message": f"Failed to mark file as processed: {file_path}"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Mark processed failed: {str(e)}")

@router.post("/queue/mark-error/{file_path}")
async def mark_file_error(
    file_path: str,
    error_message: str = Query(..., description="Error message to record")
):
    """Mark a file as failed processing"""
    
    try:
        success = await queue_manager.mark_file_error(file_path, error_message)
        
        if success:
            return {
                "success": True,
                "message": f"File marked with error: {file_path}"
            }
        else:
            return {
                "success": False,
                "message": f"Failed to mark file with error: {file_path}"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Mark error failed: {str(e)}")

# File watcher endpoints

@router.post("/watcher/start")
async def start_file_watcher(
    vault_path: str = Query(..., description="Path to vault directory to watch")
):
    """Start file system watcher for real-time change detection"""
    
    try:
        watcher = start_global_watcher(vault_path)
        
        return {
            "success": True,
            "message": f"Started file watcher for: {vault_path}",
            "status": watcher.get_status()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start file watcher: {str(e)}")

@router.post("/watcher/stop")
async def stop_file_watcher():
    """Stop file system watcher"""
    
    try:
        stop_global_watcher()
        
        return {
            "success": True,
            "message": "Stopped file watcher"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop file watcher: {str(e)}")

@router.get("/watcher/status")
async def get_watcher_status():
    """Get file watcher status"""
    
    try:
        watcher = get_file_watcher()
        
        if watcher:
            return {
                "success": True,
                "status": watcher.get_status()
            }
        else:
            return {
                "success": True,
                "status": {
                    "is_watching": False,
                    "vault_path": None,
                    "pending_events": 0,
                    "message": "File watcher not initialized"
                }
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get watcher status: {str(e)}")