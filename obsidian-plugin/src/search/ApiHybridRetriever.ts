import { apiClient } from "@/api/ApiClient";
import { getSettings } from "@/settings/model";

/**
 * API-based Hybrid Retriever that replaces local retrieval operations
 * Routes all search operations to the FastAPI RAG server
 */
export class ApiHybridRetriever {
  private settings = getSettings();

  /**
   * Retrieve relevant documents for a query
   * Replaces the HybridRetriever.getRelevantDocuments() method
   */
  async getRelevantDocuments(
    query: string,
    options: {
      limit?: number;
      threshold?: number;
      debug?: boolean;
    } = {}
  ) {
    const { limit = 5, threshold = 0.7, debug = false } = options;

    try {
      const results = await apiClient.search({
        query,
        limit,
        similarity_threshold: threshold,
      });

      if (debug) {
        console.log(`ApiHybridRetriever: Retrieved ${results.length} documents for query:`, query);
        console.log('Results:', results);
      }

      // Convert API results to the format expected by the plugin
      return results.map(result => ({
        pageContent: result.content,
        metadata: {
          source: result.source,
          score: result.score,
          ...result.metadata,
        },
      }));
    } catch (error) {
      console.error('ApiHybridRetriever: Search failed:', error);
      return []; // Return empty array on error to prevent crashes
    }
  }

  /**
   * Search with custom parameters
   */
  async search(
    query: string,
    k: number = 5,
    filter?: Record<string, any>
  ) {
    try {
      const results = await apiClient.search({
        query,
        limit: k,
        similarity_threshold: 0.7,
      });

      return results.map(result => ({
        content: result.content,
        source: result.source,
        score: result.score,
        metadata: result.metadata,
      }));
    } catch (error) {
      console.error('ApiHybridRetriever: Custom search failed:', error);
      return [];
    }
  }

  /**
   * Get similarity threshold for filtering results
   */
  getSimilarityThreshold(): number {
    return this.settings.maxSourceChunks || 0.7;
  }

  /**
   * Initialize the retriever
   */
  async initialize(): Promise<void> {
    try {
      const isConnected = await apiClient.testConnection();
      if (!isConnected) {
        throw new Error('Cannot connect to API server for retrieval operations');
      }
      
      console.log('API Hybrid Retriever initialized successfully');
    } catch (error) {
      console.error('Failed to initialize API Hybrid Retriever:', error);
      throw error;
    }
  }

  /**
   * Check if retriever is ready
   */
  async isReady(): Promise<boolean> {
    try {
      return await apiClient.testConnection();
    } catch (error) {
      return false;
    }
  }

  /**
   * Legacy compatibility method
   */
  async similaritySearchWithScore(
    query: string,
    k: number = 5,
    filter?: Record<string, any>
  ) {
    const results = await this.search(query, k, filter);
    return results.map(result => [
      {
        pageContent: result.content,
        metadata: {
          source: result.source,
          ...result.metadata,
        },
      },
      result.score,
    ]);
  }
}