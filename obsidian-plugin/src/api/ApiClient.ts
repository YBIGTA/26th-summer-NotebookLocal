// Clean API Client - Only HTTP communication
import { ChatRequest, ChatResponse, UploadResponse, HealthResponse } from "../types";

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
}