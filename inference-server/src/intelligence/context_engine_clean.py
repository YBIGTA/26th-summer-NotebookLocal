"""
Clean ContextEngine - Build relevance-ranked context pyramids using managers.

This version uses FileManager instead of direct database access to avoid
connection issues. It provides the same interface but with clean dependencies.
"""

import logging
from typing import List, Optional
from datetime import datetime

from ..database.file_manager import FileManager, file_manager
from ..storage.hybrid_store import HybridStore
from ..processors.embedder import Embedder
from ..llm.utils.config_loader import ConfigLoader
from .context_engine import ContextItem, ContextPyramid

logger = logging.getLogger(__name__)


class ContextEngineClean:
    """Build intelligent context pyramids using clean manager dependencies."""
    
    def __init__(self, hybrid_store: HybridStore, embedder: Embedder, file_manager: FileManager = None):
        self.store = hybrid_store
        self.embedder = embedder
        self.files = file_manager or file_manager
        
        # Load context config
        self.config_loader = ConfigLoader()
        self.intelligence_config = self.config_loader.load_config('configs/routing.yaml')
        self.token_allocation = self.intelligence_config['intelligence']['token_allocation']
    
    def _calculate_context_tokens(self, model_name: str = None) -> int:
        """Calculate context token limit based on model's context window."""
        if not model_name:
            model_name = self.intelligence_config['rules']['chat_default']
        
        # Find adapter for model using routing rules
        adapter_name = None
        for rule in self.intelligence_config['rules']['explicit_models']:
            if model_name in rule['models']:
                adapter_name = rule['adapter']
                break
        
        if not adapter_name:
            raise ValueError(f"No adapter found for model {model_name}")
        
        # Load model config
        model_config = self.config_loader.load_config(f'configs/models/{adapter_name}/{model_name}.yaml')
        
        # Calculate context token limit
        context_window = model_config['context_window']
        context_window_ratio = self.token_allocation['context_window_ratio']
        context_tokens = int(context_window * context_window_ratio)
        
        logger.info(f"Context tokens: {context_tokens} (model: {model_name}, adapter: {adapter_name})")
        return context_tokens
        
    async def build_context_pyramid(self,
                                   query: str,
                                   current_note_path: Optional[str] = None,
                                   vault_files: List = None,  # Ignored - we use FileManager
                                   max_tokens: Optional[int] = None,
                                   mentioned_files: List[str] = None,
                                   mentioned_folders: List[str] = None) -> ContextPyramid:
        """
        Build a context pyramid with relevance-ranked information.
        
        This is a clean implementation that uses FileManager and HybridStore
        instead of direct database access.
        """
        max_tokens = max_tokens or self._calculate_context_tokens()
        mentioned_files = mentioned_files or []
        mentioned_folders = mentioned_folders or []
        
        items: List[ContextItem] = []
        used_tokens = 0
        
        logger.info(f"🏗️ Building context pyramid for query: '{query[:50]}...'")
        
        # Layer 1: Current note (highest priority)
        if current_note_path and used_tokens < max_tokens * 0.9:
            current_item = await self._get_current_note_context(current_note_path)
            if current_item and used_tokens + current_item.token_count <= max_tokens * 0.4:
                items.append(current_item)
                used_tokens += current_item.token_count
                logger.info(f"📄 Added current file: {current_note_path} ({current_item.token_count} tokens)")
        
        # Layer 2: Explicitly mentioned files
        if mentioned_files and used_tokens < max_tokens * 0.8:
            for file_path in mentioned_files[:5]:  # Limit to avoid too many
                mentioned_item = await self._get_mentioned_file_context(file_path)
                if mentioned_item and used_tokens + mentioned_item.token_count <= max_tokens * 0.6:
                    if not any(existing.source_path == mentioned_item.source_path for existing in items):
                        items.append(mentioned_item)
                        used_tokens += mentioned_item.token_count
                        logger.info(f"📎 Added mentioned file: {file_path} ({mentioned_item.token_count} tokens)")
        
        # Layer 3: Semantically similar notes (using HybridStore)
        if self.store and used_tokens < max_tokens * 0.9:
            similar_items = await self._get_similar_notes_context(query)
            for item in similar_items:
                if used_tokens + item.token_count <= max_tokens * 0.85:
                    if not any(existing.source_path == item.source_path for existing in items):
                        items.append(item)
                        used_tokens += item.token_count
                        logger.info(f"🎯 Added similar note: {item.source_path} ({item.token_count} tokens)")
                else:
                    break
        
        # Layer 4: Recent notes (temporal context)
        if used_tokens < max_tokens * 0.95:
            recent_items = await self._get_recent_notes_context()
            for item in recent_items:
                if used_tokens + item.token_count <= max_tokens * 0.95:
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
            current_note_path=current_note_path,
            query=query,
            built_at=datetime.now()
        )
        
        logger.info(f"✅ Context pyramid built: {len(items)} items, {used_tokens}/{max_tokens} tokens, truncated={truncated}")
        return pyramid
    
    async def _get_current_note_context(self, note_path: str) -> Optional[ContextItem]:
        """Get context from the current note with highest relevance."""
        try:
            vault_file = self.files.get_file(note_path)
            
            if not vault_file or vault_file.processing_status != 'processed':
                logger.warning(f"Current file not available: {note_path}")
                return None
                
            # Create simple content from file metadata
            # TODO: In full implementation, get actual file content
            content = f"Current file: {note_path}\nType: {vault_file.file_type}\nSize: {vault_file.file_size} bytes\nModified: {vault_file.modified_at}"
            token_count = self._estimate_tokens(content)
            
            return ContextItem(
                content=content,
                source_path=note_path,
                relevance_score=1.0,  # Highest relevance
                context_type='current',
                token_count=token_count,
                metadata={
                    'file_id': str(vault_file.file_id),
                    'file_type': vault_file.file_type,
                    'file_size': vault_file.file_size,
                    'is_current': True
                }
            )
        except Exception as e:
            logger.error(f"Error getting current note context: {e}")
            return None
    
    async def _get_mentioned_file_context(self, file_path: str) -> Optional[ContextItem]:
        """Get context for explicitly mentioned file."""
        try:
            vault_file = self.files.get_file(file_path)
            
            if not vault_file or vault_file.processing_status != 'processed':
                logger.warning(f"Mentioned file not available: {file_path}")
                return None
                
            content = f"Mentioned file: {file_path}\nType: {vault_file.file_type}\nSize: {vault_file.file_size} bytes"
            token_count = self._estimate_tokens(content)
            
            return ContextItem(
                content=content,
                source_path=file_path,
                relevance_score=0.9,  # High relevance for mentioned files
                context_type='mentioned',
                token_count=token_count,
                metadata={
                    'file_id': str(vault_file.file_id),
                    'explicitly_mentioned': True
                }
            )
        except Exception as e:
            logger.error(f"Error getting mentioned file context: {e}")
            return None
    
    async def _get_similar_notes_context(self, query: str) -> List[ContextItem]:
        """Find notes similar to the query using semantic search."""
        items = []
        
        if not self.store:
            logger.warning("No hybrid store available for semantic search")
            return items
        
        try:
            results = self.store.search(
                query=query,
                k=8,
                alpha=0.8  # Favor semantic over keyword
            )
            
            logger.info(f"🔍 Found {len(results)} semantically similar notes")
            
            for result in results:
                doc_info = result.get("document", {})
                source_path = (result.get("path") or 
                             doc_info.get("path") or 
                             doc_info.get("title", "Unknown"))
                
                # Calculate relevance based on similarity score
                similarity_score = result.get("score", 0.0)
                if isinstance(similarity_score, str):
                    try:
                        similarity_score = float(similarity_score)
                    except (ValueError, TypeError):
                        similarity_score = 0.0
                
                relevance_score = min(0.7, similarity_score)
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
            logger.error(f"Error getting similar notes: {e}")
            
        # Sort by relevance
        items.sort(key=lambda x: float(x.relevance_score) if x.relevance_score else 0.0, reverse=True)
        return items
    
    async def _get_recent_notes_context(self) -> List[ContextItem]:
        """Get recently modified notes for temporal context."""
        items = []
        
        try:
            recent_files = self.files.list_files(
                status='processed',
                limit=5
            )
            
            for vault_file in recent_files:
                content = f"Recent file: {vault_file.vault_path}\nModified: {vault_file.modified_at}"
                token_count = self._estimate_tokens(content)
                
                items.append(ContextItem(
                    content=content,
                    source_path=vault_file.vault_path,
                    relevance_score=0.3,  # Lower relevance for recency
                    context_type='recent',
                    token_count=token_count,
                    metadata={
                        'file_id': str(vault_file.file_id),
                        'modified_at': vault_file.modified_at.isoformat() if vault_file.modified_at else None
                    }
                ))
                
        except Exception as e:
            logger.error(f"Error getting recent notes: {e}")
        
        return items
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars ≈ 1 token)."""
        return max(1, len(text) // 4)


# Create a clean global instance
context_engine_clean = ContextEngineClean(None, None)