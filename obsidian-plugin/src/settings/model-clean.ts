// Clean settings model - only UI and API configuration
import { atom } from "jotai";

export interface CopilotSettings {
  // Server connection
  serverUrl: string;
  timeout: number;
  
  // UI preferences
  chatOpen: boolean;
  defaultChatWidth: number;
  
  // Features
  enableAutoComplete: boolean;
  enableStreaming: boolean;
  
  // Debug
  debug: boolean;
}

export const DEFAULT_SETTINGS: CopilotSettings = {
  serverUrl: "http://localhost:8000",
  timeout: 30000,
  chatOpen: false,
  defaultChatWidth: 400,
  enableAutoComplete: true,
  enableStreaming: true,
  debug: false,
};

// Global settings atom
export const settingsAtom = atom<CopilotSettings>(DEFAULT_SETTINGS);

// Settings management
let currentSettings: CopilotSettings = { ...DEFAULT_SETTINGS };

export function getSettings(): CopilotSettings {
  return { ...currentSettings };
}

export function setSettings(settings: Partial<CopilotSettings>): void {
  currentSettings = { ...currentSettings, ...settings };
}

export function updateSetting<K extends keyof CopilotSettings>(
  key: K,
  value: CopilotSettings[K]
): void {
  currentSettings[key] = value;
}

export function resetSettings(): void {
  currentSettings = { ...DEFAULT_SETTINGS };
}

// Simple subscription system
type SettingsListener = (settings: CopilotSettings) => void;
const listeners: SettingsListener[] = [];

export function subscribeToSettingsChange(listener: SettingsListener): () => void {
  listeners.push(listener);
  
  // Return unsubscribe function
  return () => {
    const index = listeners.indexOf(listener);
    if (index > -1) {
      listeners.splice(index, 1);
    }
  };
}

function notifyListeners(): void {
  listeners.forEach(listener => listener(currentSettings));
}

// Override setSettings to notify listeners
const originalSetSettings = setSettings;
export { originalSetSettings as setSettingsWithoutNotification };

export function setSettingsWithNotification(settings: Partial<CopilotSettings>): void {
  originalSetSettings(settings);
  notifyListeners();
}