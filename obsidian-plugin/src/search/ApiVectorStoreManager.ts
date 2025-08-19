import { apiClient } from "@/api/ApiClient";
import { getSettings } from "@/settings/model";
import { Notice } from "obsidian";

/**
 * API-based Vector Store Manager that replaces local vector operations
 * Routes all vector store operations to the FastAPI RAG server
 */
export class ApiVectorStoreManager {
  private settings = getSettings();

  /**
   * Check if the index is empty - replaces VectorStoreManager.isIndexEmpty()
   */
  async isIndexEmpty(): Promise<boolean> {
    try {
      const status = await apiClient.getIndexStatus();
      return status.is_empty;
    } catch (error) {
      console.error('Failed to check index status:', error);
      new Notice('Failed to check index status. Check server connection.');
      return true; // Assume empty on error
    }
  }

  /**
   * Get index statistics
   */
  async getIndexStatus() {
    try {
      return await apiClient.getIndexStatus();
    } catch (error) {
      console.error('Failed to get index status:', error);
      throw error;
    }
  }

  /**
   * Rebuild the entire index
   */
  async rebuildIndex(): Promise<void> {
    try {
      new Notice('Starting index rebuild...');
      const result = await apiClient.rebuildIndex();
      new Notice(result.message);
    } catch (error) {
      console.error('Failed to rebuild index:', error);
      new Notice('Failed to rebuild index. Check server connection.');
      throw error;
    }
  }

  /**
   * Process and add a document to the index
   */
  async addDocument(file: File): Promise<void> {
    try {
      new Notice(`Processing ${file.name}...`);
      const result = await apiClient.processDocument(file);
      new Notice(`✅ ${file.name} processed: ${result.chunks} chunks, ${result.images} images`);
    } catch (error) {
      console.error('Failed to process document:', error);
      new Notice(`❌ Failed to process ${file.name}: ${error.message}`);
      throw error;
    }
  }

  /**
   * Delete a document from the index
   */
  async deleteDocument(documentId: string): Promise<void> {
    try {
      await apiClient.deleteDocument(documentId);
      new Notice('Document deleted from index');
    } catch (error) {
      console.error('Failed to delete document:', error);
      new Notice('Failed to delete document');
      throw error;
    }
  }

  /**
   * Get all processed documents
   */
  async getDocuments() {
    try {
      return await apiClient.getDocuments();
    } catch (error) {
      console.error('Failed to get documents:', error);
      throw error;
    }
  }

  /**
   * Search for similar content - replaces HybridRetriever functionality
   */
  async search(query: string, limit: number = 10, threshold: number = 0.7) {
    try {
      return await apiClient.search({
        query,
        limit,
        similarity_threshold: threshold
      });
    } catch (error) {
      console.error('Failed to search documents:', error);
      throw error;
    }
  }

  /**
   * Initialize/connect to the vector store
   * In API mode, this just tests the connection
   */
  async initialize(): Promise<void> {
    try {
      const isConnected = await apiClient.testConnection();
      if (!isConnected) {
        throw new Error('Cannot connect to API server');
      }
      
      console.log('API Vector Store Manager initialized successfully');
    } catch (error) {
      console.error('Failed to initialize API Vector Store Manager:', error);
      throw error;
    }
  }

  /**
   * Check if the vector store is ready for operations
   */
  async isReady(): Promise<boolean> {
    try {
      return await apiClient.testConnection();
    } catch (error) {
      console.error('Vector store readiness check failed:', error);
      return false;
    }
  }

  /**
   * Get embedding for text (if needed for compatibility)
   * Note: In API mode, embeddings are handled server-side
   */
  async getEmbedding(text: string): Promise<number[]> {
    console.warn('getEmbedding called in API mode - embeddings are handled server-side');
    return []; // Return empty array as embeddings are handled server-side
  }

  /**
   * Batch process multiple documents
   */
  async processDocuments(files: File[]): Promise<void> {
    const promises = files.map(file => this.addDocument(file));
    await Promise.allSettled(promises);
  }

  /**
   * Legacy method compatibility - update vector store
   * In API mode, this is handled automatically by the server
   */
  async updateVectorStore(): Promise<void> {
    console.log('updateVectorStore called in API mode - handled automatically by server');
  }

  /**
   * Legacy method compatibility - clear vector store
   */
  async clearVectorStore(): Promise<void> {
    try {
      await this.rebuildIndex();
    } catch (error) {
      console.error('Failed to clear vector store:', error);
      throw error;
    }
  }
}