"""
File Watcher - Real-time file change detection for vault synchronization

Features:
- Monitors vault directory for file changes
- Debounces rapid file changes
- Integrates with FileQueueManager for DB updates
- Supports multiple file system events (created, modified, deleted, moved)
- Filters based on supported file types
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Set, Optional, Callable
from threading import Thread
from dataclasses import dataclass
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from .file_queue_manager import FileQueueManager

logger = logging.getLogger(__name__)

@dataclass
class FileChangeEvent:
    file_path: str
    event_type: str  # 'created', 'modified', 'deleted', 'moved'
    timestamp: datetime
    src_path: Optional[str] = None  # For move events

class VaultFileHandler(FileSystemEventHandler):
    """Handles file system events for vault files."""
    
    def __init__(self, watcher: 'FileWatcher'):
        self.watcher = watcher
        self.supported_extensions = {'.md', '.pdf', '.txt', '.docx'}
        self.ignore_patterns = {'.obsidian', 'node_modules', '.git', '__pycache__'}
        
    def _should_process(self, file_path: str) -> bool:
        """Check if file should be processed based on extension and patterns."""
        path = Path(file_path)
        
        # Skip hidden files
        if path.name.startswith('.'):
            return False
            
        # Skip files in ignored directories
        for part in path.parts:
            if part in self.ignore_patterns:
                return False
                
        # Check extension
        return path.suffix.lower() in self.supported_extensions
    
    def on_created(self, event: FileSystemEvent):
        """Handle file creation events."""
        if not event.is_directory and self._should_process(event.src_path):
            self.watcher.queue_change_event(FileChangeEvent(
                file_path=event.src_path,
                event_type='created',
                timestamp=datetime.now()
            ))
            logger.info(f"📄 File created: {event.src_path}")
    
    def on_modified(self, event: FileSystemEvent):
        """Handle file modification events."""
        if not event.is_directory and self._should_process(event.src_path):
            self.watcher.queue_change_event(FileChangeEvent(
                file_path=event.src_path,
                event_type='modified',
                timestamp=datetime.now()
            ))
            logger.debug(f"✏️ File modified: {event.src_path}")
    
    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion events."""
        if not event.is_directory and self._should_process(event.src_path):
            self.watcher.queue_change_event(FileChangeEvent(
                file_path=event.src_path,
                event_type='deleted',
                timestamp=datetime.now()
            ))
            logger.info(f"🗑️ File deleted: {event.src_path}")
    
    def on_moved(self, event: FileSystemEvent):
        """Handle file move/rename events."""
        if (not event.is_directory and 
            hasattr(event, 'dest_path') and
            (self._should_process(event.src_path) or self._should_process(event.dest_path))):
            
            self.watcher.queue_change_event(FileChangeEvent(
                file_path=event.dest_path,
                event_type='moved',
                timestamp=datetime.now(),
                src_path=event.src_path
            ))
            logger.info(f"📁 File moved: {event.src_path} -> {event.dest_path}")

class FileWatcher:
    """
    File system watcher for vault directory with debouncing and queue integration.
    """
    
    def __init__(self, vault_path: str, queue_manager: FileQueueManager = None):
        self.vault_path = Path(vault_path)
        self.queue_manager = queue_manager or FileQueueManager()
        
        # Event handling
        self.observer = None
        self.handler = VaultFileHandler(self)
        self.is_watching = False
        
        # Debouncing settings
        self.debounce_delay = 1.0  # seconds
        self.pending_events: Dict[str, FileChangeEvent] = {}
        self.debounce_timers: Dict[str, float] = {}
        
        # Processing
        self.event_queue = asyncio.Queue()
        self.processing_task = None
        self.on_change_callback: Optional[Callable] = None
        
    def set_change_callback(self, callback: Callable[[FileChangeEvent], None]):
        """Set callback function to be called on file changes."""
        self.on_change_callback = callback
    
    def queue_change_event(self, event: FileChangeEvent):
        """Queue a file change event for debounced processing."""
        current_time = time.time()
        
        # Update pending event (latest wins for same file)
        self.pending_events[event.file_path] = event
        self.debounce_timers[event.file_path] = current_time + self.debounce_delay
        
        # Start processing task if not running
        if not self.processing_task or self.processing_task.done():
            asyncio.create_task(self._process_debounced_events())
    
    async def _process_debounced_events(self):
        """Process debounced events after delay period."""
        while self.pending_events:
            current_time = time.time()
            ready_events = []
            
            # Find events that are ready to process
            for file_path, timer_time in list(self.debounce_timers.items()):
                if current_time >= timer_time:
                    if file_path in self.pending_events:
                        ready_events.append(self.pending_events.pop(file_path))
                    del self.debounce_timers[file_path]
            
            # Process ready events
            for event in ready_events:
                await self._handle_change_event(event)
            
            # Wait a bit before checking again
            if self.pending_events:
                await asyncio.sleep(0.1)
    
    async def _handle_change_event(self, event: FileChangeEvent):
        """Handle a debounced file change event."""
        try:
            relative_path = str(Path(event.file_path).relative_to(self.vault_path))
            
            if event.event_type == 'deleted':
                await self._handle_file_deleted(relative_path)
            elif event.event_type == 'moved':
                await self._handle_file_moved(event)
            else:  # created or modified
                await self._handle_file_changed(relative_path, event.file_path)
            
            # Call user callback if set
            if self.on_change_callback:
                self.on_change_callback(event)
                
        except Exception as e:
            logger.error(f"❌ Error handling change event: {e}")
    
    async def _handle_file_changed(self, relative_path: str, full_path: str):
        """Handle file creation or modification."""
        try:
            # Trigger a scan to update the database
            logger.info(f"🔄 Syncing file change: {relative_path}")
            
            # Force rescan of the specific directory containing this file
            parent_path = os.path.dirname(full_path)
            await self.queue_manager.scan_vault_directory(parent_path, force_rescan=True)
            
            logger.info(f"✅ File sync completed: {relative_path}")
            
        except Exception as e:
            logger.error(f"❌ Error syncing file change {relative_path}: {e}")
    
    async def _handle_file_deleted(self, relative_path: str):
        """Handle file deletion."""
        try:
            logger.info(f"🗑️ Syncing file deletion: {relative_path}")
            
            # Full rescan to detect deletions
            await self.queue_manager.scan_vault_directory(str(self.vault_path), force_rescan=True)
            
            logger.info(f"✅ File deletion sync completed: {relative_path}")
            
        except Exception as e:
            logger.error(f"❌ Error syncing file deletion {relative_path}: {e}")
    
    async def _handle_file_moved(self, event: FileChangeEvent):
        """Handle file move/rename."""
        try:
            old_relative = str(Path(event.src_path).relative_to(self.vault_path))
            new_relative = str(Path(event.file_path).relative_to(self.vault_path))
            
            logger.info(f"📁 Syncing file move: {old_relative} -> {new_relative}")
            
            # Full rescan to detect moves correctly
            await self.queue_manager.scan_vault_directory(str(self.vault_path), force_rescan=True)
            
            logger.info(f"✅ File move sync completed: {old_relative} -> {new_relative}")
            
        except Exception as e:
            logger.error(f"❌ Error syncing file move: {e}")
    
    def start_watching(self):
        """Start watching the vault directory for changes."""
        if self.is_watching:
            logger.warning("File watcher is already running")
            return
        
        if not self.vault_path.exists():
            raise ValueError(f"Vault path does not exist: {self.vault_path}")
        
        try:
            self.observer = Observer()
            self.observer.schedule(
                event_handler=self.handler,
                path=str(self.vault_path),
                recursive=True
            )
            
            self.observer.start()
            self.is_watching = True
            
            logger.info(f"👀 Started watching vault directory: {self.vault_path}")
            
        except Exception as e:
            logger.error(f"❌ Failed to start file watcher: {e}")
            raise
    
    def stop_watching(self):
        """Stop watching the vault directory."""
        if not self.is_watching:
            return
        
        try:
            if self.observer:
                self.observer.stop()
                self.observer.join()
                self.observer = None
            
            # Cancel processing task
            if self.processing_task and not self.processing_task.done():
                self.processing_task.cancel()
            
            self.is_watching = False
            logger.info("🛑 Stopped file watcher")
            
        except Exception as e:
            logger.error(f"❌ Error stopping file watcher: {e}")
    
    def get_status(self) -> Dict[str, any]:
        """Get current watcher status."""
        return {
            "is_watching": self.is_watching,
            "vault_path": str(self.vault_path),
            "pending_events": len(self.pending_events),
            "debounce_delay": self.debounce_delay
        }
    
    def __enter__(self):
        self.start_watching()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_watching()

# Global watcher instance for API integration
_global_watcher: Optional[FileWatcher] = None

def get_file_watcher(vault_path: str = None) -> FileWatcher:
    """Get or create global file watcher instance."""
    global _global_watcher
    
    if _global_watcher is None and vault_path:
        _global_watcher = FileWatcher(vault_path)
    
    return _global_watcher

def start_global_watcher(vault_path: str):
    """Start the global file watcher."""
    watcher = get_file_watcher(vault_path)
    if watcher and not watcher.is_watching:
        watcher.start_watching()
    return watcher

def stop_global_watcher():
    """Stop the global file watcher."""
    global _global_watcher
    if _global_watcher:
        _global_watcher.stop_watching()
        _global_watcher = None