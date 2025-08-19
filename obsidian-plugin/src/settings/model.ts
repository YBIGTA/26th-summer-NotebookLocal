// Clean settings model - only essential settings
import { CopilotSettings } from "../types";
import { DEFAULT_SETTINGS } from "../constants-minimal";

// Global settings state
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