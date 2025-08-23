/**
 * RagContextManager - Manage RAG context state and command execution
 * 
 * Features:
 * - Execute slash commands and @ mentions
 * - Track selected files, folders, and tags for RAG context
 * - Build context for AI requests
 * - Validate context selection
 * - Integrate with VaultProcessingManager
 */

import { App, TFile, TFolder, TAbstractFile } from "obsidian";
import { CommandParser, SlashCommand, AtMention } from "./CommandParser";
import { VaultProcessingManager } from "../vault/VaultProcessingManager";
import { VaultFileCache } from "../vault/VaultFileCache";
import { ApiClient } from "../api/ApiClient-clean";

export interface RagContext {
  enabled: boolean;
  scope: 'whole' | 'selected' | 'folder';
  selectedFiles: Set<string>;
  selectedFolders: Set<string>;
  selectedTags: Set<string>;
  temporalFilters: {
    includeRecent?: boolean;
    includeActive?: boolean;
    dateRange?: { start: Date; end: Date };
  };
  lastUpdated: Date;
}

export interface ContextValidationResult {
  isValid: boolean;
  warnings: string[];
  errors: string[];
  stats: {
    totalFiles: number;
    processedFiles: number;
    unprocessedFiles: number;
    estimatedTokens: number;
  };
}

export interface RagContextChangeEvent {
  type: 'enabled' | 'disabled' | 'scope-changed' | 'files-added' | 'files-removed' | 'folders-added' | 'folders-removed';
  context: RagContext;
  changes: any;
}

export class RagContextManager {
  private static instance: RagContextManager;
  private context: RagContext;
  private commandParser: CommandParser;
  private processingManager: VaultProcessingManager;
  private fileCache: VaultFileCache<string>;
  private apiClient: ApiClient;
  
  // Event handlers
  private changeHandlers: Set<(event: RagContextChangeEvent) => void> = new Set();

  private constructor(
    private app: App,
    apiClient: ApiClient
  ) {
    this.apiClient = apiClient;
    this.commandParser = CommandParser.getInstance();
    this.processingManager = new VaultProcessingManager(this.app, this.apiClient);
    this.fileCache = VaultFileCache.getInstance<string>();
    
    this.context = this.initializeContext();
  }

  static getInstance(app?: App, apiClient?: ApiClient): RagContextManager {
    if (!RagContextManager.instance) {
      if (!app || !apiClient) {
        throw new Error("RagContextManager requires app and apiClient on first initialization");
      }
      RagContextManager.instance = new RagContextManager(app, apiClient);
    }
    return RagContextManager.instance;
  }

  private initializeContext(): RagContext {
    return {
      enabled: false,
      scope: 'whole',
      selectedFiles: new Set(),
      selectedFolders: new Set(),
      selectedTags: new Set(),
      temporalFilters: {},
      lastUpdated: new Date()
    };
  }

  /**
   * Execute slash commands
   */
  async executeSlashCommand(command: SlashCommand): Promise<string> {
    const { command: cmd, args } = command;
    
    try {
      switch (cmd) {
        case 'rag-toggle':
          return this.handleRagToggle();
          
        case 'rag-enable':
          return this.handleRagEnable();
          
        case 'rag-disable':
          return this.handleRagDisable();
          
        case 'rag-scope':
          return this.handleRagScope(args);
          
        case 'rag-clear':
          return this.handleRagClear();
          
        case 'rag-status':
          return this.handleRagStatus();
          
        case 'process-file':
          return this.handleProcessFile(args);
          
        case 'process-folder':
          return this.handleProcessFolder(args);
          
        case 'reindex-vault':
          return this.handleReindexVault();
          
        case 'show-files':
          return this.handleShowFiles(args);
          
        case 'show-queue':
          return this.handleShowQueue();
          
        default:
          return `Unknown command: ${cmd}`;
      }
    } catch (error) {
      console.error("Error executing slash command:", error);
      return `Error executing command ${cmd}: ${error.message || error}`;
    }
  }

  /**
   * Process @ mentions to add to context
   */
  async processAtMention(mention: AtMention): Promise<string> {
    const { type, target } = mention;
    
    try {
      switch (type) {
        case 'file':
          return this.addFileToContext(target);
          
        case 'folder':
          return this.addFolderToContext(target);
          
        case 'tag':
          return this.addTagToContext(target);
          
        case 'special':
          return this.handleSpecialMention(target);
          
        default:
          return `Unknown mention type: ${type}`;
      }
    } catch (error) {
      console.error("Error processing @ mention:", error);
      return `Error processing mention @${target}: ${error.message || error}`;
    }
  }

  // Slash command handlers
  private handleRagToggle(): string {
    this.context.enabled = !this.context.enabled;
    this.context.lastUpdated = new Date();
    
    this.notifyContextChange({
      type: this.context.enabled ? 'enabled' : 'disabled',
      context: this.context,
      changes: { enabled: this.context.enabled }
    });
    
    return `RAG ${this.context.enabled ? 'enabled' : 'disabled'}`;
  }

  private handleRagEnable(): string {
    this.context.enabled = true;
    this.context.lastUpdated = new Date();
    
    this.notifyContextChange({
      type: 'enabled',
      context: this.context,
      changes: { enabled: true }
    });
    
    return "RAG enabled";
  }

  private handleRagDisable(): string {
    this.context.enabled = false;
    this.context.lastUpdated = new Date();
    
    this.notifyContextChange({
      type: 'disabled', 
      context: this.context,
      changes: { enabled: false }
    });
    
    return "RAG disabled";
  }

  private handleRagScope(args: string[]): string {
    if (args.length === 0) {
      return `Current RAG scope: ${this.context.scope}`;
    }

    const newScope = args[0] as RagContext['scope'];
    if (!['whole', 'selected', 'folder'].includes(newScope)) {
      return "Invalid scope. Use: whole, selected, or folder";
    }

    const oldScope = this.context.scope;
    this.context.scope = newScope;
    this.context.lastUpdated = new Date();
    
    this.notifyContextChange({
      type: 'scope-changed',
      context: this.context,
      changes: { scope: { from: oldScope, to: newScope } }
    });
    
    return `RAG scope set to: ${newScope}`;
  }

  private handleRagClear(): string {
    const cleared = {
      files: this.context.selectedFiles.size,
      folders: this.context.selectedFolders.size,
      tags: this.context.selectedTags.size
    };
    
    this.context.selectedFiles.clear();
    this.context.selectedFolders.clear();
    this.context.selectedTags.clear();
    this.context.temporalFilters = {};
    this.context.lastUpdated = new Date();
    
    this.notifyContextChange({
      type: 'files-removed',
      context: this.context,
      changes: { cleared }
    });
    
    return `RAG context cleared (${cleared.files} files, ${cleared.folders} folders, ${cleared.tags} tags)`;
  }

  private async handleRagStatus(): Promise<string> {
    const validation = await this.validateContextSelection();
    const stats = this.processingManager.getProcessingStats();
    
    const statusLines = [
      `RAG Status: ${this.context.enabled ? '🟢 Enabled' : '🔴 Disabled'}`,
      `Scope: ${this.context.scope}`,
      `Selected Files: ${this.context.selectedFiles.size}`,
      `Selected Folders: ${this.context.selectedFolders.size}`,
      `Selected Tags: ${this.context.selectedTags.size}`,
      ``,
      `Vault Processing:`,
      `  Processed: ${stats.processedFiles}`,
      `  Queued: ${stats.queuedFiles}`,
      `  Errors: ${stats.errorFiles}`,
      `  Unprocessed: ${stats.unprocessedFiles}`,
    ];

    if (validation.warnings.length > 0) {
      statusLines.push(``, `Warnings:`, ...validation.warnings.map(w => `  ⚠️ ${w}`));
    }

    if (validation.errors.length > 0) {
      statusLines.push(``, `Errors:`, ...validation.errors.map(e => `  ❌ ${e}`));
    }

    return statusLines.join('\n');
  }

  private async handleProcessFile(args: string[]): Promise<string> {
    if (args.length === 0) {
      return "Please specify a file to process";
    }

    const fileName = args[0];
    const file = this.findFile(fileName);
    
    if (!file) {
      return `File not found: ${fileName}`;
    }

    const success = await this.processingManager.processSingleFile(file, false);
    return success ? `File queued for processing: ${fileName}` : `Failed to queue file: ${fileName}`;
  }

  private async handleProcessFolder(args: string[]): Promise<string> {
    if (args.length === 0) {
      return "Please specify a folder to process";
    }

    const folderName = args[0];
    const files = this.getFilesInFolder(folderName);
    
    if (files.length === 0) {
      return `No files found in folder: ${folderName}`;
    }

    await this.processingManager.queueFiles(files);
    return `Queued ${files.length} files from folder: ${folderName}`;
  }

  private async handleReindexVault(): Promise<string> {
    const allFiles = this.app.vault.getMarkdownFiles();
    const result = await this.processingManager.processVaultFiles(allFiles, true);
    return `Vault reindexing completed: ${result.processed} processed, ${result.errors} errors`;
  }

  private handleShowFiles(args: string[]): string {
    const status = args[0] as any;
    const filesByStatus = status ? 
      this.processingManager.getFilesByStatus(status) : 
      [];
    
    if (status && filesByStatus.length === 0) {
      return `No files found with status: ${status}`;
    }

    const stats = this.processingManager.getProcessingStats();
    const lines = [
      `File Processing Status:`,
      `  🟢 Processed: ${stats.processedFiles}`,
      `  🟡 Queued: ${stats.queuedFiles}`, 
      `  🔄 Processing: 0`, // TODO: Add processing count
      `  ⚪ Unprocessed: ${stats.unprocessedFiles}`,
      `  🔴 Errors: ${stats.errorFiles}`
    ];

    if (status && filesByStatus.length > 0) {
      lines.push(``, `Files with status '${status}':`);
      filesByStatus.slice(0, 10).forEach(file => {
        lines.push(`  ${file.vault_path}`);
      });
      if (filesByStatus.length > 10) {
        lines.push(`  ... and ${filesByStatus.length - 10} more`);
      }
    }

    return lines.join('\n');
  }

  private handleShowQueue(): string {
    const queuedFiles = this.processingManager.getFilesByStatus('queued');
    
    if (queuedFiles.length === 0) {
      return "Processing queue is empty";
    }

    const lines = [`Processing Queue (${queuedFiles.length} files):`];
    queuedFiles.slice(0, 20).forEach((file, index) => {
      lines.push(`  ${index + 1}. ${file.vault_path}`);
    });
    
    if (queuedFiles.length > 20) {
      lines.push(`  ... and ${queuedFiles.length - 20} more`);
    }

    return lines.join('\n');
  }

  // @ mention handlers
  private addFileToContext(fileName: string): string {
    const file = this.findFile(fileName);
    
    if (!file) {
      return `File not found: ${fileName}`;
    }

    this.context.selectedFiles.add(file.path);
    this.context.lastUpdated = new Date();
    
    this.notifyContextChange({
      type: 'files-added',
      context: this.context,
      changes: { addedFiles: [file.path] }
    });
    
    return `Added file to RAG context: ${fileName}`;
  }

  private addFolderToContext(folderName: string): string {
    const folder = this.findFolder(folderName);
    
    if (!folder) {
      return `Folder not found: ${folderName}`;
    }

    this.context.selectedFolders.add(folder.path);
    this.context.lastUpdated = new Date();
    
    this.notifyContextChange({
      type: 'folders-added',
      context: this.context,
      changes: { addedFolders: [folder.path] }
    });
    
    return `Added folder to RAG context: ${folderName}`;
  }

  private addTagToContext(tagName: string): string {
    // TODO: Validate that tag exists in vault
    this.context.selectedTags.add(tagName);
    this.context.lastUpdated = new Date();
    
    return `Added tag to RAG context: #${tagName}`;
  }

  private handleSpecialMention(target: string): string {
    switch (target) {
      case 'recent':
        this.context.temporalFilters.includeRecent = true;
        this.context.lastUpdated = new Date();
        return "Added recently modified files to RAG context";
        
      case 'active':
        this.context.temporalFilters.includeActive = true;
        this.context.lastUpdated = new Date();
        return "Added active file to RAG context";
        
      case 'current':
        return this.handleCurrentFile();
        
      case 'all':
        this.context.scope = 'whole';
        this.context.lastUpdated = new Date();
        return "Set RAG scope to whole vault";
        
      default:
        return `Unknown special mention: ${target}`;
    }
  }

  private handleCurrentFile(): string {
    const activeFile = this.app.workspace.getActiveFile();
    
    if (!activeFile) {
      return "No active file";
    }

    this.context.selectedFiles.add(activeFile.path);
    this.context.lastUpdated = new Date();
    
    return `Added current file to RAG context: ${activeFile.basename}`;
  }

  // Helper methods
  private findFile(fileName: string): TFile | null {
    // Try exact match first
    let file = this.app.vault.getAbstractFileByPath(fileName);
    if (file instanceof TFile) {
      return file;
    }

    // Try with .md extension
    if (!fileName.endsWith('.md')) {
      file = this.app.vault.getAbstractFileByPath(fileName + '.md');
      if (file instanceof TFile) {
        return file;
      }
    }

    // Search by basename
    const allFiles = this.app.vault.getFiles();
    return allFiles.find(f => 
      f.basename === fileName || 
      f.basename === fileName.replace(/\.md$/, '') ||
      f.name === fileName
    ) || null;
  }

  private findFolder(folderName: string): TFolder | null {
    const folder = this.app.vault.getAbstractFileByPath(folderName);
    return folder instanceof TFolder ? folder : null;
  }

  private getFilesInFolder(folderName: string): TFile[] {
    const folder = this.findFolder(folderName);
    if (!folder) {
      return [];
    }

    const files: TFile[] = [];
    
    const collectFiles = (currentFolder: TFolder) => {
      currentFolder.children.forEach(child => {
        if (child instanceof TFile) {
          files.push(child);
        } else if (child instanceof TFolder) {
          collectFiles(child);
        }
      });
    };

    collectFiles(folder);
    return files;
  }

  private notifyContextChange(event: RagContextChangeEvent): void {
    this.changeHandlers.forEach(handler => {
      try {
        handler(event);
      } catch (error) {
        console.error("Error in context change handler:", error);
      }
    });
  }

  /**
   * Build context string for AI request
   */
  async buildContextForMessage(message: string): Promise<string> {
    if (!this.context.enabled) {
      return message;
    }

    const contextFiles = await this.resolveContextFiles();
    
    if (contextFiles.length === 0) {
      return message;
    }

    // Build context from files
    const contextParts: string[] = [];
    
    for (const file of contextFiles.slice(0, 50)) { // Limit to prevent token overflow
      try {
        const content = await this.app.vault.cachedRead(file);
        contextParts.push(`--- ${file.path} ---\n${content}\n`);
      } catch (error) {
        console.warn("Failed to read file for context:", file.path, error);
      }
    }

    if (contextParts.length === 0) {
      return message;
    }

    return `${message}\n\n--- RAG Context ---\n${contextParts.join('\n')}`;
  }

  private async resolveContextFiles(): Promise<TFile[]> {
    const files: TFile[] = [];
    
    switch (this.context.scope) {
      case 'whole':
        files.push(...this.app.vault.getMarkdownFiles());
        break;
        
      case 'selected':
        // Add selected files
        this.context.selectedFiles.forEach(filePath => {
          const file = this.app.vault.getAbstractFileByPath(filePath);
          if (file instanceof TFile) {
            files.push(file);
          }
        });
        
        // Add files from selected folders
        this.context.selectedFolders.forEach(folderPath => {
          const folderFiles = this.getFilesInFolder(folderPath);
          files.push(...folderFiles);
        });
        
        // TODO: Add files with selected tags
        break;
        
      case 'folder':
        // TODO: Implement folder-specific logic
        break;
    }

    // Apply temporal filters
    let filteredFiles = files;
    
    if (this.context.temporalFilters.includeRecent) {
      const recentThreshold = Date.now() - (7 * 24 * 60 * 60 * 1000); // 7 days
      filteredFiles = filteredFiles.filter(file => file.stat.mtime > recentThreshold);
    }

    if (this.context.temporalFilters.includeActive) {
      const activeFile = this.app.workspace.getActiveFile();
      if (activeFile && !filteredFiles.includes(activeFile)) {
        filteredFiles.push(activeFile);
      }
    }

    return Array.from(new Set(filteredFiles)); // Remove duplicates
  }

  /**
   * Validate current context selection
   */
  async validateContextSelection(): Promise<ContextValidationResult> {
    const result: ContextValidationResult = {
      isValid: true,
      warnings: [],
      errors: [],
      stats: {
        totalFiles: 0,
        processedFiles: 0,
        unprocessedFiles: 0,
        estimatedTokens: 0
      }
    };

    try {
      const contextFiles = await this.resolveContextFiles();
      result.stats.totalFiles = contextFiles.length;

      let processedCount = 0;
      let estimatedTokens = 0;

      for (const file of contextFiles) {
        const metadata = this.fileCache.getMetadata(file.path);
        
        if (metadata?.processing_status === 'processed') {
          processedCount++;
        }

        // Rough token estimation (1 token ≈ 4 characters)
        try {
          const content = await this.app.vault.cachedRead(file);
          estimatedTokens += Math.ceil(content.length / 4);
        } catch (error) {
          result.warnings.push(`Cannot read file: ${file.path}`);
        }
      }

      result.stats.processedFiles = processedCount;
      result.stats.unprocessedFiles = contextFiles.length - processedCount;
      result.stats.estimatedTokens = estimatedTokens;

      // Add warnings and errors
      if (result.stats.unprocessedFiles > 0) {
        result.warnings.push(`${result.stats.unprocessedFiles} files are not processed yet`);
      }

      if (result.stats.estimatedTokens > 100000) {
        result.warnings.push(`Large context size (~${Math.ceil(result.stats.estimatedTokens / 1000)}k tokens)`);
      }

      if (result.stats.totalFiles === 0) {
        result.errors.push("No files selected for RAG context");
        result.isValid = false;
      }

    } catch (error) {
      result.errors.push(`Validation error: ${error.message || error}`);
      result.isValid = false;
    }

    return result;
  }

  // Public API
  public getContext(): RagContext {
    return { ...this.context };
  }

  public onContextChange(handler: (event: RagContextChangeEvent) => void): () => void {
    this.changeHandlers.add(handler);
    
    return () => {
      this.changeHandlers.delete(handler);
    };
  }

  public isEnabled(): boolean {
    return this.context.enabled;
  }

  public getProcessingManager(): VaultProcessingManager {
    return this.processingManager;
  }
}