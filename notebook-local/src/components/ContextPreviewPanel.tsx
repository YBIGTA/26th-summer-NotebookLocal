/**
 * ContextPreviewPanel - Visualize current RAG context
 * 
 * Features:
 * - Show selected files, folders, and tags
 * - Display processing status with indicators
 * - Quick actions (remove, reprocess, navigate)
 * - Context statistics and validation
 * - Collapsible sections
 */

import React, { useState, useEffect } from 'react';
import { TFile } from 'obsidian';
import { RagContext, RagContextManager, ContextValidationResult } from '../context/RagContextManager';
import { VaultFileCache, VaultFileMetadata } from '../vault/VaultFileCache';

interface ContextPreviewPanelProps {
  ragContext: RagContext;
  onContextChange: (context: RagContext) => void;
  className?: string;
}

interface FileItem {
  path: string;
  name: string;
  status: 'processed' | 'queued' | 'processing' | 'unprocessed' | 'error';
  errorMessage?: string;
  size?: number;
  lastModified?: Date;
}

export const ContextPreviewPanel: React.FC<ContextPreviewPanelProps> = ({
  ragContext,
  onContextChange,
  className = ""
}) => {
  const [validation, setValidation] = useState<ContextValidationResult | null>(null);
  const [fileDetails, setFileDetails] = useState<Map<string, FileItem>>(new Map());
  const [expandedSections, setExpandedSections] = useState({
    files: true,
    folders: true,
    tags: true,
    temporal: false,
    stats: false
  });
  const [isLoading, setIsLoading] = useState(false);

  const ragContextManager = RagContextManager.getInstance();
  const fileCache = VaultFileCache.getInstance<string>();

  // Update validation and file details when context changes
  useEffect(() => {
    updateContextDetails();
  }, [ragContext]);

  const updateContextDetails = async () => {
    setIsLoading(true);
    try {
      // Validate context
      const validationResult = await ragContextManager.validateContextSelection();
      setValidation(validationResult);

      // Get file details
      const fileDetailsMap = new Map<string, FileItem>();
      
      // Process selected files
      for (const filePath of ragContext.selectedFiles) {
        const file = app.vault.getAbstractFileByPath(filePath);
        if (file instanceof TFile) {
          const metadata = fileCache.getMetadata(filePath);
          const fileItem: FileItem = {
            path: filePath,
            name: file.basename,
            status: metadata?.processing_status || 'unprocessed',
            errorMessage: metadata?.error_message,
            size: file.stat.size,
            lastModified: new Date(file.stat.mtime)
          };
          fileDetailsMap.set(filePath, fileItem);
        }
      }

      // Process files from selected folders
      for (const folderPath of ragContext.selectedFolders) {
        const folder = app.vault.getAbstractFileByPath(folderPath);
        if (folder) {
          const filesInFolder = getFilesInFolder(folderPath);
          filesInFolder.forEach(file => {
            const metadata = fileCache.getMetadata(file.path);
            const fileItem: FileItem = {
              path: file.path,
              name: file.basename,
              status: metadata?.processing_status || 'unprocessed',
              errorMessage: metadata?.error_message,
              size: file.stat.size,
              lastModified: new Date(file.stat.mtime)
            };
            fileDetailsMap.set(file.path, fileItem);
          });
        }
      }

      setFileDetails(fileDetailsMap);
    } catch (error) {
      console.error('Error updating context details:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const getFilesInFolder = (folderPath: string): TFile[] => {
    const folder = app.vault.getAbstractFileByPath(folderPath);
    if (!folder || !('children' in folder)) {
      return [];
    }

    const files: TFile[] = [];
    const collectFiles = (currentFolder: any) => {
      currentFolder.children?.forEach((child: any) => {
        if (child instanceof TFile) {
          files.push(child);
        } else if ('children' in child) {
          collectFiles(child);
        }
      });
    };

    collectFiles(folder);
    return files;
  };

  const removeFromContext = async (type: 'file' | 'folder' | 'tag', item: string) => {
    const newContext = { ...ragContext };
    
    switch (type) {
      case 'file':
        newContext.selectedFiles.delete(item);
        break;
      case 'folder':
        newContext.selectedFolders.delete(item);
        break;
      case 'tag':
        newContext.selectedTags.delete(item);
        break;
    }
    
    newContext.lastUpdated = new Date();
    onContextChange(newContext);
  };

  const reprocessFile = async (filePath: string) => {
    const file = app.vault.getAbstractFileByPath(filePath);
    if (file instanceof TFile) {
      const processingManager = ragContextManager.getProcessingManager();
      await processingManager.processSingleFile(file, true);
      await updateContextDetails();
    }
  };

  const navigateToFile = (filePath: string) => {
    const file = app.vault.getAbstractFileByPath(filePath);
    if (file instanceof TFile) {
      const leaf = app.workspace.getLeaf(false);
      leaf.openFile(file);
    }
  };

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const getStatusIcon = (status: string): string => {
    const icons = {
      processed: '🟢',
      queued: '🟡',
      processing: '🔄',
      unprocessed: '⚪',
      error: '🔴'
    };
    return icons[status as keyof typeof icons] || '❓';
  };

  const getStatusColor = (status: string): string => {
    const colors = {
      processed: 'text-green-600',
      queued: 'text-yellow-600', 
      processing: 'text-blue-600',
      unprocessed: 'text-gray-400',
      error: 'text-red-600'
    };
    return colors[status as keyof typeof colors] || 'text-gray-400';
  };

  const getRagScopeIcon = () => {
    switch (ragContext.scope) {
      case 'whole': return '🌍';
      case 'selected': return '📋';
      case 'folder': return '📁';
      default: return '❓';
    }
  };

  if (!ragContext.enabled) {
    return (
      <div className={`p-4 border border-border rounded-lg bg-muted ${className}`}>
        <div className="text-center text-muted-foreground">
          <div className="text-2xl mb-2">🔴</div>
          <div className="font-medium">RAG Disabled</div>
          <div className="text-sm mt-1">Use /rag-enable to activate</div>
        </div>
      </div>
    );
  }

  return (
    <div className={`border border-border rounded-lg bg-background ${className}`}>
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-lg">🟢</span>
            <span className="font-semibold">RAG Context</span>
            <span className="text-xs text-muted-foreground">
              ({ragContext.scope})
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-lg">{getRagScopeIcon()}</span>
            {isLoading && (
              <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            )}
          </div>
        </div>
      </div>

      <div className="max-h-96 overflow-y-auto">
        {/* Selected Files */}
        {ragContext.selectedFiles.size > 0 && (
          <div className="p-4 border-b border-border">
            <button
              onClick={() => toggleSection('files')}
              className="flex items-center gap-2 w-full text-left hover:bg-muted p-2 rounded"
            >
              <span>{expandedSections.files ? '▼' : '▶'}</span>
              <span className="font-medium">📄 Files ({ragContext.selectedFiles.size})</span>
            </button>
            
            {expandedSections.files && (
              <div className="mt-2 space-y-2">
                {Array.from(ragContext.selectedFiles).map(filePath => {
                  const fileItem = fileDetails.get(filePath);
                  return (
                    <div key={filePath} className="flex items-center gap-2 p-2 bg-muted rounded text-sm">
                      <span>{getStatusIcon(fileItem?.status || 'unprocessed')}</span>
                      <span className="flex-1 truncate" title={filePath}>
                        {fileItem?.name || filePath}
                      </span>
                      <div className="flex gap-1">
                        {fileItem?.status === 'error' && (
                          <button
                            onClick={() => reprocessFile(filePath)}
                            className="px-1 py-0.5 bg-yellow-100 text-yellow-700 rounded text-xs hover:bg-yellow-200"
                            title="Reprocess file"
                          >
                            🔄
                          </button>
                        )}
                        <button
                          onClick={() => navigateToFile(filePath)}
                          className="px-1 py-0.5 bg-blue-100 text-blue-700 rounded text-xs hover:bg-blue-200"
                          title="Open file"
                        >
                          📂
                        </button>
                        <button
                          onClick={() => removeFromContext('file', filePath)}
                          className="px-1 py-0.5 bg-red-100 text-red-700 rounded text-xs hover:bg-red-200"
                          title="Remove from context"
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Selected Folders */}
        {ragContext.selectedFolders.size > 0 && (
          <div className="p-4 border-b border-border">
            <button
              onClick={() => toggleSection('folders')}
              className="flex items-center gap-2 w-full text-left hover:bg-muted p-2 rounded"
            >
              <span>{expandedSections.folders ? '▼' : '▶'}</span>
              <span className="font-medium">📁 Folders ({ragContext.selectedFolders.size})</span>
            </button>
            
            {expandedSections.folders && (
              <div className="mt-2 space-y-2">
                {Array.from(ragContext.selectedFolders).map(folderPath => {
                  const filesInFolder = getFilesInFolder(folderPath);
                  const processedCount = filesInFolder.filter(file => {
                    const metadata = fileCache.getMetadata(file.path);
                    return metadata?.processing_status === 'processed';
                  }).length;
                  
                  return (
                    <div key={folderPath} className="p-2 bg-muted rounded text-sm">
                      <div className="flex items-center gap-2">
                        <span>📁</span>
                        <span className="flex-1 truncate" title={folderPath}>
                          {folderPath}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {processedCount}/{filesInFolder.length}
                        </span>
                        <button
                          onClick={() => removeFromContext('folder', folderPath)}
                          className="px-1 py-0.5 bg-red-100 text-red-700 rounded text-xs hover:bg-red-200"
                          title="Remove from context"
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Selected Tags */}
        {ragContext.selectedTags.size > 0 && (
          <div className="p-4 border-b border-border">
            <button
              onClick={() => toggleSection('tags')}
              className="flex items-center gap-2 w-full text-left hover:bg-muted p-2 rounded"
            >
              <span>{expandedSections.tags ? '▼' : '▶'}</span>
              <span className="font-medium">🏷️ Tags ({ragContext.selectedTags.size})</span>
            </button>
            
            {expandedSections.tags && (
              <div className="mt-2 space-y-2">
                {Array.from(ragContext.selectedTags).map(tag => (
                  <div key={tag} className="flex items-center gap-2 p-2 bg-muted rounded text-sm">
                    <span>🏷️</span>
                    <span className="flex-1">#{tag}</span>
                    <button
                      onClick={() => removeFromContext('tag', tag)}
                      className="px-1 py-0.5 bg-red-100 text-red-700 rounded text-xs hover:bg-red-200"
                      title="Remove from context"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Temporal Filters */}
        {(ragContext.temporalFilters.includeRecent || ragContext.temporalFilters.includeActive) && (
          <div className="p-4 border-b border-border">
            <button
              onClick={() => toggleSection('temporal')}
              className="flex items-center gap-2 w-full text-left hover:bg-muted p-2 rounded"
            >
              <span>{expandedSections.temporal ? '▼' : '▶'}</span>
              <span className="font-medium">🕒 Temporal Filters</span>
            </button>
            
            {expandedSections.temporal && (
              <div className="mt-2 space-y-2">
                {ragContext.temporalFilters.includeRecent && (
                  <div className="flex items-center gap-2 p-2 bg-muted rounded text-sm">
                    <span>🕒</span>
                    <span>Recently modified files</span>
                  </div>
                )}
                {ragContext.temporalFilters.includeActive && (
                  <div className="flex items-center gap-2 p-2 bg-muted rounded text-sm">
                    <span>📝</span>
                    <span>Active file</span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Context Statistics */}
        {validation && (
          <div className="p-4">
            <button
              onClick={() => toggleSection('stats')}
              className="flex items-center gap-2 w-full text-left hover:bg-muted p-2 rounded"
            >
              <span>{expandedSections.stats ? '▼' : '▶'}</span>
              <span className="font-medium">📊 Statistics</span>
              {!validation.isValid && <span className="text-red-500">⚠️</span>}
            </button>
            
            {expandedSections.stats && (
              <div className="mt-2 space-y-2 text-sm">
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2 bg-muted rounded">
                    <div className="text-xs text-muted-foreground">Total Files</div>
                    <div className="font-medium">{validation.stats.totalFiles}</div>
                  </div>
                  <div className="p-2 bg-muted rounded">
                    <div className="text-xs text-muted-foreground">Processed</div>
                    <div className="font-medium text-green-600">{validation.stats.processedFiles}</div>
                  </div>
                  <div className="p-2 bg-muted rounded">
                    <div className="text-xs text-muted-foreground">Unprocessed</div>
                    <div className="font-medium text-yellow-600">{validation.stats.unprocessedFiles}</div>
                  </div>
                  <div className="p-2 bg-muted rounded">
                    <div className="text-xs text-muted-foreground">Est. Tokens</div>
                    <div className="font-medium">{Math.round(validation.stats.estimatedTokens / 1000)}k</div>
                  </div>
                </div>

                {/* Warnings */}
                {validation.warnings.length > 0 && (
                  <div className="mt-2">
                    <div className="text-xs font-medium text-yellow-600 mb-1">Warnings:</div>
                    {validation.warnings.map((warning, index) => (
                      <div key={index} className="text-xs text-yellow-600 pl-2">
                        ⚠️ {warning}
                      </div>
                    ))}
                  </div>
                )}

                {/* Errors */}
                {validation.errors.length > 0 && (
                  <div className="mt-2">
                    <div className="text-xs font-medium text-red-600 mb-1">Errors:</div>
                    {validation.errors.map((error, index) => (
                      <div key={index} className="text-xs text-red-600 pl-2">
                        ❌ {error}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Empty State */}
      {ragContext.selectedFiles.size === 0 && 
       ragContext.selectedFolders.size === 0 && 
       ragContext.selectedTags.size === 0 &&
       ragContext.scope !== 'whole' && (
        <div className="p-8 text-center text-muted-foreground">
          <div className="text-2xl mb-2">📝</div>
          <div className="font-medium">No Context Selected</div>
          <div className="text-sm mt-1">
            Use @mentions to add files, folders, or tags
          </div>
        </div>
      )}

      {/* Whole Vault Mode */}
      {ragContext.scope === 'whole' && (
        <div className="p-4 text-center">
          <div className="text-2xl mb-2">🌍</div>
          <div className="font-medium">Whole Vault Mode</div>
          <div className="text-sm text-muted-foreground mt-1">
            All vault files are included in RAG context
          </div>
        </div>
      )}
    </div>
  );
};