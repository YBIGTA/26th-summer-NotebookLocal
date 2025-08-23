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
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import hashlib
import os
import mimetypes

from src.database.connection import get_db
from src.database.models import VaultFile, Document
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/vault", tags=["vault"])

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
    request: VaultScanRequest,
    db: Session = Depends(get_db)
):
    """Scan vault directory for file changes"""
    
    vault_path = request.vault_path
    if not os.path.exists(vault_path):
        raise HTTPException(status_code=404, detail="Vault path not found")
    
    changes = {
        "new_files": [],
        "modified_files": [],
        "deleted_files": [],
        "total_scanned": 0
    }
    
    # Get existing files from database
    existing_files = {f.vault_path: f for f in db.query(VaultFile).all()}
    current_files = set()
    
    # Scan vault directory
    supported_extensions = {'.md', '.pdf', '.txt', '.docx'}
    
    for root, dirs, files in os.walk(vault_path):
        # Skip hidden directories and common ignore patterns
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {'.obsidian', 'node_modules'}]
        
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, vault_path)
            
            # Skip hidden files and unsupported extensions
            if file.startswith('.'):
                continue
                
            _, ext = os.path.splitext(file)
            if ext.lower() not in supported_extensions:
                continue
            
            current_files.add(relative_path)
            changes["total_scanned"] += 1
            
            try:
                stat = os.stat(file_path)
                modified_time = datetime.fromtimestamp(stat.st_mtime)
                file_size = stat.st_size
                
                # Calculate content hash
                with open(file_path, 'rb') as f:
                    content_hash = hashlib.md5(f.read()).hexdigest()
                
                existing_file = existing_files.get(relative_path)
                
                if existing_file is None:
                    # New file
                    vault_file = VaultFile(
                        vault_path=relative_path,
                        file_type=ext.lower()[1:],  # Remove the dot
                        content_hash=content_hash,
                        file_size=file_size,
                        modified_at=modified_time,
                        processing_status='unprocessed'
                    )
                    db.add(vault_file)
                    changes["new_files"].append(relative_path)
                    
                elif (existing_file.content_hash != content_hash or 
                      existing_file.modified_at != modified_time or
                      request.force_rescan):
                    # Modified file
                    existing_file.content_hash = content_hash
                    existing_file.file_size = file_size
                    existing_file.modified_at = modified_time
                    existing_file.updated_at = datetime.now()
                    
                    # Reset processing status if content changed
                    if existing_file.content_hash != content_hash:
                        existing_file.processing_status = 'unprocessed'
                        existing_file.error_message = None
                    
                    changes["modified_files"].append(relative_path)
                    
            except Exception as e:
                print(f"Error scanning file {relative_path}: {e}")
                continue
    
    # Find deleted files
    for vault_path in existing_files.keys():
        if vault_path not in current_files:
            db.delete(existing_files[vault_path])
            changes["deleted_files"].append(vault_path)
    
    db.commit()
    
    return {
        "message": "Vault scan completed",
        "changes": changes
    }

@router.post("/process")
async def process_vault_files(
    request: VaultProcessRequest,
    db: Session = Depends(get_db)
):
    """Queue files for processing"""
    
    processed_files = []
    failed_files = []
    
    for file_path in request.file_paths:
        vault_file = db.query(VaultFile).filter(VaultFile.vault_path == file_path).first()
        
        if not vault_file:
            failed_files.append({
                "path": file_path,
                "error": "File not found in vault database"
            })
            continue
        
        # Update status to queued
        vault_file.processing_status = 'queued'
        vault_file.error_message = None
        vault_file.updated_at = datetime.now()
        
        processed_files.append(file_path)
    
    db.commit()
    
    return {
        "message": f"Queued {len(processed_files)} files for processing",
        "processed_files": processed_files,
        "failed_files": failed_files
    }

@router.delete("/files/{file_id}")
async def remove_from_queue(
    file_id: str,
    db: Session = Depends(get_db)
):
    """Remove file from processing queue"""
    
    vault_file = db.query(VaultFile).filter(VaultFile.file_id == file_id).first()
    
    if not vault_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Only allow removal from queue if it's queued or has error
    if vault_file.processing_status not in ['queued', 'error']:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot remove file with status: {vault_file.processing_status}"
        )
    
    vault_file.processing_status = 'unprocessed'
    vault_file.error_message = None
    vault_file.updated_at = datetime.now()
    
    db.commit()
    
    return {"message": f"Removed {vault_file.vault_path} from queue"}

@router.get("/status", response_model=VaultStatusResponse)
async def get_vault_status(db: Session = Depends(get_db)):
    """Get processing status summary"""
    
    status_counts = db.execute("""
        SELECT processing_status, COUNT(*) as count
        FROM vault_files 
        GROUP BY processing_status
    """).fetchall()
    
    counts = {row[0]: row[1] for row in status_counts}
    total_files = sum(counts.values())
    
    # Get last scan time (most recent file creation)
    last_scan = db.execute("""
        SELECT MAX(created_at) FROM vault_files
    """).scalar()
    
    return VaultStatusResponse(
        total_files=total_files,
        processed=counts.get('processed', 0),
        queued=counts.get('queued', 0),
        processing=counts.get('processing', 0),
        unprocessed=counts.get('unprocessed', 0),
        error=counts.get('error', 0),
        last_scan=last_scan
    )

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