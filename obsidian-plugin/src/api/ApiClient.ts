/**
 * API Client for communicating with the FastAPI RAG server
 * Replaces internal LLM provider and vector store operations
 */

export interface ChatRequest {
  message: string;
  chat_id?: string;
  context?: Record<string, any>;
  stream?: boolean;
}

export interface ChatResponse {
  message: string;
  chat_id: string;
  timestamp: string;
  sources?: string[];
}

export interface SearchRequest {
  query: string;
  limit?: number;
  similarity_threshold?: number;
}

export interface SearchResult {
  content: string;
  source: string;
  score: number;
  metadata: Record<string, any>;
}

export interface DocumentMetadata {
  id: string;
  filename: string;
  content_preview: string;
  chunks: number;
  images: number;
  processed_at: string;
  file_size: number;
}

export interface IndexStatus {
  total_documents: number;
  total_chunks: number;
  last_updated: string;
  is_empty: boolean;
}

export interface ProcessResponse {
  filename: string;
  chunks: number;
  images: number;
  status: string;
}

export class ApiClient {
  private baseUrl: string;
  private timeout: number;

  constructor(baseUrl: string = 'http://localhost:8000', timeout: number = 30000) {
    this.baseUrl = baseUrl.replace(/\/$/, ''); // Remove trailing slash
    this.timeout = timeout;
  }

  /**
   * Set the base URL for the API server
   */
  setBaseUrl(baseUrl: string): void {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  /**
   * Generic fetch wrapper with error handling and timeout
   */
  private async fetchWithTimeout(url: string, options: RequestInit = {}): Promise<Response> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(`API Error (${response.status}): ${errorData.detail || response.statusText}`);
      }

      return response;
    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError') {
        throw new Error('Request timeout - server may be unavailable');
      }
      throw error;
    }
  }

  /**
   * Test server connectivity
   */
  async testConnection(): Promise<boolean> {
    try {
      const response = await this.fetchWithTimeout(`${this.baseUrl}/api/v1/health`);
      const data = await response.json();
      return data.status === 'healthy';
    } catch (error) {
      console.error('Server connection test failed:', error);
      return false;
    }
  }

  /**
   * Chat with the RAG system - replaces VaultQAChainRunner
   */
  async chat(request: ChatRequest): Promise<ChatResponse> {
    const response = await this.fetchWithTimeout(`${this.baseUrl}/api/v1/obsidian/chat`, {
      method: 'POST',
      body: JSON.stringify(request),
    });

    return await response.json();
  }

  /**
   * Streaming chat for real-time responses
   */
  async chatStream(
    request: ChatRequest,
    onChunk: (chunk: string) => void,
    onComplete: () => void,
    onError: (error: Error) => void
  ): Promise<void> {
    try {
      const response = await fetch(`${this.baseUrl}/api/v1/obsidian/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...request, stream: true }),
      });

      if (!response.ok) {
        throw new Error(`Stream failed: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No response body available');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.trim() === '') continue;
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.error) {
                onError(new Error(data.error));
                return;
              }
              if (data.delta) {
                onChunk(data.delta);
              }
              if (data.done) {
                onComplete();
                return;
              }
            } catch (e) {
              console.warn('Failed to parse streaming data:', line);
            }
          }
        }
      }

      onComplete();
    } catch (error) {
      onError(error as Error);
    }
  }

  /**
   * Search documents - replaces HybridRetriever
   */
  async search(request: SearchRequest): Promise<SearchResult[]> {
    const response = await this.fetchWithTimeout(`${this.baseUrl}/api/v1/obsidian/search`, {
      method: 'POST',
      body: JSON.stringify(request),
    });

    return await response.json();
  }

  /**
   * Get list of processed documents
   */
  async getDocuments(): Promise<DocumentMetadata[]> {
    const response = await this.fetchWithTimeout(`${this.baseUrl}/api/v1/obsidian/documents`);
    return await response.json();
  }

  /**
   * Delete a document from the index
   */
  async deleteDocument(documentId: string): Promise<{ status: string; document_id: string }> {
    const response = await this.fetchWithTimeout(
      `${this.baseUrl}/api/v1/obsidian/documents/${documentId}`,
      { method: 'DELETE' }
    );
    return await response.json();
  }

  /**
   * Get index status - replaces VectorStoreManager.isIndexEmpty()
   */
  async getIndexStatus(): Promise<IndexStatus> {
    const response = await this.fetchWithTimeout(`${this.baseUrl}/api/v1/obsidian/index/status`);
    return await response.json();
  }

  /**
   * Rebuild the entire index
   */
  async rebuildIndex(): Promise<{ status: string; message: string }> {
    const response = await this.fetchWithTimeout(`${this.baseUrl}/api/v1/obsidian/index/rebuild`, {
      method: 'POST',
    });
    return await response.json();
  }

  /**
   * Process a document (file upload) - replaces internal indexing
   */
  async processDocument(file: File): Promise<ProcessResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${this.baseUrl}/api/v1/process`, {
      method: 'POST',
      body: formData,
      // Don't set Content-Type header, let browser set it with boundary for FormData
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(`Upload failed: ${errorData.detail}`);
    }

    return await response.json();
  }

  /**
   * Legacy compatibility - simple Q&A without chat context
   */
  async askQuestion(question: string): Promise<string> {
    const response = await this.fetchWithTimeout(`${this.baseUrl}/api/v1/ask`, {
      method: 'POST',
      body: JSON.stringify({ question }),
    });

    const data = await response.json();
    return data.answer;
  }
}

// Initialize API client with settings
import { getSettings } from "@/settings/model";

// Singleton instance for the plugin
export const apiClient = new ApiClient();

// Update API client when settings change
export function updateApiClientSettings(): void {
  const settings = getSettings();
  apiClient.setBaseUrl(settings.serverUrl || "http://localhost:8000");
}