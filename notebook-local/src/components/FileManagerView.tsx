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
import { TFile, TFolder, TAbstractFile, App } from 'obsidian';
import { VaultProcessingManager } from '../vault/VaultProcessingManager';
import { VaultFileCache, VaultFileMetadata } from '../vault/VaultFileCache';
import { ApiClient } from '../api/ApiClient-clean';

// Global app reference for accessing Obsidian API
declare const app: App;

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
  apiClient?: ApiClient;
  className?: string;
}

type FilterType = 'all' | 'processed' | 'queued' | 'processing' | 'unprocessed' | 'error';
type SortType = 'name' | 'modified' | 'size' | 'status';

export const FileManagerView: React.FC<FileManagerViewProps> = ({
  onFileSelect,
  onFolderSelect,
  apiClient,
  className = ""
}) => {
  const [fileTree, setFileTree] = useState<FileNode[]>([]);
  const [selectedNodes, setSelectedNodes] = useState<Set<string>>(new Set());
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set(['/'])); // Root expanded by default
  const [filter, setFilter] = useState<FilterType>('all');
  const [sortBy, setSortBy] = useState<SortType>('name');
  const [searchQuery, setSearchQuery] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isWatcherActive, setIsWatcherActive] = useState(false);
  const [processingStats, setProcessingStats] = useState({
    total: 0,
    processed: 0,
    queued: 0,
    unprocessed: 0,
    error: 0
  });

  const fileCache = VaultFileCache.getInstance<string>();
  // Note: VaultProcessingManager should be passed as prop or accessed differently
  // For now, accessing directly from app (needs refactoring)
  const processingManager = new VaultProcessingManager(app, null as any);

  // Load file tree and metadata
  useEffect(() => {
    loadFileTree();
    loadProcessingStats();
    checkWatcherStatus();
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
      // Try to sync with backend first if API client is available
      if (apiClient) {
        await syncWithBackend();
      }
      
      await fileCache.loadMetadata();
      const tree = buildFileTree(app.vault.getRoot());
      setFileTree(tree);
    } catch (error) {
      console.error('Error loading file tree:', error);
    }
  };

  const syncWithBackend = async () => {
    try {
      // Trigger a vault scan to sync file changes
      const vaultPath = app.vault.adapter.path;
      const response = await fetch(`${apiClient.baseURL}/api/v1/vault/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          vault_path: vaultPath,
          force_rescan: false
        })
      });
      
      if (response.ok) {
        const result = await response.json();
        console.log('Backend sync completed:', result);
      }
    } catch (error) {
      console.error('Error syncing with backend:', error);
      // Don't throw - allow fallback to local cache
    }
  };

  const loadProcessingStats = async () => {
    try {
      // Try to get stats from backend first if API client is available
      if (apiClient) {
        const response = await fetch(`${apiClient.baseURL}/api/v1/vault/status`);
        
        if (response.ok) {
          const backendStats = await response.json();
          setProcessingStats({
            total: backendStats.total_files,
            processed: backendStats.processed,
            queued: backendStats.queued,
            unprocessed: backendStats.unprocessed,
            error: backendStats.error
          });
          return; // Use backend stats if available
        }
      }
      
      // Fallback to local processing manager
      const stats = processingManager.getProcessingStats();
      setProcessingStats({
        total: stats.totalFiles,
        processed: stats.processedFiles,
        queued: stats.queuedFiles,
        unprocessed: stats.unprocessedFiles,
        error: stats.errorFiles
      });
    } catch (error) {
      console.error('Error loading processing stats:', error);
      // Fallback to local stats on error
      const stats = processingManager.getProcessingStats();
      setProcessingStats({
        total: stats.totalFiles,
        processed: stats.processedFiles,
        queued: stats.queuedFiles,
        unprocessed: stats.unprocessedFiles,
        error: stats.errorFiles
      });
    }
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
          status: metadata?.processingStatus || 'unprocessed',
          errorMessage: metadata?.errorMessage,
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

  const toggleNodeSelection = (nodePath: string, isMultiSelect: boolean = false, isShiftSelect: boolean = false) => {
    setSelectedNodes(prev => {
      if (isShiftSelect && prev.size > 0) {
        // Shift+click: select range from last selected to current
        const allNodes = getAllVisibleNodePaths(filteredAndSortedTree);
        const currentIndex = allNodes.indexOf(nodePath);
        const lastSelected = Array.from(prev).pop();
        const lastIndex = lastSelected ? allNodes.indexOf(lastSelected) : -1;
        
        if (currentIndex !== -1 && lastIndex !== -1) {
          const start = Math.min(currentIndex, lastIndex);
          const end = Math.max(currentIndex, lastIndex);
          const rangeNodes = allNodes.slice(start, end + 1);
          return new Set([...prev, ...rangeNodes]);
        }
      }
      
      const next = new Set(isMultiSelect ? prev : []);
      if (prev.has(nodePath)) {
        next.delete(nodePath);
      } else {
        next.add(nodePath);
      }
      return next;
    });
  };
  
  const getAllVisibleNodePaths = (nodes: FileNode[]): string[] => {
    const paths: string[] = [];
    const traverse = (nodeList: FileNode[]) => {
      nodeList.forEach(node => {
        paths.push(node.path);
        if (node.type === 'folder' && node.isExpanded && node.children) {
          traverse(node.children);
        }
      });
    };
    traverse(nodes);
    return paths;
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
    const selectedFilePaths = Array.from(selectedNodes)
      .map(path => {
        const file = app.vault.getAbstractFileByPath(path);
        return file instanceof TFile ? path : null;
      })
      .filter((path): path is string => path !== null);

    if (selectedFilePaths.length === 0) {
      return;
    }

    setIsProcessing(true);
    try {
      // Use new backend API for queueing and processing
      if (apiClient) {
        const response = await fetch(`${apiClient.baseURL}/api/v1/vault/process`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            file_paths: selectedFilePaths,
            force_reprocess: false
          })
        });
        
        if (!response.ok) {
          throw new Error(`Failed to queue files: ${response.statusText}`);
        }
        
        const result = await response.json();
        console.log('Files queued for processing:', result);
      } else {
        // Fallback to old processing manager
        const selectedFiles = selectedFilePaths
          .map(path => app.vault.getAbstractFileByPath(path))
          .filter((file): file is TFile => file instanceof TFile);
        await processingManager.processVaultFiles(selectedFiles, false);
      }
      
      await loadFileTree();
      loadProcessingStats();
    } catch (error) {
      console.error('Error processing files:', error);
    } finally {
      setIsProcessing(false);
    }
  };

  const queueSelectedFiles = async () => {
    const selectedFilePaths = Array.from(selectedNodes)
      .map(path => {
        const file = app.vault.getAbstractFileByPath(path);
        return file instanceof TFile ? path : null;
      })
      .filter((path): path is string => path !== null);

    if (selectedFilePaths.length === 0) {
      return;
    }

    try {
      // Use new backend API for queueing
      if (apiClient) {
        const response = await fetch(`${apiClient.baseURL}/api/v1/vault/process`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            file_paths: selectedFilePaths,
            force_reprocess: false
          })
        });
        
        if (!response.ok) {
          throw new Error(`Failed to queue files: ${response.statusText}`);
        }
        
        const result = await response.json();
        console.log('Files queued:', result);
      } else {
        // Fallback to old processing manager
        const selectedFiles = selectedFilePaths
          .map(path => app.vault.getAbstractFileByPath(path))
          .filter((file): file is TFile => file instanceof TFile);
        await processingManager.queueFiles(selectedFiles);
      }
      
      await loadFileTree();
      loadProcessingStats();
    } catch (error) {
      console.error('Error queueing files:', error);
    }
  };

  const toggleFileWatcher = async () => {
    if (!apiClient) {
      console.warn('API client not available for file watcher');
      return;
    }

    try {
      if (isWatcherActive) {
        // Stop file watcher
        const response = await fetch(`${apiClient.baseURL}/api/v1/vault/watcher/stop`, {
          method: 'POST'
        });
        
        if (response.ok) {
          setIsWatcherActive(false);
          console.log('File watcher stopped');
        }
      } else {
        // Start file watcher
        const vaultPath = app.vault.adapter.path;
        const response = await fetch(`${apiClient.baseURL}/api/v1/vault/watcher/start?vault_path=${encodeURIComponent(vaultPath)}`, {
          method: 'POST'
        });
        
        if (response.ok) {
          setIsWatcherActive(true);
          console.log('File watcher started');
        }
      }
    } catch (error) {
      console.error('Error toggling file watcher:', error);
    }
  };

  const checkWatcherStatus = async () => {
    if (!apiClient) return;

    try {
      const response = await fetch(`${apiClient.baseURL}/api/v1/vault/watcher/status`);
      
      if (response.ok) {
        const result = await response.json();
        setIsWatcherActive(result.status?.is_watching || false);
      }
    } catch (error) {
      console.error('Error checking watcher status:', error);
    }
  };

  const selectFilesByStatus = (status: FilterType) => {
    const getNodesByStatus = (nodes: FileNode[]): string[] => {
      const matching: string[] = [];
      nodes.forEach(node => {
        if (node.type === 'file' && (status === 'all' || node.status === status)) {
          matching.push(node.path);
        }
        if (node.type === 'folder' && node.children) {
          matching.push(...getNodesByStatus(node.children));
        }
      });
      return matching;
    };

    const matchingNodes = getNodesByStatus(filteredAndSortedTree);
    setSelectedNodes(new Set(matchingNodes));
  };
  
  const selectFolderContents = (folderPath: string) => {
    const getFolderFiles = (nodes: FileNode[], targetPath: string): string[] => {
      for (const node of nodes) {
        if (node.path === targetPath && node.type === 'folder' && node.children) {
          const files: string[] = [];
          const collectFiles = (children: FileNode[]) => {
            children.forEach(child => {
              if (child.type === 'file') {
                files.push(child.path);
              } else if (child.children) {
                collectFiles(child.children);
              }
            });
          };
          collectFiles(node.children);
          return files;
        }
        if (node.children) {
          const result = getFolderFiles(node.children, targetPath);
          if (result.length > 0) return result;
        }
      }
      return [];
    };
    
    const folderFiles = getFolderFiles(filteredAndSortedTree, folderPath);
    setSelectedNodes(prev => new Set([...prev, ...folderFiles]));
  };

  const addSelectedToContext = () => {
    // Legacy add to context removed - files are now automatically included via @mentions
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

  // formatDate removed - not used in current UI

  const renderNode = (node: FileNode, depth: number = 0): React.ReactNode => {
    const indentStyle = { paddingLeft: `${depth * 20 + 8}px` };
    const isSelected = selectedNodes.has(node.path);

    if (node.type === 'folder') {
      return (
        <div key={node.id}>
          <div
            className={`flex items-center py-1.5 px-2 hover:bg-muted transition-colors ${
              isSelected ? 'bg-accent border-l-2 border-blue-500' : ''
            }`}
            style={indentStyle}
          >
            {/* Checkbox for selection */}
            <input
              type="checkbox"
              checked={isSelected}
              onChange={(e) => {
                e.stopPropagation();
                toggleNodeSelection(node.path, e.ctrlKey || e.metaKey, e.shiftKey);
              }}
              className="w-4 h-4 mr-2 rounded border-gray-300 focus:ring-2 focus:ring-blue-500"
            />
            
            {/* Expand/collapse button */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                toggleFolderExpansion(node.path);
              }}
              className="w-6 h-6 mr-1 flex items-center justify-center hover:bg-gray-200 rounded transition-colors"
            >
              <span className="text-xs font-bold text-gray-600">
                {node.isExpanded ? '−' : '+'}
              </span>
            </button>
            
            {/* Folder icon and name */}
            <span 
              className="w-5 text-base mr-2 cursor-pointer flex-shrink-0"
              onClick={() => {
                if (onFolderSelect) {
                  const folder = app.vault.getAbstractFileByPath(node.path);
                  if (folder instanceof TFolder) {
                    onFolderSelect(folder);
                  }
                }
              }}
            >
              {node.isExpanded ? '📂' : '📁'}
            </span>
            <span 
              className="flex-1 text-sm font-medium cursor-pointer select-none"
              onClick={() => {
                if (onFolderSelect) {
                  const folder = app.vault.getAbstractFileByPath(node.path);
                  if (folder instanceof TFolder) {
                    onFolderSelect(folder);
                  }
                }
              }}
            >
              {node.name}
            </span>
            {node.children && (
              <>
                <span className="text-xs text-muted-foreground px-1 py-0.5 bg-gray-100 rounded mr-1">
                  {node.children.length}
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    selectFolderContents(node.path);
                  }}
                  className="text-xs px-1 py-0.5 text-blue-600 hover:bg-blue-100 rounded transition-colors"
                  title="Select all files in this folder"
                >
                  ✓
                </button>
              </>
            )}
          </div>
          {node.isExpanded && node.children && (
            <div className="border-l border-gray-200 ml-4">
              {node.children.map(child => renderNode(child, depth + 1))}
            </div>
          )}
        </div>
      );
    }

    return (
      <div
        key={node.id}
        className={`flex items-center py-1.5 px-2 hover:bg-muted cursor-pointer text-sm transition-colors ${
          isSelected ? 'bg-accent border-l-2 border-blue-500' : ''
        }`}
        style={indentStyle}
        title={node.errorMessage || node.path}
      >
        {/* Checkbox for selection */}
        <input
          type="checkbox"
          checked={isSelected}
          onChange={(e) => {
            e.stopPropagation();
            toggleNodeSelection(node.path, e.ctrlKey || e.metaKey, e.shiftKey);
          }}
          className="w-4 h-4 mr-2 rounded border-gray-300 focus:ring-2 focus:ring-blue-500"
        />
        
        {/* File status and type icons */}
        <span className="w-4 text-sm mr-1 flex-shrink-0">{getStatusIcon(node.status)}</span>
        <span className="w-4 text-sm mr-2 flex-shrink-0">{getFileTypeIcon(node.extension)}</span>
        
        {/* File name - clickable to open */}
        <span 
          className="flex-1 truncate cursor-pointer select-none hover:text-blue-600"
          onClick={(e) => {
            e.stopPropagation();
            if (onFileSelect) {
              const file = app.vault.getAbstractFileByPath(node.path);
              if (file instanceof TFile) {
                onFileSelect(file);
              }
            }
          }}
        >
          {node.name}
        </span>
        
        {/* File size */}
        <span className="text-xs text-muted-foreground ml-2 flex-shrink-0">
          {formatFileSize(node.size)}
        </span>
      </div>
    );
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey) {
        switch (e.key) {
          case 'a':
            e.preventDefault();
            selectAllVisible();
            break;
          case 'd':
            e.preventDefault();
            clearSelection();
            break;
        }
      }
      if (e.key === 'Escape') {
        clearSelection();
      }
    };
    
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div className={`flex flex-col h-full ${className}`} tabIndex={0}>
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

        <div className="flex gap-2 text-xs flex-wrap">
          <button
            onClick={selectAllVisible}
            className="px-2 py-1 border border-border rounded hover:bg-muted"
            title="Select all visible files (Ctrl+A)"
          >
            Select All
          </button>
          <button
            onClick={() => selectFilesByStatus('unprocessed')}
            className="px-2 py-1 border border-border rounded hover:bg-muted"
          >
            Select Unprocessed
          </button>
          <button
            onClick={() => selectFilesByStatus('error')}
            className="px-2 py-1 border border-border rounded hover:bg-muted"
          >
            Select Errors
          </button>
          <button
            onClick={loadFileTree}
            className="px-2 py-1 border border-border rounded hover:bg-muted"
          >
            Refresh
          </button>
          {apiClient && (
            <button
              onClick={toggleFileWatcher}
              className={`px-2 py-1 border border-border rounded hover:bg-muted ${
                isWatcherActive ? 'bg-green-100 text-green-800' : 'bg-gray-100'
              }`}
            >
              {isWatcherActive ? '👀 Watching' : '👁️ Start Watch'}
            </button>
          )}
        </div>
        
        {/* Help text */}
        <div className="text-xs text-muted-foreground mt-2 px-1">
          📝 Use checkboxes to select • Ctrl+click for multi-select • Shift+click for range • Ctrl+A to select all • Esc to clear
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