import { type TFile } from "obsidian";

declare module "obsidian" {
  interface MetadataCache {
    // Note that this API is considered internal and may work differently in the
    // future.
    getBacklinksForFile(file: TFile): {
      data: Map<string, any>;
    } | null;
  }
}

// Minimal types for clean plugin
export interface CopilotSettings {
  serverUrl: string;
  timeout: number;
  enableStreaming: boolean;
  debug: boolean;
}

export interface ChatMessage {
  id: string;
  content: string;
  sender: 'user' | 'assistant';
  timestamp: Date;
  sources?: string[];
}

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
}
