/**
 * FileManagerView - Tree view of vault files with processing status
 * 
 * Features:
 * - Hierarchical file tree with folders
 * - Processing status indicators (🟢🟡🔄⚪🔴)
 * - Batch operations (select, process, queue)
 * - Filter by status, file type, folder
 * - Real-time progress tracking
 * - Context menu actions
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { TFile, TFolder, TAbstractFile } from 'obsidian';
import { VaultProcessingManager } from '../vault/VaultProcessingManager';
import { VaultFileCache, VaultFileMetadata } from '../vault/VaultFileCache';
// Legacy RAG context import removed

interface FileNode {
  id: string;
  name: string;
  path: string;
  type: 'file' | 'folder';
  extension?: string;
  size?: number;
  modified?: Date;
  status?: 'processed' | 'queued' | 'processing' | 'unprocessed' | 'error';
  errorMessage?: string;
  children?: FileNode[];
  isExpanded?: boolean;
  isSelected?: boolean;
}

interface FileManagerViewProps {
  onFileSelect?: (file: TFile) => void;
  onFolderSelect?: (folder: TFolder) => void;
  className?: string;
}

type FilterType = 'all' | 'processed' | 'queued' | 'processing' | 'unprocessed' | 'error';
type SortType = 'name' | 'modified' | 'size' | 'status';

export const FileManagerView: React.FC<FileManagerViewProps> = ({
  onFileSelect,
  onFolderSelect,
  className = ""
}) => {
  const [fileTree, setFileTree] = useState<FileNode[]>([]);
  const [selectedNodes, setSelectedNodes] = useState<Set<string>>(new Set());
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set(['/'])); // Root expanded by default
  const [filter, setFilter] = useState<FilterType>('all');
  const [sortBy, setSortBy] = useState<SortType>('name');
  const [searchQuery, setSearchQuery] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStats, setProcessingStats] = useState({
    total: 0,
    processed: 0,
    queued: 0,
    unprocessed: 0,
    error: 0
  });

  const fileCache = VaultFileCache.getInstance<string>();
  const ragContextManager = RagContextManager.getInstance();
  const processingManager = ragContextManager.getProcessingManager();

  // Load file tree and metadata
  useEffect(() => {
    loadFileTree();
    loadProcessingStats();
  }, []);

  // Refresh data periodically
  useEffect(() => {
    const interval = setInterval(() => {
      loadProcessingStats();
      if (!isProcessing) {
        loadFileTree();
      }
    }, 5000); // Refresh every 5 seconds

    return () => clearInterval(interval);
  }, [isProcessing]);

  const loadFileTree = async () => {
    try {
      await fileCache.loadMetadata();
      const tree = buildFileTree(app.vault.getRoot());
      setFileTree(tree);
    } catch (error) {
      console.error('Error loading file tree:', error);
    }
  };

  const loadProcessingStats = () => {
    const stats = processingManager.getProcessingStats();
    setProcessingStats({
      total: stats.totalFiles,
      processed: stats.processedFiles,
      queued: stats.queuedFiles,
      unprocessed: stats.unprocessedFiles,
      error: stats.errorFiles
    });
  };

  const buildFileTree = (folder: TFolder): FileNode[] => {
    const nodes: FileNode[] = [];
    const children = folder.children.slice().sort((a, b) => {
      // Folders first, then files
      if (a instanceof TFolder && b instanceof TFile) return -1;
      if (a instanceof TFile && b instanceof TFolder) return 1;
      return a.name.localeCompare(b.name);
    });

    children.forEach(child => {
      if (child instanceof TFolder) {
        const folderNode: FileNode = {
          id: child.path,
          name: child.name,
          path: child.path,
          type: 'folder',
          children: buildFileTree(child),
          isExpanded: expandedFolders.has(child.path),
          isSelected: selectedNodes.has(child.path)
        };
        nodes.push(folderNode);
      } else if (child instanceof TFile) {
        const metadata = fileCache.getMetadata(child.path);
        const fileNode: FileNode = {
          id: child.path,
          name: child.basename,
          path: child.path,
          type: 'file',
          extension: child.extension,
          size: child.stat.size,
          modified: new Date(child.stat.mtime),
          status: metadata?.processing_status || 'unprocessed',
          errorMessage: metadata?.error_message,
          isSelected: selectedNodes.has(child.path)
        };
        nodes.push(fileNode);
      }
    });

    return nodes;
  };

  const filteredAndSortedTree = useMemo(() => {
    const filterNodes = (nodes: FileNode[]): FileNode[] => {
      return nodes.map(node => {
        if (node.type === 'folder') {
          const filteredChildren = filterNodes(node.children || []);
          // Include folder if it has matching children or if searching
          if (filteredChildren.length > 0 || 
              (searchQuery && node.name.toLowerCase().includes(searchQuery.toLowerCase()))) {
            return { ...node, children: filteredChildren };
          }
          return null;
        } else {
          // Filter files
          let include = true;
          
          // Status filter
          if (filter !== 'all' && node.status !== filter) {
            include = false;
          }
          
          // Search filter
          if (searchQuery && !node.name.toLowerCase().includes(searchQuery.toLowerCase())) {
            include = false;
          }
          
          return include ? node : null;
        }
      }).filter((node): node is FileNode => node !== null);
    };

    const sortNodes = (nodes: FileNode[]): FileNode[] => {
      return nodes.map(node => ({
        ...node,
        children: node.children ? sortNodes(node.children) : undefined
      })).sort((a, b) => {
        // Always keep folders first
        if (a.type === 'folder' && b.type === 'file') return -1;
        if (a.type === 'file' && b.type === 'folder') return 1;
        
        switch (sortBy) {
          case 'name':
            return a.name.localeCompare(b.name);
          case 'modified':
            return (b.modified?.getTime() || 0) - (a.modified?.getTime() || 0);
          case 'size':
            return (b.size || 0) - (a.size || 0);
          case 'status':
            const statusOrder = { error: 0, unprocessed: 1, queued: 2, processing: 3, processed: 4 };
            const aOrder = statusOrder[a.status as keyof typeof statusOrder] || 5;
            const bOrder = statusOrder[b.status as keyof typeof statusOrder] || 5;
            return aOrder - bOrder;
          default:
            return 0;
        }
      });
    };

    return sortNodes(filterNodes(fileTree));
  }, [fileTree, filter, sortBy, searchQuery, selectedNodes, expandedFolders]);

  const toggleFolderExpansion = (folderPath: string) => {
    setExpandedFolders(prev => {
      const next = new Set(prev);
      if (next.has(folderPath)) {
        next.delete(folderPath);
      } else {
        next.add(folderPath);
      }
      return next;
    });
  };

  const toggleNodeSelection = (nodePath: string, isMultiSelect: boolean = false) => {
    setSelectedNodes(prev => {
      const next = new Set(isMultiSelect ? prev : []);
      if (prev.has(nodePath)) {
        next.delete(nodePath);
      } else {
        next.add(nodePath);
      }
      return next;
    });
  };

  const selectAllVisible = () => {
    const getVisibleNodes = (nodes: FileNode[]): string[] => {
      const visible: string[] = [];
      nodes.forEach(node => {
        visible.push(node.path);
        if (node.type === 'folder' && node.isExpanded && node.children) {
          visible.push(...getVisibleNodes(node.children));
        }
      });
      return visible;
    };

    const visibleNodes = getVisibleNodes(filteredAndSortedTree);
    setSelectedNodes(new Set(visibleNodes));
  };

  const clearSelection = () => {
    setSelectedNodes(new Set());
  };

  const processSelectedFiles = async () => {
    const selectedFiles = Array.from(selectedNodes)
      .map(path => app.vault.getAbstractFileByPath(path))
      .filter((file): file is TFile => file instanceof TFile);

    if (selectedFiles.length === 0) {
      return;
    }

    setIsProcessing(true);
    try {
      await processingManager.processVaultFiles(selectedFiles, false);
      await loadFileTree();
      loadProcessingStats();
    } catch (error) {
      console.error('Error processing files:', error);
    } finally {
      setIsProcessing(false);
    }
  };

  const queueSelectedFiles = async () => {
    const selectedFiles = Array.from(selectedNodes)
      .map(path => app.vault.getAbstractFileByPath(path))
      .filter((file): file is TFile => file instanceof TFile);

    if (selectedFiles.length === 0) {
      return;
    }

    await processingManager.queueFiles(selectedFiles);
    await loadFileTree();
    loadProcessingStats();
  };

  const addSelectedToContext = () => {
    // Legacy add to context removed - files are now automatically included via @mentions
    }
  };

  const getStatusIcon = (status?: string): string => {
    const icons = {
      processed: '🟢',
      queued: '🟡',
      processing: '🔄',
      unprocessed: '⚪',
      error: '🔴'
    };
    return icons[status as keyof typeof icons] || '❓';
  };

  const getFileTypeIcon = (extension?: string): string => {
    const icons = {
      md: '📝',
      pdf: '📄',
      txt: '📄',
      docx: '📄',
      jpg: '🖼️',
      png: '🖼️',
      gif: '🖼️'
    };
    return icons[extension as keyof typeof icons] || '📄';
  };

  const formatFileSize = (bytes?: number): string => {
    if (!bytes) return '';
    const units = ['B', 'KB', 'MB'];
    let size = bytes;
    let unit = 0;
    while (size >= 1024 && unit < units.length - 1) {
      size /= 1024;
      unit++;
    }
    return `${Math.round(size)}${units[unit]}`;
  };

  const formatDate = (date?: Date): string => {
    if (!date) return '';
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const renderNode = (node: FileNode, depth: number = 0): React.ReactNode => {
    const indentStyle = { paddingLeft: `${depth * 16 + 8}px` };
    const isSelected = selectedNodes.has(node.path);

    if (node.type === 'folder') {
      return (
        <div key={node.id}>
          <div
            className={`flex items-center py-1 px-2 hover:bg-muted cursor-pointer ${
              isSelected ? 'bg-accent' : ''
            }`}
            style={indentStyle}
            onClick={(e) => {
              toggleFolderExpansion(node.path);
              toggleNodeSelection(node.path, e.ctrlKey || e.metaKey);
              if (onFolderSelect) {
                const folder = app.vault.getAbstractFileByPath(node.path);
                if (folder instanceof TFolder) {
                  onFolderSelect(folder);
                }
              }
            }}
          >
            <span className="w-4 text-sm">
              {node.isExpanded ? '📂' : '📁'}
            </span>
            <span className="w-4 text-sm mr-1">
              {node.isExpanded ? '▼' : '▶'}
            </span>
            <span className="flex-1 text-sm font-medium">{node.name}</span>
            {node.children && (
              <span className="text-xs text-muted-foreground">
                ({node.children.length})
              </span>
            )}
          </div>
          {node.isExpanded && node.children && (
            <div>
              {node.children.map(child => renderNode(child, depth + 1))}
            </div>
          )}
        </div>
      );
    }

    return (
      <div
        key={node.id}
        className={`flex items-center py-1 px-2 hover:bg-muted cursor-pointer text-sm ${
          isSelected ? 'bg-accent' : ''
        }`}
        style={indentStyle}
        onClick={(e) => {
          toggleNodeSelection(node.path, e.ctrlKey || e.metaKey);
          if (onFileSelect) {
            const file = app.vault.getAbstractFileByPath(node.path);
            if (file instanceof TFile) {
              onFileSelect(file);
            }
          }
        }}
        title={node.errorMessage || node.path}
      >
        <span className="w-4 text-sm">{getStatusIcon(node.status)}</span>
        <span className="w-4 text-sm mr-1">{getFileTypeIcon(node.extension)}</span>
        <span className="flex-1 truncate">{node.name}</span>
        <span className="text-xs text-muted-foreground ml-2">
          {formatFileSize(node.size)}
        </span>
      </div>
    );
  };

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Header with stats */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold">File Manager</h3>
          <div className="text-xs text-muted-foreground">
            {processingStats.total} files
          </div>
        </div>
        
        {/* Processing stats */}
        <div className="grid grid-cols-5 gap-2 text-xs">
          <div className="text-center">
            <div className="font-medium text-green-600">{processingStats.processed}</div>
            <div className="text-muted-foreground">🟢</div>
          </div>
          <div className="text-center">
            <div className="font-medium text-yellow-600">{processingStats.queued}</div>
            <div className="text-muted-foreground">🟡</div>
          </div>
          <div className="text-center">
            <div className="font-medium">0</div>
            <div className="text-muted-foreground">🔄</div>
          </div>
          <div className="text-center">
            <div className="font-medium text-gray-500">{processingStats.unprocessed}</div>
            <div className="text-muted-foreground">⚪</div>
          </div>
          <div className="text-center">
            <div className="font-medium text-red-600">{processingStats.error}</div>
            <div className="text-muted-foreground">🔴</div>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="p-4 space-y-3 border-b border-border">
        {/* Search */}
        <input
          type="text"
          placeholder="Search files..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full px-3 py-2 text-sm border border-border rounded focus:outline-none focus:ring-2 focus:ring-primary"
        />

        {/* Filters and Sort */}
        <div className="flex gap-2">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as FilterType)}
            className="flex-1 px-2 py-1 text-sm border border-border rounded"
          >
            <option value="all">All Files</option>
            <option value="processed">🟢 Processed</option>
            <option value="queued">🟡 Queued</option>
            <option value="processing">🔄 Processing</option>
            <option value="unprocessed">⚪ Unprocessed</option>
            <option value="error">🔴 Error</option>
          </select>

          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortType)}
            className="flex-1 px-2 py-1 text-sm border border-border rounded"
          >
            <option value="name">Name</option>
            <option value="modified">Modified</option>
            <option value="size">Size</option>
            <option value="status">Status</option>
          </select>
        </div>

        {/* Selection Actions */}
        {selectedNodes.size > 0 && (
          <div className="flex gap-2 text-xs">
            <span className="text-muted-foreground">{selectedNodes.size} selected</span>
            <button
              onClick={processSelectedFiles}
              disabled={isProcessing}
              className="px-2 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
            >
              Process
            </button>
            <button
              onClick={queueSelectedFiles}
              className="px-2 py-1 bg-yellow-500 text-white rounded hover:bg-yellow-600"
            >
              Queue
            </button>
            {false && (
              <button
                onClick={addSelectedToContext}
                className="px-2 py-1 bg-green-500 text-white rounded hover:bg-green-600"
              >
                Add to Context
              </button>
            )}
            <button
              onClick={clearSelection}
              className="px-2 py-1 bg-gray-500 text-white rounded hover:bg-gray-600"
            >
              Clear
            </button>
          </div>
        )}

        <div className="flex gap-2 text-xs">
          <button
            onClick={selectAllVisible}
            className="px-2 py-1 border border-border rounded hover:bg-muted"
          >
            Select All
          </button>
          <button
            onClick={loadFileTree}
            className="px-2 py-1 border border-border rounded hover:bg-muted"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* File Tree */}
      <div className="flex-1 overflow-y-auto">
        {filteredAndSortedTree.length > 0 ? (
          <div className="pb-4">
            {filteredAndSortedTree.map(node => renderNode(node))}
          </div>
        ) : (
          <div className="p-8 text-center text-muted-foreground">
            <div className="text-2xl mb-2">📁</div>
            <div>No files found</div>
            {filter !== 'all' || searchQuery ? (
              <div className="text-sm mt-1">Try adjusting your filters</div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
};