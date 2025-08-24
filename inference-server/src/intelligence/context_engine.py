"""
ContextEngine - Build relevance-ranked context pyramids for intelligent responses.

Core concept: Build a "context pyramid" where most relevant information is at the top,
less relevant below. Current note gets highest priority, linked notes come next,
similar notes by content/tags follow, recent notes provide temporal context.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib

from ..database.models import VaultFile
from ..database.connection import get_db_connection
from ..storage.hybrid_store import HybridStore
from ..processors.embedder import Embedder
from ..llm.utils.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

@dataclass
class ContextItem:
    """Single item in the context pyramid."""
    content: str
    source_path: str
    relevance_score: float
    context_type: str  # 'current', 'linked', 'similar', 'recent', 'tagged'
    token_count: int
    metadata: Dict[str, Any]

@dataclass
class ContextPyramid:
    """Structured context with relevance ranking."""
    items: List[ContextItem]
    total_tokens: int
    truncated: bool
    current_note_path: Optional[str]
    query: str
    built_at: datetime

class ContextEngine:
    """Build intelligent context pyramids for vault queries."""
    
    def __init__(self, hybrid_store: HybridStore, embedder: Embedder):
        self.store = hybrid_store
        self.embedder = embedder
        
        # Load context config
        self.config_loader = ConfigLoader()
        self.intelligence_config = self.config_loader.load_config('configs/routing.yaml')
        self.context_config = self.intelligence_config['context']
        self.max_tokens = self.context_config.get('max_tokens', 8000)
        
    async def build_context_pyramid(
        self,
        query: str,
        current_note_path: Optional[str] = None,
        vault_files: List[VaultFile] = None,
        max_tokens: Optional[int] = None,
        mentioned_files: List[str] = None,
        mentioned_folders: List[str] = None
    ) -> ContextPyramid:
        """
        Build a context pyramid with relevance-ranked information.
        
        Priority order:
        1. Current note (highest priority)
        2. Linked notes from current note
        3. Semantically similar notes
        4. Recent notes (temporal context)
        5. Notes with shared tags
        """
        max_tokens = max_tokens or self.max_tokens
        items: List[ContextItem] = []
        used_tokens = 0
        mentioned_files = mentioned_files or []
        mentioned_folders = mentioned_folders or []
        
        logger.info(f"🏗️ Building context pyramid for query: '{query[:50]}...'")
        if mentioned_files:
            logger.info(f"📎 With mentioned files: {mentioned_files}")
        if mentioned_folders:
            logger.info(f"📂 With mentioned folders: {mentioned_folders}")
        
        # Layer 0: Explicitly mentioned files (highest priority)
        for file_path in mentioned_files:
            if used_tokens >= max_tokens * 0.6:  # Reserve 40% for other layers
                break
            mentioned_item = await self._get_mentioned_file_context(file_path)
            if mentioned_item and used_tokens + mentioned_item.token_count <= max_tokens * 0.6:
                items.append(mentioned_item)
                used_tokens += mentioned_item.token_count
                logger.info(f"📎 Added mentioned file: {file_path} ({mentioned_item.token_count} tokens)")
        
        # Layer 0.5: Explicitly mentioned folders
        for folder_path in mentioned_folders:
            if used_tokens >= max_tokens * 0.7:  # Reserve 30% for other layers
                break
            folder_items = await self._get_mentioned_folder_context(folder_path)
            for folder_item in folder_items[:3]:  # Limit folder items
                if used_tokens + folder_item.token_count <= max_tokens * 0.7:
                    items.append(folder_item)
                    used_tokens += folder_item.token_count
                    logger.info(f"📂 Added from mentioned folder: {folder_item.source_path} ({folder_item.token_count} tokens)")
                else:
                    break
        
        # Layer 1: Current note (high priority)
        if current_note_path and used_tokens < max_tokens * 0.8:
            current_item = await self._get_current_note_context(current_note_path)
            if current_item and used_tokens + current_item.token_count <= max_tokens * 0.8:
                # Don't duplicate if already mentioned
                if not any(item.source_path == current_note_path for item in items):
                    items.append(current_item)
                    used_tokens += current_item.token_count
                    logger.info(f"📄 Added current note: {current_note_path} ({current_item.token_count} tokens)")
        
        # Layer 2: Linked notes (medium-high priority)
        if current_note_path and used_tokens < max_tokens * 0.7:  # Reserve 30% for other layers
            linked_items = await self._get_linked_notes_context(current_note_path, vault_files)
            for item in linked_items:
                if used_tokens + item.token_count <= max_tokens * 0.7:
                    items.append(item)
                    used_tokens += item.token_count
                    logger.info(f"🔗 Added linked note: {item.source_path} ({item.token_count} tokens)")
                else:
                    break
        
        # Layer 3: Semantically similar notes (medium priority)
        if used_tokens < max_tokens * 0.8:  # Reserve 20% for temporal context
            similar_items = await self._get_similar_notes_context(query, vault_files)
            for item in similar_items:
                if used_tokens + item.token_count <= max_tokens * 0.8:
                    # Avoid duplicates
                    if not any(existing.source_path == item.source_path for existing in items):
                        items.append(item)
                        used_tokens += item.token_count
                        logger.info(f"🎯 Added similar note: {item.source_path} ({item.token_count} tokens)")
                else:
                    break
        
        # Layer 4: Recent notes (temporal context)
        if used_tokens < max_tokens * 0.9:  # Reserve 10% buffer
            recent_items = await self._get_recent_notes_context(vault_files)
            for item in recent_items:
                if used_tokens + item.token_count <= max_tokens * 0.9:
                    # Avoid duplicates
                    if not any(existing.source_path == item.source_path for existing in items):
                        items.append(item)
                        used_tokens += item.token_count
                        logger.info(f"🕒 Added recent note: {item.source_path} ({item.token_count} tokens)")
                else:
                    break
        
        # Layer 5: Tagged notes (if space remains)
        if current_note_path and used_tokens < max_tokens * 0.95:
            tagged_items = await self._get_tagged_notes_context(current_note_path, vault_files)
            for item in tagged_items:
                if used_tokens + item.token_count <= max_tokens * 0.95:
                    # Avoid duplicates
                    if not any(existing.source_path == item.source_path for existing in items):
                        items.append(item)
                        used_tokens += item.token_count
                        logger.info(f"🏷️ Added tagged note: {item.source_path} ({item.token_count} tokens)")
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
            # Query the database for this specific file
            from ..database.connection import get_db_connection
            
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT content, file_size, modified_at FROM vault_files WHERE vault_path = %s AND processing_status = 'processed'",
                    (note_path,)
                )
                result = cursor.fetchone()
                
                if not result:
                    return None
                
                content, file_size, modified_at = result
                token_count = self._estimate_tokens(content)
                
                return ContextItem(
                    content=content,
                    source_path=note_path,
                    relevance_score=1.0,  # Highest possible relevance
                    context_type='current',
                    token_count=token_count,
                    metadata={
                        'file_size': file_size,
                        'modified_at': modified_at,
                        'is_current': True
                    }
                )
                
        except Exception as e:
            logger.error(f"Error getting current note context for {note_path}: {e}")
            return None
    
    async def _get_linked_notes_context(self, current_path: str, vault_files: List[VaultFile]) -> List[ContextItem]:
        """Find notes linked from the current note."""
        items = []
        
        try:
            # Get current note content to extract links
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT content FROM vault_files WHERE vault_path = %s",
                    (current_path,)
                )
                result = cursor.fetchone()
                
                if not result:
                    return items
                
                content = result[0]
                
                # Extract [[wikilinks]] from content
                import re
                link_pattern = r'\[\[([^\]]+)\]\]'
                links = re.findall(link_pattern, content)
                
                logger.info(f"🔍 Found {len(links)} links in current note")
                
                # Find linked files in vault
                for link in links[:10]:  # Limit to avoid too many links
                    # Try to find the linked file
                    linked_item = await self._find_linked_file_context(link, vault_files)
                    if linked_item:
                        items.append(linked_item)
                        
        except Exception as e:
            logger.error(f"Error getting linked notes for {current_path}: {e}")
            
        # Sort by relevance and return
        items.sort(key=lambda x: x.relevance_score, reverse=True)
        return items
    
    async def _find_linked_file_context(self, link_text: str, vault_files: List[VaultFile]) -> Optional[ContextItem]:
        """Find a specific linked file and create context item."""
        try:
            # Try different variations of the link
            possible_paths = [
                link_text,
                f"{link_text}.md",
                link_text.split('|')[0],  # Handle [[file|alias]] format
                f"{link_text.split('|')[0]}.md"
            ]
            
            for path in possible_paths:
                # Query database for this file
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT content, file_size, modified_at FROM vault_files WHERE vault_path LIKE %s AND processing_status = 'processed'",
                        (f"%{path}",)
                    )
                    result = cursor.fetchone()
                    
                    if result:
                        content, file_size, modified_at = result
                        token_count = self._estimate_tokens(content)
                        
                        return ContextItem(
                            content=content,
                            source_path=path,
                            relevance_score=0.8,  # High relevance for linked notes
                            context_type='linked',
                            token_count=token_count,
                            metadata={
                                'file_size': file_size,
                                'modified_at': modified_at,
                                'link_text': link_text
                            }
                        )
                        
        except Exception as e:
            logger.error(f"Error finding linked file {link_text}: {e}")
            
        return None
    
    async def _get_similar_notes_context(self, query: str, vault_files: List[VaultFile]) -> List[ContextItem]:
        """Find notes similar to the query using semantic search."""
        items = []
        
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
                source_path = doc_info.get("title", "Unknown")
                
                # Calculate relevance based on similarity score
                similarity_score = result.get("score", 0.0)
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
            logger.error(f"Error getting similar notes: {e}")
            
        # Sort by relevance
        items.sort(key=lambda x: x.relevance_score, reverse=True)
        return items
    
    async def _get_recent_notes_context(self, vault_files: List[VaultFile]) -> List[ContextItem]:
        """Get recently modified notes for temporal context."""
        items = []
        
        try:
            # Get files modified in last 7 days
            cutoff_date = datetime.now() - timedelta(days=7)
            
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT vault_path, content, file_size, modified_at 
                    FROM vault_files 
                    WHERE modified_at > %s 
                    AND processing_status = 'processed'
                    ORDER BY modified_at DESC 
                    LIMIT 5
                """, (cutoff_date,))
                
                results = cursor.fetchall()
                logger.info(f"🕒 Found {len(results)} recent notes")
                
                for vault_path, content, file_size, modified_at in results:
                    token_count = self._estimate_tokens(content)
                    
                    # Calculate relevance based on recency
                    days_ago = (datetime.now() - modified_at).days
                    relevance_score = max(0.2, 0.6 - (days_ago * 0.1))  # Decay over time
                    
                    items.append(ContextItem(
                        content=content,
                        source_path=vault_path,
                        relevance_score=relevance_score,
                        context_type='recent',
                        token_count=token_count,
                        metadata={
                            'modified_at': modified_at,
                            'days_ago': days_ago,
                            'file_size': file_size
                        }
                    ))
                    
        except Exception as e:
            logger.error(f"Error getting recent notes: {e}")
            
        return items
    
    async def _get_tagged_notes_context(self, current_path: str, vault_files: List[VaultFile]) -> List[ContextItem]:
        """Get notes with similar tags to current note."""
        items = []
        
        try:
            # Extract tags from current note
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT content FROM vault_files WHERE vault_path = %s",
                    (current_path,)
                )
                result = cursor.fetchone()
                
                if not result:
                    return items
                
                content = result[0]
                
                # Extract #tags from content
                import re
                tag_pattern = r'#(\w+)'
                tags = set(re.findall(tag_pattern, content))
                
                if not tags:
                    return items
                
                logger.info(f"🏷️ Found tags in current note: {tags}")
                
                # Find other notes with these tags
                for tag in list(tags)[:3]:  # Limit to 3 most important tags
                    cursor.execute("""
                        SELECT vault_path, content, file_size, modified_at 
                        FROM vault_files 
                        WHERE content LIKE %s 
                        AND vault_path != %s
                        AND processing_status = 'processed'
                        LIMIT 3
                    """, (f"%#{tag}%", current_path))
                    
                    tag_results = cursor.fetchall()
                    
                    for vault_path, content, file_size, modified_at in tag_results:
                        token_count = self._estimate_tokens(content)
                        
                        items.append(ContextItem(
                            content=content,
                            source_path=vault_path,
                            relevance_score=0.5,  # Medium relevance for shared tags
                            context_type='tagged',
                            token_count=token_count,
                            metadata={
                                'shared_tag': tag,
                                'modified_at': modified_at,
                                'file_size': file_size
                            }
                        ))
                        
        except Exception as e:
            logger.error(f"Error getting tagged notes: {e}")
            
        return items
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (1 token ≈ 4 characters)."""
        return max(1, len(text) // 4)
    
    def format_context_for_llm(self, pyramid: ContextPyramid) -> str:
        """Format context pyramid for LLM consumption."""
        if not pyramid.items:
            return ""
        
        sections = []
        
        # Group items by context type
        by_type = {}
        for item in pyramid.items:
            if item.context_type not in by_type:
                by_type[item.context_type] = []
            by_type[item.context_type].append(item)
        
        # Format each section with appropriate priority
        type_labels = {
            'current': '📄 Current Note',
            'linked': '🔗 Linked Notes', 
            'similar': '🎯 Related Notes',
            'recent': '🕒 Recent Notes',
            'tagged': '🏷️ Tagged Notes'
        }
        
        for context_type in ['current', 'linked', 'similar', 'recent', 'tagged']:
            if context_type in by_type:
                sections.append(f"\n=== {type_labels[context_type]} ===")
                
                for item in by_type[context_type]:
                    sections.append(f"\n--- {item.source_path} (relevance: {item.relevance_score:.2f}) ---")
                    sections.append(item.content)
        
        context_text = '\n'.join(sections)
        
        # Add metadata footer
        footer = f"\n\n=== Context Summary ===\n"
        footer += f"Query: {pyramid.query}\n"
        footer += f"Total items: {len(pyramid.items)}\n"
        footer += f"Total tokens: {pyramid.total_tokens}\n"
        footer += f"Truncated: {pyramid.truncated}\n"
        footer += f"Built at: {pyramid.built_at.strftime('%Y-%m-%d %H:%M:%S')}"
        
        return context_text + footer
    
    def get_context_sources(self, pyramid: ContextPyramid) -> List[str]:
        """Extract source citations from context pyramid."""
        sources = []
        
        for item in pyramid.items:
            source_label = f"[{item.source_path}]"
            
            # Add context type indicator
            type_indicators = {
                'current': '📄',
                'linked': '🔗',
                'similar': '🎯', 
                'recent': '🕒',
                'tagged': '🏷️'
            }
            
            if item.context_type in type_indicators:
                source_label = f"{type_indicators[item.context_type]} {source_label}"
            
            # Add relevance indicator
            if item.relevance_score >= 0.8:
                source_label += " (high relevance)"
            elif item.relevance_score >= 0.5:
                source_label += " (medium relevance)"
            else:
                source_label += " (low relevance)"
                
            sources.append(source_label)
        
        return sources
    
    def validate_context_pyramid(self, pyramid: ContextPyramid) -> Dict[str, Any]:
        """Validate context pyramid and provide feedback."""
        validation = {
            'is_valid': True,
            'warnings': [],
            'errors': [],
            'stats': {
                'total_items': len(pyramid.items),
                'total_tokens': pyramid.total_tokens,
                'by_type': {},
                'truncated': pyramid.truncated
            }
        }
        
        # Count items by type
        for item in pyramid.items:
            context_type = item.context_type
            if context_type not in validation['stats']['by_type']:
                validation['stats']['by_type'][context_type] = 0
            validation['stats']['by_type'][context_type] += 1
        
        # Add warnings
        if pyramid.truncated:
            validation['warnings'].append("Context was truncated due to token limits")
        
        if len(pyramid.items) == 0:
            validation['errors'].append("No relevant context found")
            validation['is_valid'] = False
        
        if pyramid.total_tokens > self.max_tokens * 0.9:
            validation['warnings'].append(f"Large context size ({pyramid.total_tokens} tokens)")
        
        # Check for missing current note
        current_items = [item for item in pyramid.items if item.context_type == 'current']
        if pyramid.current_note_path and len(current_items) == 0:
            validation['warnings'].append("Current note not found in context")
        
        return validation
    
    async def _get_mentioned_file_context(self, file_path: str) -> Optional[ContextItem]:
        """Get context from explicitly mentioned file."""
        try:
            # Handle different file path formats
            possible_paths = [
                file_path,
                f"{file_path}.md" if not file_path.endswith('.md') else file_path,
                file_path.replace('.md', '') + '.md'
            ]
            
            for path in possible_paths:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT content, file_size, modified_at FROM vault_files WHERE vault_path = %s OR vault_path LIKE %s AND processing_status = 'processed'",
                        (path, f"%{path}")
                    )
                    result = cursor.fetchone()
                    
                    if result:
                        content, file_size, modified_at = result
                        token_count = self._estimate_tokens(content)
                        
                        return ContextItem(
                            content=content,
                            source_path=path,
                            relevance_score=0.95,  # Very high relevance for explicitly mentioned
                            context_type='mentioned',
                            token_count=token_count,
                            metadata={
                                'file_size': file_size,
                                'modified_at': modified_at,
                                'explicitly_mentioned': True
                            }
                        )
                        
        except Exception as e:
            logger.error(f"Error getting mentioned file context for {file_path}: {e}")
            
        return None
    
    async def _get_mentioned_folder_context(self, folder_path: str) -> List[ContextItem]:
        """Get context from files in explicitly mentioned folder."""
        items = []
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT vault_path, content, file_size, modified_at 
                    FROM vault_files 
                    WHERE vault_path LIKE %s 
                    AND processing_status = 'processed'
                    ORDER BY modified_at DESC
                    LIMIT 10
                """, (f"{folder_path}/%",))
                
                results = cursor.fetchall()
                logger.info(f"📂 Found {len(results)} files in mentioned folder: {folder_path}")
                
                for vault_path, content, file_size, modified_at in results:
                    token_count = self._estimate_tokens(content)
                    
                    items.append(ContextItem(
                        content=content,
                        source_path=vault_path,
                        relevance_score=0.9,  # High relevance for mentioned folder content
                        context_type='mentioned_folder',
                        token_count=token_count,
                        metadata={
                            'folder_path': folder_path,
                            'file_size': file_size,
                            'modified_at': modified_at,
                            'explicitly_mentioned': True
                        }
                    ))
                    
        except Exception as e:
            logger.error(f"Error getting mentioned folder context for {folder_path}: {e}")
            
        return items