/**
 * VaultProcessingManager - Batch processing pipeline for vault files
 * Adapted from obsidian-original IndexOperations.ts
 * 
 * Features:
 * - Batch processing with progress tracking
 * - Pause/resume functionality
 * - Queue management
 * - Error handling and recovery
 * - Integration with backend API
 */

import { App, Notice, TFile, Platform } from "obsidian";
import { ApiClient } from "../api/ApiClient-clean";
import { VaultFileCache, VaultFileMetadata } from "./VaultFileCache";
import { getSettings } from "../settings/model-clean";

export interface ProcessingState {
  isProcessingPaused: boolean;
  isProcessingCancelled: boolean;
  processedCount: number;
  totalFilesToProcess: number;
  processedFiles: Set<string>;
  currentProcessingNotice: Notice | null;
  processNoticeMessage: HTMLSpanElement | null;
  errors: Map<string, string>; // filePath -> error message
}

export interface ProcessingOptions {
  batchSize: number;
  enableProgressNotice: boolean;
  supportedExtensions: string[];
  overwrite?: boolean;
}

export class VaultProcessingManager {
  private apiClient: ApiClient;
  private fileCache: VaultFileCache<string>;
  private state: ProcessingState;
  private options: ProcessingOptions;

  constructor(
    private app: App,
    apiClient: ApiClient,
    options?: Partial<ProcessingOptions>
  ) {
    this.apiClient = apiClient;
    this.fileCache = VaultFileCache.getInstance<string>();
    
    this.options = {
      batchSize: 10,
      enableProgressNotice: true,
      supportedExtensions: ['md', 'pdf', 'txt', 'docx'],
      ...options
    };

    this.state = this.initializeProcessingState();
  }

  private initializeProcessingState(): ProcessingState {
    return {
      isProcessingPaused: false,
      isProcessingCancelled: false,
      processedCount: 0,
      totalFilesToProcess: 0,
      processedFiles: new Set(),
      currentProcessingNotice: null,
      processNoticeMessage: null,
      errors: new Map()
    };
  }

  /**
   * Process files in the vault
   */
  async processVaultFiles(
    files?: TFile[], 
    overwrite: boolean = false
  ): Promise<{ processed: number; errors: number }> {
    const errors: string[] = [];

    try {
      // Get files to process
      const filesToProcess = files || await this.getFilesToProcess(overwrite);
      
      if (filesToProcess.length === 0) {
        new Notice("No files found to process.");
        return { processed: 0, errors: 0 };
      }

      // Initialize processing state
      this.state = this.initializeProcessingState();
      this.state.totalFilesToProcess = filesToProcess.length;

      if (this.options.enableProgressNotice) {
        this.createProcessingNotice();
      }

      // Load metadata from cache
      await this.fileCache.loadMetadata();

      // Process files in batches
      for (let i = 0; i < filesToProcess.length; i += this.options.batchSize) {
        if (this.state.isProcessingCancelled) break;
        
        await this.handlePause();

        const batch = filesToProcess.slice(i, i + this.options.batchSize);
        
        try {
          await this.processBatch(batch, overwrite);
        } catch (error) {
          this.handleBatchError(error, batch, errors);
        }
      }

      // Finalize processing
      this.finalizeProcessing(errors);

      return {
        processed: this.state.processedCount,
        errors: this.state.errors.size
      };

    } catch (error) {
      this.handleError(error);
      return { processed: 0, errors: 1 };
    }
  }

  /**
   * Process a single file
   */
  async processSingleFile(file: TFile, forceReprocess: boolean = false): Promise<boolean> {
    try {
      // Check if file needs processing
      const metadata = this.fileCache.getMetadata(file.path);
      const fileContent = await this.app.vault.cachedRead(file);
      
      const hasChanged = await this.fileCache.hasContentChanged(file, fileContent);
      
      if (!forceReprocess && metadata?.processingStatus === 'processed' && !hasChanged) {
        console.log("VaultProcessingManager: File already processed and unchanged:", file.path);
        return true;
      }

      // Update status to processing
      await this.fileCache.updateMetadata(file, { processingStatus: 'processing' });

      // Send to backend for processing
      const formData = new FormData();
      const blob = new Blob([fileContent], { type: 'text/plain' });
      const fileName = `${file.basename}.${file.extension}`;
      formData.append('file', blob, fileName);

      const response = await this.apiClient.uploadDocument(
        new File([blob], fileName, { type: 'text/plain' })
      );

      if (response.success) {
        // Update cache and metadata
        await this.fileCache.set(this.fileCache.getCacheKey(file), fileContent, file);
        await this.fileCache.updateMetadata(file, { 
          processingStatus: 'processed',
          contentHash: this.fileCache.getContentHash(fileContent)
        });
        
        console.log("VaultProcessingManager: Successfully processed:", file.path);
        return true;
      } else {
        throw new Error(response.message || 'Processing failed');
      }

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      console.error("VaultProcessingManager: Error processing file:", file.path, error);
      
      // Update metadata with error
      await this.fileCache.updateMetadata(file, { 
        processingStatus: 'error',
        errorMessage 
      });
      
      this.state.errors.set(file.path, errorMessage);
      return false;
    }
  }

  private async processBatch(files: TFile[], overwrite: boolean): Promise<void> {
    const promises = files.map(file => this.processSingleFile(file, overwrite));
    const results = await Promise.allSettled(promises);

    results.forEach((result, index) => {
      const file = files[index];
      
      if (result.status === 'fulfilled' && result.value) {
        this.state.processedFiles.add(file.path);
      } else {
        const error = result.status === 'rejected' ? result.reason : 'Processing failed';
        this.state.errors.set(file.path, error.message || error.toString());
      }
    });

    // Update progress
    this.state.processedCount = this.state.processedFiles.size;
    this.updateProcessingNoticeMessage();
  }

  private async getFilesToProcess(overwrite: boolean): Promise<TFile[]> {
    const allFiles = this.app.vault.getFiles();
    const supportedFiles = allFiles.filter(file => 
      this.options.supportedExtensions.includes(file.extension.toLowerCase())
    );

    if (overwrite) {
      return supportedFiles;
    }

    // Filter out already processed files
    const filesToProcess: TFile[] = [];
    
    for (const file of supportedFiles) {
      const metadata = this.fileCache.getMetadata(file.path);
      const fileContent = await this.app.vault.cachedRead(file);
      const hasChanged = await this.fileCache.hasContentChanged(file, fileContent);
      
      if (!metadata || 
          metadata.processingStatus !== 'processed' || 
          hasChanged) {
        filesToProcess.push(file);
      }
    }

    return filesToProcess;
  }

  private createProcessingNotice(): Notice {
    const frag = document.createDocumentFragment();
    const container = frag.createEl("div", { cls: "vault-processing-notice-container" });

    this.state.processNoticeMessage = container.createEl("div", { 
      cls: "vault-processing-notice-message" 
    });
    this.updateProcessingNoticeMessage();

    // Create button container
    const buttonContainer = container.createEl("div", { 
      cls: "vault-processing-notice-buttons" 
    });

    // Pause/Resume button
    const pauseButton = buttonContainer.createEl("button");
    pauseButton.textContent = "Pause";
    pauseButton.addEventListener("click", (event) => {
      event.stopPropagation();
      event.preventDefault();
      if (this.state.isProcessingPaused) {
        this.resumeProcessing();
        pauseButton.textContent = "Pause";
      } else {
        this.pauseProcessing();
        pauseButton.textContent = "Resume";
      }
    });

    // Stop button
    const stopButton = buttonContainer.createEl("button");
    stopButton.textContent = "Stop";
    stopButton.style.marginLeft = "8px";
    stopButton.addEventListener("click", (event) => {
      event.stopPropagation();
      event.preventDefault();
      this.cancelProcessing();
    });

    frag.appendChild(container);

    this.state.currentProcessingNotice = new Notice(frag, 0);
    return this.state.currentProcessingNotice;
  }

  private updateProcessingNoticeMessage(): void {
    if (this.state.processNoticeMessage) {
      const status = this.state.isProcessingPaused ? " (Paused)" : "";
      const errorCount = this.state.errors.size > 0 ? ` (${this.state.errors.size} errors)` : "";
      
      this.state.processNoticeMessage.textContent = 
        `Processing vault files: ${this.state.processedCount}/${this.state.totalFilesToProcess}${status}${errorCount}`;
    }
  }

  private async handlePause(): Promise<void> {
    while (this.state.isProcessingPaused && !this.state.isProcessingCancelled) {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }

  public pauseProcessing(): void {
    this.state.isProcessingPaused = true;
    console.log("VaultProcessingManager: Processing paused");
  }

  public resumeProcessing(): void {
    this.state.isProcessingPaused = false;
    console.log("VaultProcessingManager: Processing resumed");
  }

  public async cancelProcessing(): Promise<void> {
    console.log("VaultProcessingManager: Processing cancelled by user");
    this.state.isProcessingCancelled = true;

    await new Promise((resolve) => setTimeout(resolve, 100));

    if (this.state.currentProcessingNotice) {
      this.state.currentProcessingNotice.hide();
    }
  }

  private handleBatchError(error: any, batch: TFile[], errors: string[]): void {
    console.error("VaultProcessingManager: Batch processing error:", error);
    
    batch.forEach(file => {
      const errorMessage = error.message || 'Batch processing failed';
      this.state.errors.set(file.path, errorMessage);
      errors.push(file.path);
    });
  }

  private handleError(error: any): void {
    console.error("VaultProcessingManager: Fatal processing error:", error);
    
    if (this.state.currentProcessingNotice) {
      this.state.currentProcessingNotice.hide();
    }

    const message = error.message || 'Unknown processing error';
    new Notice(`Processing error: ${message}`);
  }

  private finalizeProcessing(errors: string[]): void {
    if (this.state.currentProcessingNotice) {
      this.state.currentProcessingNotice.hide();
    }

    if (this.state.isProcessingCancelled) {
      new Notice("File processing cancelled");
      return;
    }

    const successCount = this.state.processedCount;
    const errorCount = this.state.errors.size;

    if (errorCount > 0) {
      new Notice(`Processing completed: ${successCount} files processed, ${errorCount} errors`);
    } else {
      new Notice(`Processing completed successfully: ${successCount} files processed`);
    }
  }

  /**
   * Get processing statistics
   */
  getProcessingStats(): {
    totalFiles: number;
    processedFiles: number;
    queuedFiles: number;
    errorFiles: number;
    unprocessedFiles: number;
  } {
    const stats = this.fileCache.getStats();
    
    return {
      totalFiles: stats.metadataCacheSize,
      processedFiles: stats.processingStats.processed,
      queuedFiles: stats.processingStats.queued,
      errorFiles: stats.processingStats.error,
      unprocessedFiles: stats.processingStats.unprocessed
    };
  }

  /**
   * Queue files for processing
   */
  async queueFiles(files: TFile[]): Promise<void> {
    for (const file of files) {
      await this.fileCache.updateMetadata(file, { processingStatus: 'queued' });
    }
    
    console.log("VaultProcessingManager: Queued", files.length, "files for processing");
  }

  /**
   * Remove files from queue
   */
  async unqueueFiles(files: TFile[]): Promise<void> {
    for (const file of files) {
      const metadata = this.fileCache.getMetadata(file.path);
      if (metadata?.processingStatus === 'queued') {
        await this.fileCache.updateMetadata(file, { processingStatus: 'unprocessed' });
      }
    }
    
    console.log("VaultProcessingManager: Unqueued", files.length, "files");
  }

  /**
   * Get files by processing status
   */
  getFilesByStatus(status: VaultFileMetadata['processingStatus']): VaultFileMetadata[] {
    return this.fileCache.getFilesByStatus(status);
  }

  /**
   * Check if a file is supported for processing
   */
  isSupportedFile(file: TFile): boolean {
    return this.options.supportedExtensions.includes(file.extension.toLowerCase());
  }
}