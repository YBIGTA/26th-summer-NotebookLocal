/**
 * VaultFileWatcher - Real-time file change detection for Obsidian vault
 * Adapted from obsidian-original IndexEventHandler.ts
 * 
 * Key features:
 * - Debounced file change detection
 * - Support for multiple file types (md, pdf, txt, docx)
 * - Event-driven processing queue updates
 * - Proper cleanup and memory management
 */

import { App, TAbstractFile, TFile, Platform } from "obsidian";
import { getSettings } from "../settings/model-clean";

const DEBOUNCE_DELAY = 5000; // 5 seconds

export interface VaultFileWatcherConfig {
  supportedExtensions: string[];
  enableDebouncing: boolean;
  debounceDelay: number;
}

export interface FileChangeEvent {
  type: 'create' | 'modify' | 'delete' | 'rename';
  file: TFile;
  oldPath?: string;
  newPath?: string;
}

export class VaultFileWatcher {
  private debounceTimer: number | null = null;
  private lastActiveFile: TFile | null = null;
  private lastActiveFileMtime: number | null = null;
  private config: VaultFileWatcherConfig;
  
  // Event handlers
  private onFileChangeHandlers: Set<(event: FileChangeEvent) => void> = new Set();
  private onProcessingRequestHandlers: Set<(file: TFile) => void> = new Set();

  constructor(
    private app: App,
    config?: Partial<VaultFileWatcherConfig>
  ) {
    this.config = {
      supportedExtensions: ['md', 'pdf', 'txt', 'docx'],
      enableDebouncing: true,
      debounceDelay: DEBOUNCE_DELAY,
      ...config
    };
    
    this.initializeEventListeners();
  }

  private initializeEventListeners() {
    console.log("VaultFileWatcher: Initializing event listeners");
    
    // Listen for active file changes (for debounced processing)
    this.app.workspace.on("active-leaf-change", this.handleActiveLeafChange);
    
    // Listen for file system events
    this.app.vault.on("create", this.handleFileCreate);
    this.app.vault.on("modify", this.handleFileModify);
    this.app.vault.on("delete", this.handleFileDelete);
    this.app.vault.on("rename", this.handleFileRename);
  }

  private handleActiveLeafChange = (leaf: any) => {
    if (Platform.isMobile && getSettings().disableOnMobile) {
      return;
    }

    // Get the previously active file that we need to check
    const fileToCheck = this.lastActiveFile;
    const previousMtime = this.lastActiveFileMtime;

    // Update tracking for the new active file
    const currentView = leaf?.view;
    this.lastActiveFile = currentView?.file ?? null;
    this.lastActiveFileMtime = this.lastActiveFile?.stat?.mtime ?? null;

    // If there was no previous file or it's the same as current, do nothing
    if (!fileToCheck || fileToCheck === this.lastActiveFile) {
      return;
    }

    // Safety check for file stats and mtime
    if (!fileToCheck?.stat?.mtime || previousMtime === null) {
      return;
    }

    // Only process supported file types
    if (this.isSupportedFile(fileToCheck)) {
      // Check if file was modified while it was active
      const wasModified = previousMtime !== null && fileToCheck.stat.mtime > previousMtime;

      if (wasModified) {
        if (this.config.enableDebouncing) {
          this.debouncedProcessFile(fileToCheck);
        } else {
          this.requestProcessing(fileToCheck);
        }
      }
    }
  };

  private handleFileCreate = (file: TAbstractFile) => {
    if (file instanceof TFile && this.isSupportedFile(file)) {
      const event: FileChangeEvent = {
        type: 'create',
        file,
        newPath: file.path
      };
      this.notifyFileChange(event);
    }
  };

  private handleFileModify = (file: TAbstractFile) => {
    if (file instanceof TFile && this.isSupportedFile(file)) {
      const event: FileChangeEvent = {
        type: 'modify',
        file
      };
      this.notifyFileChange(event);
    }
  };

  private handleFileDelete = (file: TAbstractFile) => {
    if (file instanceof TFile && this.isSupportedFile(file)) {
      const event: FileChangeEvent = {
        type: 'delete',
        file
      };
      this.notifyFileChange(event);
    }
  };

  private handleFileRename = (file: TAbstractFile, oldPath: string) => {
    if (file instanceof TFile && this.isSupportedFile(file)) {
      const event: FileChangeEvent = {
        type: 'rename',
        file,
        oldPath,
        newPath: file.path
      };
      this.notifyFileChange(event);
    }
  };

  private debouncedProcessFile = (file: TFile) => {
    if (this.debounceTimer !== null) {
      window.clearTimeout(this.debounceTimer);
    }

    this.debounceTimer = window.setTimeout(() => {
      console.log("VaultFileWatcher: Triggering debounced processing for file", file.path);
      this.requestProcessing(file);
      this.debounceTimer = null;
    }, this.config.debounceDelay);
  };

  private requestProcessing(file: TFile) {
    this.onProcessingRequestHandlers.forEach(handler => {
      try {
        handler(file);
      } catch (error) {
        console.error("Error in processing request handler:", error);
      }
    });
  }

  private notifyFileChange(event: FileChangeEvent) {
    this.onFileChangeHandlers.forEach(handler => {
      try {
        handler(event);
      } catch (error) {
        console.error("Error in file change handler:", error);
      }
    });
  }

  private isSupportedFile(file: TFile): boolean {
    const extension = file.extension.toLowerCase();
    return this.config.supportedExtensions.includes(extension);
  }

  // Public API
  public onFileChange(handler: (event: FileChangeEvent) => void): () => void {
    this.onFileChangeHandlers.add(handler);
    
    // Return unsubscribe function
    return () => {
      this.onFileChangeHandlers.delete(handler);
    };
  }

  public onProcessingRequest(handler: (file: TFile) => void): () => void {
    this.onProcessingRequestHandlers.add(handler);
    
    // Return unsubscribe function
    return () => {
      this.onProcessingRequestHandlers.delete(handler);
    };
  }

  public getSupportedExtensions(): string[] {
    return [...this.config.supportedExtensions];
  }

  public updateConfig(newConfig: Partial<VaultFileWatcherConfig>) {
    this.config = { ...this.config, ...newConfig };
  }

  public cleanup() {
    if (this.debounceTimer !== null) {
      window.clearTimeout(this.debounceTimer);
    }
    
    // Clear event handlers
    this.onFileChangeHandlers.clear();
    this.onProcessingRequestHandlers.clear();
    
    // Remove Obsidian event listeners
    this.app.workspace.off("active-leaf-change", this.handleActiveLeafChange);
    this.app.vault.off("create", this.handleFileCreate);
    this.app.vault.off("modify", this.handleFileModify);
    this.app.vault.off("delete", this.handleFileDelete);
    this.app.vault.off("rename", this.handleFileRename);
  }

  public unload() {
    if (this.debounceTimer !== null) {
      window.clearTimeout(this.debounceTimer);
    }
    
    // Clean up file tracking
    this.lastActiveFile = null;
    this.lastActiveFileMtime = null;
    
    this.cleanup();
  }
}