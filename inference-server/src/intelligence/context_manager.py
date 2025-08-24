"""
ContextManager - Handle context building with clean dependencies.

Separates context building logic from database access:
- Uses FileManager for vault file operations
- Uses HybridStore for semantic search
- Builds context pyramids with proper relevance ranking
- No direct database access - all through managers
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import hashlib

from ..database.manager import DatabaseManager, db_manager
from ..database.file_manager import FileManager, file_manager
from ..database.models import VaultFile
from ..storage.hybrid_store import HybridStore
from ..processors.embedder import Embedder
from .context_engine import ContextItem, ContextPyramid

logger = logging.getLogger(__name__)


class ContextManager:
    """Manage context building with clean separation of concerns."""
    
    def __init__(self, 
                 file_manager: FileManager = None,
                 hybrid_store: HybridStore = None,
                 embedder: Embedder = None):
        self.files = file_manager or file_manager
        self.store = hybrid_store
        self.embedder = embedder
        
        # Load routing config for token allocation
        from ..llm.utils.config_loader import ConfigLoader
        config_loader = ConfigLoader()
        routing_config = config_loader.load_config('configs/routing.yaml')
        self.token_allocation = routing_config['intelligence']['token_allocation']
    
    def build_context(self, 
                     query: str, 
                     current_file_path: str = None,
                     max_tokens: int = None,
                     mentioned_files: List[str] = None,
                     mentioned_folders: List[str] = None) -> ContextPyramid:
        """
        Build comprehensive context pyramid for intelligence queries.
        
        Args:
            query: User's query
            current_file_path: Path to current file (highest priority)
            max_tokens: Maximum tokens to use (calculated dynamically if None)
            mentioned_files: Files explicitly mentioned in query
            mentioned_folders: Folders explicitly mentioned in query
            
        Returns:
            ContextPyramid with relevance-ranked context items
        """
        max_tokens = max_tokens or self._calculate_context_tokens()
        mentioned_files = mentioned_files or []
        mentioned_folders = mentioned_folders or []
        
        items: List[ContextItem] = []
        used_tokens = 0
        
        logger.info(f"🏗️ Building context pyramid for query: '{query[:50]}...'")
        
        # Layer 1: Current note (highest priority)
        if current_file_path and used_tokens < max_tokens * 0.9:
            current_item = self._get_current_file_context(current_file_path)
            if current_item and used_tokens + current_item.token_count <= max_tokens * 0.4:
                items.append(current_item)
                used_tokens += current_item.token_count
                logger.info(f"📄 Added current file: {current_file_path} ({current_item.token_count} tokens)")
        
        # Layer 2: Explicitly mentioned files
        if mentioned_files and used_tokens < max_tokens * 0.8:
            mentioned_items = self._get_mentioned_files_context(mentioned_files)
            for item in mentioned_items:
                if used_tokens + item.token_count <= max_tokens * 0.6:
                    # Avoid duplicates
                    if not any(existing.source_path == item.source_path for existing in items):
                        items.append(item)
                        used_tokens += item.token_count
                        logger.info(f"📎 Added mentioned file: {item.source_path} ({item.token_count} tokens)")
        
        # Layer 3: Linked notes (from current note)
        if current_file_path and used_tokens < max_tokens * 0.8:
            linked_items = self._get_linked_files_context(current_file_path)
            for item in linked_items:
                if used_tokens + item.token_count <= max_tokens * 0.7:
                    # Avoid duplicates
                    if not any(existing.source_path == item.source_path for existing in items):
                        items.append(item)
                        used_tokens += item.token_count
                        logger.info(f"🔗 Added linked file: {item.source_path} ({item.token_count} tokens)")
                else:
                    break
        
        # Layer 4: Semantically similar notes
        if self.store and used_tokens < max_tokens * 0.9:
            similar_items = self._get_similar_files_context(query)
            for item in similar_items:
                if used_tokens + item.token_count <= max_tokens * 0.85:
                    # Avoid duplicates
                    if not any(existing.source_path == item.source_path for existing in items):
                        items.append(item)
                        used_tokens += item.token_count
                        logger.info(f"🎯 Added similar file: {item.source_path} ({item.token_count} tokens)")
                else:
                    break
        
        # Layer 5: Recent notes (temporal context)
        if used_tokens < max_tokens * 0.95:
            recent_items = self._get_recent_files_context()
            for item in recent_items:
                if used_tokens + item.token_count <= max_tokens * 0.95:
                    # Avoid duplicates
                    if not any(existing.source_path == item.source_path for existing in items):
                        items.append(item)
                        used_tokens += item.token_count
                        logger.info(f"🕒 Added recent file: {item.source_path} ({item.token_count} tokens)")
                else:
                    break
        
        truncated = used_tokens >= max_tokens * 0.95
        
        pyramid = ContextPyramid(
            items=items,
            total_tokens=used_tokens,
            truncated=truncated,
            current_note_path=current_file_path,
            query=query,
            built_at=datetime.now()
        )
        
        logger.info(f"✅ Context pyramid built: {len(items)} items, {used_tokens}/{max_tokens} tokens, truncated={truncated}")
        return pyramid
    
    def _calculate_context_tokens(self, model_name: str = None) -> int:
        """Calculate context token limit based on model's context window."""
        if not model_name:
            # Get routing config to find default model
            from ..llm.utils.config_loader import ConfigLoader
            config_loader = ConfigLoader()
            routing_config = config_loader.load_config('configs/routing.yaml')
            model_name = routing_config['rules']['chat_default']
        
        # Find adapter for model using routing rules
        adapter_name = None
        routing_config = config_loader.load_config('configs/routing.yaml')
        for rule in routing_config['rules']['explicit_models']:
            if model_name in rule['models']:
                adapter_name = rule['adapter']
                break
        
        if not adapter_name:
            raise ValueError(f"No adapter found for model {model_name}")
        
        # Load model config
        model_config = config_loader.load_config(f'configs/models/{adapter_name}/{model_name}.yaml')
        
        # Calculate context token limit
        context_window = model_config['context_window']
        context_window_ratio = self.token_allocation['context_window_ratio']
        context_tokens = int(context_window * context_window_ratio)
        
        logger.info(f"Context tokens: {context_tokens} (model: {model_name}, adapter: {adapter_name})")
        return context_tokens
    
    def _get_current_file_context(self, file_path: str) -> Optional[ContextItem]:
        """Get context from the current file with highest relevance."""
        vault_file = self.files.get_file(file_path)
        if not vault_file or vault_file.processing_status != 'processed':
            return None
        
        # For now, we'll need to get content from the file system or database
        # This is a simplified version - in practice you'd get the actual content
        content = f"Current file: {file_path}\nProcessing status: {vault_file.processing_status}"
        
        return ContextItem(
            content=content,
            source_path=file_path,
            relevance_score=1.0,  # Highest relevance
            context_type='current',
            token_count=self._estimate_tokens(content),
            metadata={
                'file_id': str(vault_file.file_id),
                'file_type': vault_file.file_type,
                'modified_at': vault_file.modified_at.isoformat() if vault_file.modified_at else None
            }
        )
    
    def _get_mentioned_files_context(self, mentioned_files: List[str]) -> List[ContextItem]:
        """Get context for explicitly mentioned files."""
        items = []
        
        for file_path in mentioned_files:
            vault_file = self.files.get_file(file_path)
            if vault_file and vault_file.processing_status == 'processed':
                content = f"Mentioned file: {file_path}\nProcessing status: {vault_file.processing_status}"
                
                item = ContextItem(
                    content=content,
                    source_path=file_path,
                    relevance_score=0.9,  # High relevance for mentioned files
                    context_type='mentioned',
                    token_count=self._estimate_tokens(content),
                    metadata={
                        'file_id': str(vault_file.file_id),
                        'file_type': vault_file.file_type
                    }
                )
                items.append(item)
        
        return items
    
    def _get_linked_files_context(self, current_file_path: str) -> List[ContextItem]:
        """Get context from files linked to the current file."""
        items = []
        
        # This is a simplified version - in practice you'd parse the file content
        # to find [[wikilinks]] and extract linked files
        # For now, return empty list
        logger.debug(f"Getting linked files for: {current_file_path}")
        
        return items
    
    def _get_similar_files_context(self, query: str) -> List[ContextItem]:
        """Get context from semantically similar files."""
        items = []
        
        if not self.store:
            logger.warning("No hybrid store available for semantic search")
            return items
        
        try:
            # Use hybrid store for semantic similarity
            results = self.store.search(
                query=query,
                k=8,  # Get more results than we might use
                alpha=0.8  # Favor semantic over keyword
            )
            
            logger.info(f"🔍 Found {len(results)} semantically similar notes")
            
            for result in results:
                doc_info = result.get("document", {})
                # Try to get actual file path, fall back to title
                source_path = (result.get("path") or 
                             doc_info.get("path") or 
                             doc_info.get("title", "Unknown"))
                
                # Calculate relevance based on similarity score
                similarity_score = result.get("score", 0.0)
                # Ensure score is a float
                if isinstance(similarity_score, str):
                    try:
                        similarity_score = float(similarity_score)
                    except (ValueError, TypeError):
                        similarity_score = 0.0
                relevance_score = min(0.7, similarity_score)  # Cap at 0.7 for similar notes
                
                token_count = self._estimate_tokens(result.get("text", ""))
                
                items.append(ContextItem(
                    content=result.get("text", ""),
                    source_path=source_path,
                    relevance_score=relevance_score,
                    context_type='similar',
                    token_count=token_count,
                    metadata={
                        'similarity_score': similarity_score,
                        'page': result.get('page'),
                        'document_id': doc_info.get('id')
                    }
                ))
                
        except Exception as e:
            logger.error(f"Error getting similar files: {e}")
            
        # Sort by relevance - ensure numeric comparison
        items.sort(key=lambda x: float(x.relevance_score) if x.relevance_score else 0.0, reverse=True)
        return items
    
    def _get_recent_files_context(self, days: int = 7) -> List[ContextItem]:
        """Get context from recently modified files."""
        items = []
        
        try:
            # Get recently updated files from file manager
            recent_files = self.files.list_files(
                status='processed',
                limit=5
            )
            
            for vault_file in recent_files:
                # Simple content for recent files
                content = f"Recent file: {vault_file.vault_path}\nLast modified: {vault_file.modified_at}"
                
                items.append(ContextItem(
                    content=content,
                    source_path=vault_file.vault_path,
                    relevance_score=0.3,  # Lower relevance for recency
                    context_type='recent',
                    token_count=self._estimate_tokens(content),
                    metadata={
                        'file_id': str(vault_file.file_id),
                        'modified_at': vault_file.modified_at.isoformat() if vault_file.modified_at else None
                    }
                ))
                
        except Exception as e:
            logger.error(f"Error getting recent files: {e}")
        
        return items
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars ≈ 1 token)."""
        return max(1, len(text) // 4)


# Global instance for easy access  
context_manager = ContextManager()