/**
 * Clean API Client - Only HTTP communication with inference server
 */

export interface ChatRequest {
  message: string;
  chat_id?: string;
  stream?: boolean;
}

export interface ChatResponse {
  message: string;
  chat_id: string;
  sources?: string[];
}

export interface UploadResponse {
  success: boolean;
  filename: string;
  document_id: string;
  message: string;
}

export interface HealthResponse {
  status: string;
  timestamp: string;
  version?: string;
}

export interface SearchRequest {
  query: string;
  limit?: number;
}

export interface SearchResult {
  content: string;
  source: string;
  score: number;
}

export interface DocumentInfo {
  id: string;
  filename: string;
  uploaded_at: string;
  chunks: number;
}

// Vault management interfaces
export interface VaultFileResponse {
  file_id: string;
  vault_path: string;
  file_type?: string;
  content_hash?: string;
  file_size?: number;
  modified_at?: string;
  processing_status: string;
  doc_uid?: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface VaultScanRequest {
  vault_path: string;
  force_rescan?: boolean;
}

export interface VaultProcessRequest {
  file_paths: string[];
  force_reprocess?: boolean;
}

export interface VaultStatusResponse {
  total_files: number;
  processed: number;
  queued: number;
  processing: number;
  unprocessed: number;
  error: number;
  last_scan?: string;
}

// RAG context interfaces
export interface RagContextRequest {
  enabled: boolean;
  scope: 'whole' | 'selected' | 'folder';
  selected_files: string[];
  selected_folders: string[];
  selected_tags: string[];
  temporal_filters: Record<string, any>;
}

export interface RagContextResponse extends RagContextRequest {
  last_updated: string;
  file_count: number;
  processed_file_count: number;
}

export interface ContextValidationResponse {
  is_valid: boolean;
  warnings: string[];
  errors: string[];
  stats: Record<string, number>;
}

export interface CommandParseResponse {
  command_type: string;
  parsed_command: string;
  arguments: string[];
  is_valid: boolean;
  result?: string;
  error?: string;
}

export interface AutocompleteResponse {
  suggestions: Array<{
    type: string;
    label: string;
    description: string;
    icon?: string;
    processing_status?: string;
  }>;
}

export class ApiClient {
  private baseUrl: string;
  private timeout: number;

  constructor(settings: any) {
    this.baseUrl = settings.serverUrl || 'http://localhost:8000';
    this.timeout = settings.timeout || 30000;
  }

  updateSettings(settings: any) {
    this.baseUrl = settings.serverUrl || 'http://localhost:8000';
    this.timeout = settings.timeout || 30000;
  }

  // Health check
  async healthCheck(): Promise<HealthResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(this.timeout),
    });

    if (!response.ok) {
      throw new Error(`Health check failed: ${response.status}`);
    }

    return await response.json();
  }

  // Upload document
  async uploadDocument(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${this.baseUrl}/api/v1/process`, {
      method: 'POST',
      body: formData,
      signal: AbortSignal.timeout(this.timeout),
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.status}`);
    }

    return await response.json();
  }

  // Chat with documents
  async chat(request: ChatRequest): Promise<ChatResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/obsidian/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
      signal: AbortSignal.timeout(this.timeout),
    });

    if (!response.ok) {
      throw new Error(`Chat failed: ${response.status}`);
    }

    return await response.json();
  }

  // Streaming chat
  async *chatStream(request: ChatRequest): AsyncGenerator<string, void, unknown> {
    const response = await fetch(`${this.baseUrl}/api/v1/obsidian/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ ...request, stream: true }),
      signal: AbortSignal.timeout(this.timeout),
    });

    if (!response.ok) {
      throw new Error(`Streaming chat failed: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') return;
            
            try {
              const parsed = JSON.parse(data);
              // console.log('Streaming data received:', parsed); // DEBUG
              if (parsed.content) {
                yield parsed.content;
              }
              if (parsed.error) {
                // console.error('Streaming error:', parsed.error); // DEBUG
                throw new Error(parsed.error);
              }
            } catch (e) {
              // console.warn('Invalid streaming JSON:', data, e); // DEBUG
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  // Search documents
  async search(request: SearchRequest): Promise<SearchResult[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/obsidian/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
      signal: AbortSignal.timeout(this.timeout),
    });

    if (!response.ok) {
      throw new Error(`Search failed: ${response.status}`);
    }

    return await response.json();
  }

  // List documents
  async getDocuments(): Promise<DocumentInfo[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/obsidian/documents`, {
      method: 'GET',
      signal: AbortSignal.timeout(this.timeout),
    });

    if (!response.ok) {
      throw new Error(`Failed to get documents: ${response.status}`);
    }

    return await response.json();
  }

  // Delete document
  async deleteDocument(documentId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/v1/obsidian/documents/${documentId}`, {
      method: 'DELETE',
      signal: AbortSignal.timeout(this.timeout),
    });

    if (!response.ok) {
      throw new Error(`Failed to delete document: ${response.status}`);
    }
  }

  // ========================================
  // Vault Management API Methods
  // ========================================

  // List vault files
  async getVaultFiles(
    status?: string,
    fileType?: string,
    limit: number = 100,
    offset: number = 0
  ): Promise<VaultFileResponse[]> {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (fileType) params.append('file_type', fileType);
    params.append('limit', limit.toString());
    params.append('offset', offset.toString());

    const response = await fetch(`${this.baseUrl}/api/v1/vault/files?${params}`, {
      method: 'GET',
      signal: AbortSignal.timeout(this.timeout),
    });

    if (!response.ok) {
      throw new Error(`Failed to get vault files: ${response.status}`);
    }

    return await response.json();
  }

  // Scan vault for changes
  async scanVault(request: VaultScanRequest): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/v1/vault/scan`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
      signal: AbortSignal.timeout(this.timeout),
    });

    if (!response.ok) {
      throw new Error(`Vault scan failed: ${response.status}`);
    }

    return await response.json();
  }

  // Process vault files
  async processVaultFiles(request: VaultProcessRequest): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/v1/vault/process`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
      signal: AbortSignal.timeout(this.timeout),
    });

    if (!response.ok) {
      throw new Error(`Vault processing failed: ${response.status}`);
    }

    return await response.json();
  }

  // Remove file from processing queue
  async removeFromQueue(fileId: string): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/v1/vault/files/${fileId}`, {
      method: 'DELETE',
      signal: AbortSignal.timeout(this.timeout),
    });

    if (!response.ok) {
      throw new Error(`Failed to remove from queue: ${response.status}`);
    }

    return await response.json();
  }

  // Get vault status
  async getVaultStatus(): Promise<VaultStatusResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/vault/status`, {
      method: 'GET',
      signal: AbortSignal.timeout(this.timeout),
    });

    if (!response.ok) {
      throw new Error(`Failed to get vault status: ${response.status}`);
    }

    return await response.json();
  }

  // ========================================
  // RAG Context Management API Methods
  // ========================================

  // Set RAG context
  async setRagContext(context: RagContextRequest): Promise<{ message: string; context: RagContextResponse }> {
    const response = await fetch(`${this.baseUrl}/api/v1/rag/context/set`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(context),
      signal: AbortSignal.timeout(this.timeout),
    });

    if (!response.ok) {
      throw new Error(`Failed to set RAG context: ${response.status}`);
    }

    return await response.json();
  }

  // Get current RAG context
  async getRagContext(): Promise<RagContextResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/rag/context`, {
      method: 'GET',
      signal: AbortSignal.timeout(this.timeout),
    });

    if (!response.ok) {
      throw new Error(`Failed to get RAG context: ${response.status}`);
    }

    return await response.json();
  }

  // Validate RAG context
  async validateRagContext(context: RagContextRequest): Promise<ContextValidationResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/rag/context/validate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ context }),
      signal: AbortSignal.timeout(this.timeout),
    });

    if (!response.ok) {
      throw new Error(`Failed to validate RAG context: ${response.status}`);
    }

    return await response.json();
  }

  // Parse command
  async parseCommand(command: string, context?: RagContextRequest): Promise<CommandParseResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/rag/context/parse-command`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ command, context }),
      signal: AbortSignal.timeout(this.timeout),
    });

    if (!response.ok) {
      throw new Error(`Failed to parse command: ${response.status}`);
    }

    return await response.json();
  }

  // Get autocomplete suggestions
  async getAutocompleteSuggestions(
    query: string,
    contextType: 'file' | 'folder' | 'tag' | 'command' | 'special',
    limit: number = 10
  ): Promise<AutocompleteResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/rag/context/autocomplete`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query,
        context_type: contextType,
        limit,
      }),
      signal: AbortSignal.timeout(this.timeout),
    });

    if (!response.ok) {
      throw new Error(`Failed to get autocomplete suggestions: ${response.status}`);
    }

    return await response.json();
  }

  // Context-aware search
  async contextAwareSearch(
    query: string,
    context: RagContextRequest,
    limit: number = 5,
    similarityThreshold: number = 0.7
  ): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/v1/rag/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query,
        context,
        limit,
        similarity_threshold: similarityThreshold,
      }),
      signal: AbortSignal.timeout(this.timeout),
    });

    if (!response.ok) {
      throw new Error(`Context-aware search failed: ${response.status}`);
    }

    return await response.json();
  }
}