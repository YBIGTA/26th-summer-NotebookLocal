/**
 * VaultFileCache - Content-based caching system for vault files
 * Adapted from obsidian-original FileCache.ts
 * 
 * Features:
 * - Multi-layer caching (memory + persistent storage)
 * - MD5-based content hashing for change detection
 * - Processing status tracking
 * - Efficient cache invalidation
 */

import { MD5 } from "crypto-js";
import { TFile } from "obsidian";

export interface VaultFileCacheEntry<T> {
  content: T;
  timestamp: number;
  contentHash: string;
  fileSize: number;
  mtime: number;
}

export interface VaultFileMetadata {
  path: string;
  size: number;
  mtime: number;
  contentHash: string;
  processingStatus: 'unprocessed' | 'queued' | 'processing' | 'processed' | 'error';
  errorMessage?: string;
}

export class VaultFileCache<T> {
  private static instance: VaultFileCache<any>;
  private cacheDir: string;
  private memoryCache: Map<string, VaultFileCacheEntry<T>> = new Map();
  private metadataCache: Map<string, VaultFileMetadata> = new Map();

  private constructor(cacheDir: string = ".notebook-local/vault-cache") {
    this.cacheDir = cacheDir;
  }

  static getInstance<T>(cacheDir?: string): VaultFileCache<T> {
    if (!VaultFileCache.instance) {
      VaultFileCache.instance = new VaultFileCache<T>(cacheDir);
    }
    return VaultFileCache.instance as VaultFileCache<T>;
  }

  private async ensureCacheDir() {
    if (!(await app.vault.adapter.exists(this.cacheDir))) {
      console.log("VaultFileCache: Creating cache directory:", this.cacheDir);
      await app.vault.adapter.mkdir(this.cacheDir);
    }
  }

  /**
   * Generate cache key for a file based on path, size, and modification time
   */
  getCacheKey(file: TFile, additionalContext?: string): string {
    const metadata = `${file.path}:${file.stat.size}:${file.stat.mtime}${additionalContext ? `:${additionalContext}` : ""}`;
    return MD5(metadata).toString();
  }

  /**
   * Generate content hash for file content
   */
  getContentHash(content: string): string {
    return MD5(content).toString();
  }

  private getCachePath(cacheKey: string): string {
    return `${this.cacheDir}/${cacheKey}.json`;
  }

  private getMetadataPath(): string {
    return `${this.cacheDir}/metadata.json`;
  }

  /**
   * Get cached content for a file
   */
  async get(cacheKey: string): Promise<T | null> {
    try {
      // Check memory cache first
      const memoryResult = this.memoryCache.get(cacheKey);
      if (memoryResult) {
        console.log("VaultFileCache: Memory cache hit for:", cacheKey);
        return memoryResult.content;
      }

      // Check persistent cache
      const cachePath = this.getCachePath(cacheKey);
      if (await app.vault.adapter.exists(cachePath)) {
        console.log("VaultFileCache: Disk cache hit for:", cacheKey);
        const cacheContent = await app.vault.adapter.read(cachePath);
        
        try {
          const parsedEntry: VaultFileCacheEntry<T> = JSON.parse(cacheContent);
          
          // Store in memory cache
          this.memoryCache.set(cacheKey, parsedEntry);
          
          return parsedEntry.content;
        } catch (parseError) {
          console.warn("VaultFileCache: Failed to parse cached content:", parseError);
          // Clean up corrupted cache file
          await app.vault.adapter.remove(cachePath);
        }
      }

      console.log("VaultFileCache: Cache miss for:", cacheKey);
      return null;
    } catch (error) {
      console.error("VaultFileCache: Error reading from cache:", error);
      return null;
    }
  }

  /**
   * Cache content for a file
   */
  async set(cacheKey: string, content: T, file: TFile): Promise<void> {
    try {
      await this.ensureCacheDir();
      
      const contentStr = typeof content === 'string' ? content : JSON.stringify(content);
      const contentHash = this.getContentHash(contentStr);
      
      const timestamp = Date.now();
      const cacheEntry: VaultFileCacheEntry<T> = {
        content,
        timestamp,
        contentHash,
        fileSize: file.stat.size,
        mtime: file.stat.mtime
      };

      // Store in memory cache
      this.memoryCache.set(cacheKey, cacheEntry);

      // Store in persistent cache
      const cachePath = this.getCachePath(cacheKey);
      const serializedContent = JSON.stringify(cacheEntry, null, 2);
      await app.vault.adapter.write(cachePath, serializedContent);

      console.log("VaultFileCache: Cached content for:", cacheKey);
    } catch (error) {
      console.error("VaultFileCache: Error writing to cache:", error);
    }
  }

  /**
   * Remove cached content
   */
  async remove(cacheKey: string): Promise<void> {
    try {
      // Remove from memory cache
      this.memoryCache.delete(cacheKey);

      // Remove from persistent cache
      const cachePath = this.getCachePath(cacheKey);
      if (await app.vault.adapter.exists(cachePath)) {
        await app.vault.adapter.remove(cachePath);
        console.log("VaultFileCache: Removed cached content for:", cacheKey);
      }
    } catch (error) {
      console.error("VaultFileCache: Error removing from cache:", error);
    }
  }

  /**
   * Clear all cached content
   */
  async clear(): Promise<void> {
    try {
      // Clear memory cache
      this.memoryCache.clear();
      this.metadataCache.clear();

      // Clear persistent cache
      if (await app.vault.adapter.exists(this.cacheDir)) {
        const files = await app.vault.adapter.list(this.cacheDir);
        console.log("VaultFileCache: Clearing cache, removing files:", files.files.length);

        for (const file of files.files) {
          await app.vault.adapter.remove(file);
        }
      }
    } catch (error) {
      console.error("VaultFileCache: Error clearing cache:", error);
    }
  }

  /**
   * Check if content has changed based on hash
   */
  async hasContentChanged(file: TFile, content: string): Promise<boolean> {
    const cacheKey = this.getCacheKey(file);
    const cachedEntry = await this.get(cacheKey);
    
    if (!cachedEntry) {
      return true; // No cached content, assume changed
    }
    
    const currentHash = this.getContentHash(content);
    const cachedHash = this.memoryCache.get(cacheKey)?.contentHash;
    
    return currentHash !== cachedHash;
  }

  /**
   * Update file metadata (processing status, etc.)
   */
  async updateMetadata(file: TFile, metadata: Partial<VaultFileMetadata>): Promise<void> {
    const currentMetadata = this.metadataCache.get(file.path) || {
      path: file.path,
      size: file.stat.size,
      mtime: file.stat.mtime,
      contentHash: '',
      processingStatus: 'unprocessed' as const
    };

    const updatedMetadata: VaultFileMetadata = {
      ...currentMetadata,
      ...metadata
    };

    this.metadataCache.set(file.path, updatedMetadata);
    
    try {
      await this.ensureCacheDir();
      const metadataPath = this.getMetadataPath();
      const allMetadata = Object.fromEntries(this.metadataCache);
      await app.vault.adapter.write(metadataPath, JSON.stringify(allMetadata, null, 2));
    } catch (error) {
      console.error("VaultFileCache: Error updating metadata:", error);
    }
  }

  /**
   * Get file metadata
   */
  getMetadata(filePath: string): VaultFileMetadata | null {
    return this.metadataCache.get(filePath) || null;
  }

  /**
   * Get all files with specific processing status
   */
  getFilesByStatus(status: VaultFileMetadata['processingStatus']): VaultFileMetadata[] {
    return Array.from(this.metadataCache.values()).filter(
      metadata => metadata.processingStatus === status
    );
  }

  /**
   * Load metadata from disk
   */
  async loadMetadata(): Promise<void> {
    try {
      const metadataPath = this.getMetadataPath();
      if (await app.vault.adapter.exists(metadataPath)) {
        const content = await app.vault.adapter.read(metadataPath);
        const metadata = JSON.parse(content);
        
        this.metadataCache.clear();
        Object.entries(metadata).forEach(([path, data]) => {
          this.metadataCache.set(path, data as VaultFileMetadata);
        });
        
        console.log("VaultFileCache: Loaded metadata for", this.metadataCache.size, "files");
      }
    } catch (error) {
      console.error("VaultFileCache: Error loading metadata:", error);
    }
  }

  /**
   * Get cache statistics
   */
  getStats(): {
    memoryCacheSize: number;
    metadataCacheSize: number;
    processingStats: Record<VaultFileMetadata['processingStatus'], number>;
  } {
    const processingStats = {
      unprocessed: 0,
      queued: 0,
      processing: 0,
      processed: 0,
      error: 0
    };

    this.metadataCache.forEach(metadata => {
      processingStats[metadata.processingStatus]++;
    });

    return {
      memoryCacheSize: this.memoryCache.size,
      metadataCacheSize: this.metadataCache.size,
      processingStats
    };
  }
}