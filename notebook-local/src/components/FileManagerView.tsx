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
  apiClient: ApiClient;
  className?: string;
}

// FilterType removed - simplified to use direct processing buttons
// SortType also removed - using simple name-based sorting in tree

export const FileManagerView: React.FC<FileManagerViewProps> = ({
  onFileSelect,
  onFolderSelect,
  apiClient,
  className = ""
}) => {
  const [fileTree, setFileTree] = useState<FileNode[]>([]);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set(['/']));
  const [searchQuery, setSearchQuery] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [processingStats, setProcessingStats] = useState({
    total: 0,
    processed: 0,
    processing: 0,
    pending: 0,
    errors: 0
  });
  const [fileWaitTimes, setFileWaitTimes] = useState<Map<string, number>>(new Map());
  const [showSettings, setShowSettings] = useState(false);
  const [frequencyLimit, setFrequencyLimit] = useState(60); // Default 60 seconds
  const [isWatcherActive, setIsWatcherActive] = useState(false);
  
  // Auto-processing state
  const [autoProcessingActive, setAutoProcessingActive] = useState(false);

  // Simple file metadata cache
  const [fileMetadata, setFileMetadata] = useState<Map<string, any>>(new Map());

  // Load file tree and metadata
  useEffect(() => {
    loadFileTree();
    checkWatcherStatus();
  }, []);

  // Refresh data periodically
  useEffect(() => {
    const interval = setInterval(() => {
      if (processingStats.processing > 0) {
        loadFileTree();
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [processingStats.processing]);

  const loadFileTree = async () => {
    setIsLoading(true);
    try {
      // First, validate vault access
      if (!app?.vault) {
        console.error('Obsidian vault not available');
        setFileTree([]);
        return;
      }

      // Try to get vault root
      let vaultRoot;
      try {
        vaultRoot = app.vault.getRoot();
        if (!vaultRoot) {
          console.error('Cannot access vault root');
          setFileTree([]);
          return;
        }
      } catch (error) {
        console.error('Error accessing vault root:', error);
        setFileTree([]);
        return;
      }

      if (apiClient) {
        try {
          // Load processing stats from new DocumentProcessingService
          const statsResponse = await fetch(`${apiClient.getBaseUrl()}/api/v1/documents/stats`);
          if (statsResponse.ok) {
            const data = await statsResponse.json();
            setProcessingStats({
              total: data.total_files || 0,
              processed: data.file_stats?.processed || 0,
              processing: data.file_stats?.processing || 0,
              pending: data.file_stats?.unprocessed || 0,
              errors: data.file_stats?.error || 0
            });
          }
        } catch (error) {
          console.warn('Failed to load document stats:', error);
        }

        try {
          // Load file watcher status for frequency limiting info
          const watcherResponse = await fetch(`${apiClient.getBaseUrl()}/api/v1/vault/watcher/status`);
          if (watcherResponse.ok) {
            const watcherData = await watcherResponse.json();
            const waitTimes = new Map<string, number>();
            
            if (watcherData.status?.cooldown_details) {
              watcherData.status.cooldown_details.forEach((item: any) => {
                waitTimes.set(item.file, item.wait_seconds);
              });
            }
            setFileWaitTimes(waitTimes);
            setIsWatcherActive(watcherData.status?.is_watching || false);
          }
        } catch (error) {
          console.warn('Failed to load watcher status:', error);
        }

        try {
          // Sync with backend
          await syncWithBackend();
        } catch (error) {
          console.warn('Failed to sync with backend:', error);
        }
      }
      
      // Build file tree from Obsidian's vault
      console.log('Building file tree from vault root:', vaultRoot.path);
      const tree = buildFileTree(vaultRoot);
      console.log('File tree built with', tree.length, 'root items');
      setFileTree(tree);
    } catch (error) {
      console.error('Error loading file tree:', error);
      setFileTree([]);
    } finally {
      setIsLoading(false);
    }
  };

  const syncWithBackend = async () => {
    if (!apiClient || !app?.vault) return;

    try {
      // Trigger a vault scan to sync file changes
      const vaultAdapter = app.vault.adapter as any;
      const vaultPath = vaultAdapter.basePath || vaultAdapter.path || (app.vault as any).name || 'vault';
      if (!vaultPath) {
        console.warn('Cannot get vault path for sync');
        return;
      }

      console.log('Syncing with backend, vault path:', vaultPath);
      const response = await fetch(`${apiClient.getBaseUrl()}/api/v1/vault/scan`, {
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
      } else {
        console.warn('Backend sync failed:', response.statusText);
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
        const response = await fetch(`${apiClient.getBaseUrl()}/api/v1/vault/status`);
        
        if (response.ok) {
          const backendStats = await response.json();
          setProcessingStats({
            total: backendStats.total_files,
            processed: backendStats.processed,
            processing: backendStats.processing || 0,
            pending: backendStats.unprocessed,
            errors: backendStats.error
          });
          return; // Use backend stats if available
        }
      }
      
      // Calculate local stats from file tree (fallback)
      const localStats = calculateLocalStats(fileTree);
      setProcessingStats(localStats);
    } catch (error) {
      console.error('Error loading processing stats:', error);
      // Fallback to basic stats
      setProcessingStats({
        total: 0,
        processed: 0,
        processing: 0,
        pending: 0,
        errors: 0
      });
    }
  };

  const calculateLocalStats = (tree: FileNode[]): typeof processingStats => {
    const stats = { total: 0, processed: 0, processing: 0, pending: 0, errors: 0 };
    
    const countFiles = (nodes: FileNode[]) => {
      nodes.forEach(node => {
        if (node.type === 'file') {
          stats.total++;
          switch (node.status) {
            case 'processed': stats.processed++; break;
            case 'processing': stats.processing++; break;
            case 'error': stats.errors++; break;
            default: stats.pending++; break;
          }
        }
        if (node.children) {
          countFiles(node.children);
        }
      });
    };
    
    countFiles(tree);
    return stats;
  };

  const buildFileTree = (folder: TFolder): FileNode[] => {
    const nodes: FileNode[] = [];
    
    try {
      if (!folder || !folder.children) {
        console.warn('Invalid folder or no children:', folder);
        return nodes;
      }

      console.log(`Building tree for folder: ${folder.name} with ${folder.children.length} children`);
      
      const children = folder.children.slice().sort((a, b) => {
        // Folders first, then files
        if (a instanceof TFolder && b instanceof TFile) return -1;
        if (a instanceof TFile && b instanceof TFolder) return 1;
        return a.name.localeCompare(b.name);
      });

      children.forEach(child => {
        try {
          if (child instanceof TFolder) {
            const folderNode: FileNode = {
              id: child.path,
              name: child.name,
              path: child.path,
              type: 'folder',
              children: buildFileTree(child),
              isExpanded: expandedFolders.has(child.path)
            };
            nodes.push(folderNode);
          } else if (child instanceof TFile) {
            // Only include supported file types
            const supportedExtensions = ['md', 'pdf', 'txt', 'docx'];
            if (!supportedExtensions.includes(child.extension.toLowerCase())) {
              return;
            }

            const metadata = fileMetadata.get(child.path);
            const fileNode: FileNode = {
              id: child.path,
              name: child.basename,
              path: child.path,
              type: 'file',
              extension: child.extension,
              size: child.stat?.size || 0,
              modified: child.stat?.mtime ? new Date(child.stat.mtime) : new Date(),
              status: metadata?.processingStatus || 'unprocessed',
              errorMessage: metadata?.errorMessage
            };
            nodes.push(fileNode);
          }
        } catch (error) {
          console.error(`Error processing child ${child?.name}:`, error);
        }
      });

      console.log(`Built ${nodes.length} nodes for folder ${folder.name}`);
    } catch (error) {
      console.error('Error building file tree:', error);
    }

    return nodes;
  };

  // Simple filtering for search
  const filteredFiles = fileTree.filter(node => {
    if (!searchQuery) return true;
    
    // Search by name
    if (node.name.toLowerCase().includes(searchQuery.toLowerCase())) {
      return true;
    }
    
    // Search in children for folders
    if (node.type === 'folder' && node.children) {
      return node.children.some(child => 
        child.name.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }
    
    return false;
  });

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

  // Selection logic removed - using individual process buttons instead
  
  // Complex selection functions removed - using simple individual processing

  const processFile = async (filePath: string) => {
    if (!apiClient) {
      console.warn('API client not available');
      return;
    }
    
    console.log('🔄 Processing file:', filePath);

    try {
      setIsProcessing(true);
      const response = await fetch(`${apiClient.getBaseUrl()}/api/v1/documents/process-file`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: filePath })
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('❌ File processing failed:', response.status, response.statusText);
        console.error('❌ Error details:', errorText);
        throw new Error(`Failed to process file: ${response.statusText} - ${errorText}`);
      } else {
        const result = await response.json();
        console.log('✅ File processing successful:', result);
      }

      // Refresh to show updated status
      setTimeout(() => loadFileTree(), 1000);
    } catch (error) {
      console.error('Error processing file:', error);
    } finally {
      setIsProcessing(false);
    }
  };

  const processFolder = async (folderPath: string) => {
    if (!apiClient) {
      console.warn('API client not available');
      return;
    }
    
    console.log('📁 Processing folder:', folderPath);

    try {
      setIsProcessing(true);
      const response = await fetch(`${apiClient.getBaseUrl()}/api/v1/documents/process-vault`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vault_path: folderPath })
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('❌ Folder processing failed:', response.status, response.statusText);
        console.error('❌ Error details:', errorText);
        throw new Error(`Failed to process folder: ${response.statusText} - ${errorText}`);
      } else {
        const result = await response.json();
        console.log('✅ Folder processing successful:', result);
      }

      // Refresh to show updated status
      setTimeout(() => loadFileTree(), 1000);
    } catch (error) {
      console.error('Error processing folder:', error);
    } finally {
      setIsProcessing(false);
    }
  };

  const processAllPending = async () => {
    const vaultAdapter = app.vault.adapter as any;
    const vaultPath = vaultAdapter.basePath || vaultAdapter.path || (app.vault as any).name || 'vault';
    await processFolder(vaultPath);
  };

  const forceProcessFile = async (filePath: string) => {
    if (!apiClient) return;

    try {
      // First, force process the file in the watcher (bypass frequency limit)
      await fetch(`${apiClient.getBaseUrl()}/api/v1/vault/watcher/force-process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: filePath })
      });

      // Then process the file
      await processFile(filePath);
    } catch (error) {
      console.error('Error force processing file:', error);
    }
  };

  const updateFrequencyLimit = async (seconds: number) => {
    if (!apiClient) return;

    try {
      const response = await fetch(`${apiClient.getBaseUrl()}/api/v1/vault/watcher/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ frequency_limit_seconds: seconds })
      });

      if (response.ok) {
        setFrequencyLimit(seconds);
        // Refresh file tree to get updated wait times
        setTimeout(() => loadFileTree(), 1000);
        console.log(`Frequency limit updated to ${seconds} seconds`);
      }
    } catch (error) {
      console.error('Error updating frequency limit:', error);
    }
  };

  // Auto-processing functions
  const enableAutoProcessing = async () => {
    if (!apiClient) return;

    try {
      // Start watcher for the entire vault with ignore patterns
      const vaultAdapter = app.vault.adapter as any;
      const vaultPath = vaultAdapter.basePath || vaultAdapter.path || (app.vault as any).name || 'vault';
      
      console.log('🔄 Enabling auto-processing for vault:', vaultPath);
      
      const response = await fetch(`${apiClient.getBaseUrl()}/api/v1/vault/watcher/start?vault_path=${encodeURIComponent(vaultPath)}`, {
        method: 'POST'
      });
      
      if (response.ok) {
        setAutoProcessingActive(true);
        setIsWatcherActive(true);
        console.log('✅ Auto-processing enabled');
      }
    } catch (error) {
      console.error('Error enabling auto-processing:', error);
    }
  };

  const disableAutoProcessing = async () => {
    if (!apiClient) return;

    try {
      const response = await fetch(`${apiClient.getBaseUrl()}/api/v1/vault/watcher/stop`, {
        method: 'POST'
      });
      
      if (response.ok) {
        setAutoProcessingActive(false);
        setIsWatcherActive(false);
        console.log('🛑 Auto-processing disabled');
      }
    } catch (error) {
      console.error('Error disabling auto-processing:', error);
    }
  };

  // Batch processing functions removed - using individual processing buttons instead

  const checkWatcherStatus = async () => {
    if (!apiClient) return;

    try {
      const response = await fetch(`${apiClient.getBaseUrl()}/api/v1/vault/watcher/status`);
      
      if (response.ok) {
        const result = await response.json();
        const isActive = result.status?.is_watching || false;
        setIsWatcherActive(isActive);
        setAutoProcessingActive(isActive);
      }
    } catch (error) {
      console.error('Error checking watcher status:', error);
    }
  };

  // Complex selection functions removed for simplified UI

  const getFileStatus = (node: FileNode) => {
    const waitTime = fileWaitTimes.get(node.path);
    
    if (waitTime && waitTime > 0) {
      return {
        icon: '⏳',
        label: `Waiting ${waitTime}s`,
        canProcess: false,
        color: 'text-yellow-600'
      };
    }
    
    switch (node.status) {
      case 'processed':
        return {
          icon: '✓',
          label: 'Processed',
          canProcess: false,
          color: 'text-green-600'
        };
      case 'processing':
        return {
          icon: '⟳',
          label: 'Processing...',
          canProcess: false,
          color: 'text-blue-600'
        };
      case 'error':
        return {
          icon: '✗',
          label: 'Error',
          canProcess: true,
          color: 'text-red-600'
        };
      default:
        return {
          icon: '○',
          label: 'Pending',
          canProcess: true,
          color: 'text-gray-500'
        };
    }
  };

  // getStatusIcon removed - using getFileStatus instead

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
    const indentClass = `ml-${depth * 4}`;

    if (node.type === 'folder') {
      const folderFileCount = node.children ? node.children.filter(c => c.type === 'file').length : 0;
      const pendingCount = node.children ? 
        node.children.filter(c => c.type === 'file' && c.status === 'unprocessed').length : 0;

      return (
        <div key={node.id} className="mb-1">
          <div className={`flex items-center p-2 hover:bg-gray-50 rounded ${indentClass}`}>
            <button 
              onClick={() => toggleFolderExpansion(node.path)}
              className="w-6 h-6 flex items-center justify-center mr-2 hover:bg-gray-200 rounded"
            >
              <span className="text-xs">{node.isExpanded ? '▼' : '▶'}</span>
            </button>
            
            <span className="text-base mr-2">📁</span>
            <span className="flex-1 font-medium">
              {node.name}
            </span>
            
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <span>{folderFileCount} files</span>
              {pendingCount > 0 && (
                <button
                  onClick={() => processFolder(node.path)}
                  disabled={isProcessing}
                  className="px-2 py-1 bg-blue-500 text-white rounded text-xs hover:bg-blue-600 disabled:opacity-50"
                >
                  {isProcessing ? 'Processing...' : `Process ${pendingCount}`}
                </button>
              )}
            </div>
          </div>
          
          {node.isExpanded && node.children && (
            <div className="ml-4 border-l border-gray-200 pl-2">
              {node.children.map(child => renderNode(child, depth + 1))}
            </div>
          )}
        </div>
      );
    }

    // File node
    const status = getFileStatus(node);
    
    return (
      <div key={node.id} className={`flex items-center p-2 hover:bg-gray-50 rounded ${indentClass}`}>
        <div className="w-6 mr-2"></div> {/* Spacer for alignment */}
        
        <span className={`w-4 mr-2 ${status.color}`}>
          {status.icon}
        </span>
        
        <span className="text-base mr-2">{getFileTypeIcon(node.extension)}</span>
        <span 
          className="flex-1 truncate cursor-pointer hover:text-blue-600"
          onClick={() => {
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
        
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">
            {formatFileSize(node.size)}
          </span>
          
          {node.errorMessage && (
            <span className="text-xs text-red-500" title={node.errorMessage}>⚠</span>
          )}
          
          {status.canProcess && (
            <div className="flex gap-1">
              <button
                onClick={() => processFile(node.path)}
                disabled={isProcessing}
                className="px-2 py-1 bg-blue-500 text-white rounded text-xs hover:bg-blue-600 disabled:opacity-50"
              >
                Process
              </button>
              {status.label === 'Waiting' && (
                <button
                  onClick={() => forceProcessFile(node.path)}
                  disabled={isProcessing}
                  className="px-2 py-1 bg-orange-500 text-white rounded text-xs hover:bg-orange-600 disabled:opacity-50"
                  title="Force process (bypass frequency limit)"
                >
                  Force
                </button>
              )}
            </div>
          )}
          
          {!status.canProcess && (
            <span className={`text-xs px-2 py-1 rounded ${status.color}`}>
              {status.label}
            </span>
          )}
        </div>
      </div>
    );
  };

  // Keyboard shortcuts removed for simplified UI

  return (
    <div className={`flex flex-col h-full ${className}`} tabIndex={0}>
      {/* Header */}
      <div className="p-4 border-b">
        <h3 className="text-lg font-semibold mb-2">Document Processing</h3>
        
        {/* Stats Overview */}
        <div className="grid grid-cols-4 gap-3 mb-4">
          <div className="text-center p-2 bg-green-50 rounded">
            <div className="text-lg font-bold text-green-600">{processingStats.processed}</div>
            <div className="text-xs text-gray-600">Processed</div>
          </div>
          <div className="text-center p-2 bg-blue-50 rounded">
            <div className="text-lg font-bold text-blue-600">{processingStats.processing}</div>
            <div className="text-xs text-gray-600">Processing</div>
          </div>
          <div className="text-center p-2 bg-gray-50 rounded">
            <div className="text-lg font-bold text-gray-600">{processingStats.pending}</div>
            <div className="text-xs text-gray-600">Pending</div>
          </div>
          <div className="text-center p-2 bg-red-50 rounded">
            <div className="text-lg font-bold text-red-600">{processingStats.errors}</div>
            <div className="text-xs text-gray-600">Errors</div>
          </div>
        </div>

        {/* Global Actions */}
        <div className="flex gap-2 mb-4">
          <button
            onClick={processAllPending}
            disabled={processingStats.pending === 0 || isProcessing}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isProcessing ? 'Processing...' : `Process All Pending (${processingStats.pending})`}
          </button>
          <button
            onClick={loadFileTree}
            className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
          >
            Refresh
          </button>
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
          >
            ⚙️ Settings
          </button>
          <button
            onClick={autoProcessingActive ? disableAutoProcessing : enableAutoProcessing}
            className={`px-4 py-2 rounded ${autoProcessingActive ? 'bg-green-500 hover:bg-green-600 text-white' : 'border border-gray-300 hover:bg-gray-50'}`}
          >
            {autoProcessingActive ? '🟢 Auto-Processing ON' : '⚪ Auto-Processing OFF'}
          </button>
        </div>

        {/* Settings Panel */}
        {showSettings && (
          <div className="mb-4 p-4 bg-gray-50 rounded border">
            <h4 className="font-medium mb-3">Processing Settings</h4>
            
            <div className="mb-3">
              <label className="block text-sm font-medium mb-1">
                Frequency Limit: {frequencyLimit}s
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  min="10"
                  max="300"
                  step="10"
                  value={frequencyLimit}
                  onChange={(e) => {
                    const value = parseInt(e.target.value);
                    setFrequencyLimit(value);
                  }}
                  className="flex-1"
                />
                <button
                  onClick={() => updateFrequencyLimit(frequencyLimit)}
                  className="px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600"
                >
                  Apply
                </button>
              </div>
              <div className="flex gap-2 mt-2">
                {[30, 60, 120, 300].map(seconds => (
                  <button
                    key={seconds}
                    onClick={() => {
                      setFrequencyLimit(seconds);
                      updateFrequencyLimit(seconds);
                    }}
                    className="px-2 py-1 text-xs border border-gray-300 rounded hover:bg-gray-100"
                  >
                    {seconds}s
                  </button>
                ))}
              </div>
              <p className="text-xs text-gray-600 mt-1">
                Minimum time between processing the same file. Higher values prevent excessive processing during heavy editing.
              </p>
            </div>
          </div>
        )}

        {/* Auto-Processing Status */}
        {autoProcessingActive && (
          <div className="mb-4 p-3 bg-green-50 rounded border border-green-200">
            <div className="flex items-center gap-2">
              <span className="text-green-600">🟢</span>
              <span className="font-medium text-green-800">Auto-Processing Active</span>
            </div>
            <div className="mt-1 text-sm text-green-700">
              All files are automatically processed except those matching ignore patterns in plugin settings.
            </div>
            <div className="mt-2 text-xs text-green-600">
              💡 Configure ignore patterns in Settings → Community plugins → NotebookLocal → Auto-processing ignore config
            </div>
          </div>
        )}
      </div>

      {/* Search and Filter */}
      <div className="p-4 border-b">
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Search files..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="flex-1 px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* File Tree */}
      <div className="flex-1 overflow-y-auto p-4">
        {isLoading ? (
          <div className="text-center py-8">
            <div className="text-gray-500">Loading files...</div>
          </div>
        ) : fileTree.length > 0 ? (
          <div>
            {fileTree
              .filter(node => !searchQuery || 
                node.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                (node.children && node.children.some(child => 
                  child.name.toLowerCase().includes(searchQuery.toLowerCase())
                ))
              )
              .map(node => renderNode(node))}
          </div>
        ) : (
          <div className="text-center py-8">
            <div className="text-4xl mb-2">📁</div>
            <div className="text-gray-500">
              {searchQuery ? 'No files found matching your search' : 'No supported files found in vault'}
            </div>
            {searchQuery ? (
              <div className="text-sm text-gray-400 mt-1">Try adjusting your search terms</div>
            ) : (
              <div className="text-sm text-gray-400 mt-1">
                Supported files: .md, .pdf, .txt, .docx<br/>
                Make sure your vault has files or check console for errors
              </div>
            )}
            <button
              onClick={() => {
                console.log('🔄 Force refresh triggered');
                loadFileTree();
              }}
              className="mt-4 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm"
            >
              🔄 Refresh Files
            </button>
          </div>
        )}
      </div>
    </div>
  );
};