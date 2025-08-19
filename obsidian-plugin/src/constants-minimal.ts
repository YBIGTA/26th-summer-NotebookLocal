// Minimal constants for clean plugin
export const CHAT_VIEWTYPE = "copilot-chat-view";
export const PLUGIN_NAME = "Copilot";

// Default settings
export const DEFAULT_SETTINGS = {
  serverUrl: "http://localhost:8000",
  timeout: 30000,
  enableStreaming: true,
  debug: false,
} as const;

// API endpoints
export const API_ENDPOINTS = {
  HEALTH: "/api/v1/health",
  UPLOAD: "/api/v1/process",
  CHAT: "/api/v1/obsidian/chat",
  CHAT_STREAM: "/api/v1/obsidian/chat/stream",
  SEARCH: "/api/v1/obsidian/search",
  DOCUMENTS: "/api/v1/obsidian/documents",
} as const;