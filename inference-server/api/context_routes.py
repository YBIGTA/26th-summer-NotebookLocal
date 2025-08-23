"""
RAG Context management API routes

Endpoints:
- POST /api/v1/rag/context/set - Set RAG context scope and selection
- GET /api/v1/rag/context - Get current RAG context
- POST /api/v1/rag/context/validate - Validate context selection
- POST /api/v1/rag/context/parse-command - Parse and validate commands
- GET /api/v1/rag/context/autocomplete - Get autocomplete suggestions
- POST /api/v1/rag/search - Context-aware search with RAG
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
from pydantic import BaseModel

from src.database.connection import get_db
from src.database.models import VaultFile, Document, Chunk

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])

# Request/Response Models
class RagContextRequest(BaseModel):
    enabled: bool
    scope: str  # 'whole', 'selected', 'folder'
    selected_files: List[str] = []
    selected_folders: List[str] = []
    selected_tags: List[str] = []
    temporal_filters: Dict[str, Any] = {}

class RagContextResponse(BaseModel):
    enabled: bool
    scope: str
    selected_files: List[str]
    selected_folders: List[str]
    selected_tags: List[str]
    temporal_filters: Dict[str, Any]
    last_updated: datetime
    file_count: int
    processed_file_count: int

class ContextValidationRequest(BaseModel):
    context: RagContextRequest

class ContextValidationResponse(BaseModel):
    is_valid: bool
    warnings: List[str]
    errors: List[str]
    stats: Dict[str, Union[int, float]]

class CommandParseRequest(BaseModel):
    command: str
    context: Optional[RagContextRequest] = None

class CommandParseResponse(BaseModel):
    command_type: str  # 'slash' or 'mention'
    parsed_command: str
    arguments: List[str]
    is_valid: bool
    result: Optional[str] = None
    error: Optional[str] = None

class AutocompleteRequest(BaseModel):
    query: str
    context_type: str  # 'file', 'folder', 'tag', 'command'
    limit: int = 10

class AutocompleteResponse(BaseModel):
    suggestions: List[Dict[str, Any]]

class RagSearchRequest(BaseModel):
    query: str
    context: RagContextRequest
    limit: int = 5
    similarity_threshold: float = 0.7

class RagSearchResponse(BaseModel):
    results: List[Dict[str, Any]]
    context_info: Dict[str, Any]

# Global context storage (in production, use Redis or database)
_current_context: Optional[RagContextRequest] = None

@router.post("/context/set")
async def set_rag_context(
    context: RagContextRequest,
    db: Session = Depends(get_db)
):
    """Set RAG context scope and selection"""
    
    global _current_context
    
    # Validate file paths exist in database
    if context.selected_files:
        existing_files = db.query(VaultFile.vault_path).filter(
            VaultFile.vault_path.in_(context.selected_files)
        ).all()
        existing_paths = {f[0] for f in existing_files}
        
        missing_files = set(context.selected_files) - existing_paths
        if missing_files:
            raise HTTPException(
                status_code=400,
                detail=f"Files not found: {list(missing_files)}"
            )
    
    # Store context (in production, associate with user session)
    _current_context = context
    
    # Get file count statistics
    file_count = 0
    processed_file_count = 0
    
    if context.scope == 'whole':
        file_count = db.query(VaultFile).count()
        processed_file_count = db.query(VaultFile).filter(
            VaultFile.processing_status == 'processed'
        ).count()
    elif context.scope == 'selected':
        all_selected_files = set(context.selected_files)
        
        # Add files from selected folders
        if context.selected_folders:
            folder_files = db.query(VaultFile).filter(
                VaultFile.vault_path.like(
                    db.func.any(f"{folder}%" for folder in context.selected_folders)
                )
            ).all()
            all_selected_files.update(f.vault_path for f in folder_files)
        
        file_count = len(all_selected_files)
        if all_selected_files:
            processed_file_count = db.query(VaultFile).filter(
                VaultFile.vault_path.in_(all_selected_files),
                VaultFile.processing_status == 'processed'
            ).count()
    
    return {
        "message": "RAG context updated successfully",
        "context": RagContextResponse(
            enabled=context.enabled,
            scope=context.scope,
            selected_files=context.selected_files,
            selected_folders=context.selected_folders,
            selected_tags=context.selected_tags,
            temporal_filters=context.temporal_filters,
            last_updated=datetime.now(),
            file_count=file_count,
            processed_file_count=processed_file_count
        )
    }

@router.get("/context", response_model=RagContextResponse)
async def get_rag_context(db: Session = Depends(get_db)):
    """Get current RAG context"""
    
    global _current_context
    
    if _current_context is None:
        # Return default context
        return RagContextResponse(
            enabled=False,
            scope='whole',
            selected_files=[],
            selected_folders=[],
            selected_tags=[],
            temporal_filters={},
            last_updated=datetime.now(),
            file_count=0,
            processed_file_count=0
        )
    
    # Calculate current file counts
    file_count = 0
    processed_file_count = 0
    
    if _current_context.scope == 'whole':
        file_count = db.query(VaultFile).count()
        processed_file_count = db.query(VaultFile).filter(
            VaultFile.processing_status == 'processed'
        ).count()
    elif _current_context.scope == 'selected':
        all_selected_files = set(_current_context.selected_files)
        
        # Add files from selected folders
        if _current_context.selected_folders:
            folder_files = db.query(VaultFile).filter(
                VaultFile.vault_path.like(
                    db.func.any(f"{folder}%" for folder in _current_context.selected_folders)
                )
            ).all()
            all_selected_files.update(f.vault_path for f in folder_files)
        
        file_count = len(all_selected_files)
        if all_selected_files:
            processed_file_count = db.query(VaultFile).filter(
                VaultFile.vault_path.in_(all_selected_files),
                VaultFile.processing_status == 'processed'
            ).count()
    
    return RagContextResponse(
        enabled=_current_context.enabled,
        scope=_current_context.scope,
        selected_files=_current_context.selected_files,
        selected_folders=_current_context.selected_folders,
        selected_tags=_current_context.selected_tags,
        temporal_filters=_current_context.temporal_filters,
        last_updated=datetime.now(),
        file_count=file_count,
        processed_file_count=processed_file_count
    )

@router.post("/context/validate", response_model=ContextValidationResponse)
async def validate_context(
    request: ContextValidationRequest,
    db: Session = Depends(get_db)
):
    """Validate RAG context selection"""
    
    context = request.context
    warnings = []
    errors = []
    stats = {}
    
    # Validate selected files
    if context.selected_files:
        existing_files = db.query(VaultFile).filter(
            VaultFile.vault_path.in_(context.selected_files)
        ).all()
        
        existing_paths = {f.vault_path for f in existing_files}
        missing_files = set(context.selected_files) - existing_paths
        
        if missing_files:
            errors.extend([f"File not found: {path}" for path in missing_files])
        
        # Check processing status
        unprocessed_files = [f for f in existing_files if f.processing_status != 'processed']
        if unprocessed_files:
            warnings.append(f"{len(unprocessed_files)} files are not processed yet")
        
        stats['selected_files_total'] = len(context.selected_files)
        stats['selected_files_existing'] = len(existing_files)
        stats['selected_files_processed'] = len(existing_files) - len(unprocessed_files)
    
    # Validate folders
    if context.selected_folders:
        folder_file_count = 0
        folder_processed_count = 0
        
        for folder in context.selected_folders:
            folder_files = db.query(VaultFile).filter(
                VaultFile.vault_path.like(f"{folder}%")
            ).all()
            
            if not folder_files:
                warnings.append(f"No files found in folder: {folder}")
            else:
                folder_file_count += len(folder_files)
                folder_processed_count += len([f for f in folder_files if f.processing_status == 'processed'])
        
        stats['folder_files_total'] = folder_file_count
        stats['folder_files_processed'] = folder_processed_count
        
        if folder_file_count > folder_processed_count:
            warnings.append(f"{folder_file_count - folder_processed_count} folder files are not processed")
    
    # Calculate total context size
    total_files = 0
    total_processed = 0
    estimated_tokens = 0
    
    if context.scope == 'whole':
        total_files = db.query(VaultFile).count()
        total_processed = db.query(VaultFile).filter(
            VaultFile.processing_status == 'processed'
        ).count()
        
        # Rough token estimation (1 token ≈ 4 characters, average file ~2000 chars)
        estimated_tokens = total_processed * 500  # 500 tokens per file average
        
    elif context.scope == 'selected':
        total_files = stats.get('selected_files_total', 0) + stats.get('folder_files_total', 0)
        total_processed = stats.get('selected_files_processed', 0) + stats.get('folder_files_processed', 0)
        estimated_tokens = total_processed * 500
    
    stats['total_files'] = total_files
    stats['total_processed'] = total_processed
    stats['estimated_tokens'] = estimated_tokens
    
    # Add warnings for large contexts
    if estimated_tokens > 50000:
        warnings.append(f"Large context size (~{estimated_tokens:,} tokens)")
    
    if total_files > 100:
        warnings.append(f"Large number of files ({total_files})")
    
    # Determine if context is valid
    is_valid = len(errors) == 0 and total_processed > 0
    
    if total_processed == 0:
        errors.append("No processed files in context")
    
    return ContextValidationResponse(
        is_valid=is_valid,
        warnings=warnings,
        errors=errors,
        stats=stats
    )

@router.post("/context/parse-command", response_model=CommandParseResponse)
async def parse_command(request: CommandParseRequest):
    """Parse and validate slash commands or @ mentions"""
    
    command = request.command.strip()
    
    if command.startswith('/'):
        # Slash command
        parts = command[1:].split()
        if not parts:
            return CommandParseResponse(
                command_type='slash',
                parsed_command='',
                arguments=[],
                is_valid=False,
                error='Empty command'
            )
        
        cmd = parts[0]
        args = parts[1:] if len(parts) > 1 else []
        
        # Validate command
        supported_commands = {
            'rag-toggle': 'Toggle RAG on/off',
            'rag-enable': 'Enable RAG',
            'rag-disable': 'Disable RAG',
            'rag-scope': 'Set RAG scope (whole|selected|folder)',
            'rag-clear': 'Clear RAG context',
            'rag-status': 'Show RAG status',
            'process-file': 'Queue file for processing',
            'process-folder': 'Queue folder for processing',
            'reindex-vault': 'Rebuild entire index',
            'show-files': 'Show file processing status',
            'show-queue': 'Show processing queue'
        }
        
        if cmd not in supported_commands:
            return CommandParseResponse(
                command_type='slash',
                parsed_command=cmd,
                arguments=args,
                is_valid=False,
                error=f'Unknown command: {cmd}'
            )
        
        return CommandParseResponse(
            command_type='slash',
            parsed_command=cmd,
            arguments=args,
            is_valid=True,
            result=f'Valid command: {supported_commands[cmd]}'
        )
    
    elif command.startswith('@'):
        # @ mention
        mention = command[1:]
        
        if mention.startswith('#'):
            # Tag mention
            tag = mention[1:]
            return CommandParseResponse(
                command_type='mention',
                parsed_command=f'tag:{tag}',
                arguments=[tag],
                is_valid=True,
                result=f'Tag mention: #{tag}'
            )
        elif mention.endswith('/'):
            # Folder mention
            folder = mention[:-1]
            return CommandParseResponse(
                command_type='mention',
                parsed_command=f'folder:{folder}',
                arguments=[folder],
                is_valid=True,
                result=f'Folder mention: {folder}/'
            )
        elif mention in ['recent', 'active', 'current', 'all']:
            # Special mention
            return CommandParseResponse(
                command_type='mention',
                parsed_command=f'special:{mention}',
                arguments=[mention],
                is_valid=True,
                result=f'Special mention: @{mention}'
            )
        else:
            # File mention
            return CommandParseResponse(
                command_type='mention',
                parsed_command=f'file:{mention}',
                arguments=[mention],
                is_valid=True,
                result=f'File mention: {mention}'
            )
    
    return CommandParseResponse(
        command_type='unknown',
        parsed_command=command,
        arguments=[],
        is_valid=False,
        error='Command must start with / or @'
    )

@router.post("/context/autocomplete", response_model=AutocompleteResponse)
async def get_autocomplete_suggestions(
    request: AutocompleteRequest,
    db: Session = Depends(get_db)
):
    """Get autocomplete suggestions for commands or file/folder names"""
    
    suggestions = []
    query = request.query.lower()
    
    if request.context_type == 'command':
        # Command suggestions
        commands = [
            {'command': 'rag-toggle', 'description': 'Toggle RAG on/off'},
            {'command': 'rag-enable', 'description': 'Enable RAG'},
            {'command': 'rag-disable', 'description': 'Disable RAG'},
            {'command': 'rag-scope', 'description': 'Set RAG scope'},
            {'command': 'rag-clear', 'description': 'Clear RAG context'},
            {'command': 'rag-status', 'description': 'Show RAG status'},
            {'command': 'process-file', 'description': 'Queue file for processing'},
            {'command': 'process-folder', 'description': 'Queue folder for processing'},
            {'command': 'reindex-vault', 'description': 'Rebuild entire index'},
            {'command': 'show-files', 'description': 'Show file processing status'},
            {'command': 'show-queue', 'description': 'Show processing queue'}
        ]
        
        suggestions = [
            {
                'type': 'command',
                'label': f"/{cmd['command']}",
                'description': cmd['description'],
                'icon': '⚡'
            }
            for cmd in commands
            if query in cmd['command'] or query in cmd['description'].lower()
        ][:request.limit]
    
    elif request.context_type == 'file':
        # File suggestions
        files = db.query(VaultFile).filter(
            VaultFile.vault_path.ilike(f"%{query}%")
        ).limit(request.limit).all()
        
        suggestions = [
            {
                'type': 'file',
                'label': f"@{os.path.basename(f.vault_path)}",
                'description': f.vault_path,
                'processing_status': f.processing_status,
                'icon': '📄'
            }
            for f in files
        ]
    
    elif request.context_type == 'folder':
        # Folder suggestions (extract from file paths)
        folders = set()
        files = db.query(VaultFile.vault_path).filter(
            VaultFile.vault_path.ilike(f"%{query}%")
        ).limit(request.limit * 2).all()  # Get more to extract folders
        
        for (file_path,) in files:
            parts = file_path.split('/')
            for i in range(1, len(parts)):
                folder_path = '/'.join(parts[:i])
                if query in folder_path.lower():
                    folders.add(folder_path)
        
        suggestions = [
            {
                'type': 'folder',
                'label': f"@{folder}/",
                'description': folder,
                'icon': '📁'
            }
            for folder in list(folders)[:request.limit]
        ]
    
    elif request.context_type == 'special':
        # Special mentions
        specials = [
            {'name': 'recent', 'description': 'Recently modified files'},
            {'name': 'active', 'description': 'Currently active file'},
            {'name': 'current', 'description': 'Current file in editor'},
            {'name': 'all', 'description': 'All files in vault'}
        ]
        
        suggestions = [
            {
                'type': 'special',
                'label': f"@{special['name']}",
                'description': special['description'],
                'icon': '⭐'
            }
            for special in specials
            if query in special['name'] or query in special['description'].lower()
        ][:request.limit]
    
    return AutocompleteResponse(suggestions=suggestions)

@router.post("/search", response_model=RagSearchResponse)
async def context_aware_search(
    request: RagSearchRequest,
    db: Session = Depends(get_db)
):
    """Perform context-aware search using RAG"""
    
    results = []
    context_info = {
        'files_searched': 0,
        'context_scope': request.context.scope,
        'enabled': request.context.enabled
    }
    
    if not request.context.enabled:
        return RagSearchResponse(
            results=[],
            context_info={'error': 'RAG is disabled', **context_info}
        )
    
    # Get files in context
    context_files = []
    
    if request.context.scope == 'whole':
        context_files = db.query(VaultFile).filter(
            VaultFile.processing_status == 'processed'
        ).all()
    elif request.context.scope == 'selected':
        file_paths = set(request.context.selected_files)
        
        # Add files from folders
        for folder in request.context.selected_folders:
            folder_files = db.query(VaultFile).filter(
                VaultFile.vault_path.like(f"{folder}%"),
                VaultFile.processing_status == 'processed'
            ).all()
            file_paths.update(f.vault_path for f in folder_files)
        
        if file_paths:
            context_files = db.query(VaultFile).filter(
                VaultFile.vault_path.in_(file_paths),
                VaultFile.processing_status == 'processed'
            ).all()
    
    context_info['files_searched'] = len(context_files)
    
    if not context_files:
        return RagSearchResponse(
            results=[],
            context_info={'error': 'No processed files in context', **context_info}
        )
    
    # Get document UIDs for context files
    doc_uids = [f.doc_uid for f in context_files if f.doc_uid]
    
    if not doc_uids:
        return RagSearchResponse(
            results=[],
            context_info={'error': 'No processed documents found', **context_info}
        )
    
    # Search in chunks (simplified - would use vector search in production)
    search_pattern = f"%{request.query}%"
    chunks = db.query(Chunk, Document).join(Document).filter(
        Document.doc_uid.in_(doc_uids),
        Chunk.text.ilike(search_pattern)
    ).limit(request.limit).all()
    
    results = [
        {
            'chunk_id': str(chunk.chunk_id),
            'document_title': document.title,
            'document_path': document.path,
            'content': chunk.text[:500] + '...' if len(chunk.text) > 500 else chunk.text,
            'score': 1.0,  # Placeholder score
            'page': chunk.page,
            'section': chunk.section
        }
        for chunk, document in chunks
    ]
    
    return RagSearchResponse(
        results=results,
        context_info=context_info
    )