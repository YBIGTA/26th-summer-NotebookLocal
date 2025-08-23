// Streaming Settings Component
import React from "react";
import { getSettings, setSettings } from "./model-clean";

interface StreamingSettingsProps {
  onSettingsChange?: () => void;
}

export function StreamingSettings({ onSettingsChange }: StreamingSettingsProps) {
  const settings = getSettings();

  const handleStreamingToggle = (enabled: boolean) => {
    setSettings({ enableStreaming: enabled });
    if (onSettingsChange) {
      onSettingsChange();
    }
  };

  return (
    <div style={{ padding: '16px' }}>
      <h3 style={{ 
        margin: '0 0 16px 0', 
        fontSize: '18px', 
        fontWeight: '600',
        color: 'var(--text-normal)'
      }}>
        Streaming Settings
      </h3>
      
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '12px',
        padding: '12px',
        backgroundColor: 'var(--background-secondary)',
        border: '1px solid var(--background-modifier-border)',
        borderRadius: '8px'
      }}>
        <label style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          cursor: 'pointer',
          fontSize: '14px',
          color: 'var(--text-normal)'
        }}>
          <input
            type="checkbox"
            checked={settings.enableStreaming}
            onChange={(e) => handleStreamingToggle(e.target.checked)}
            style={{
              width: '16px',
              height: '16px',
              cursor: 'pointer'
            }}
          />
          Enable streaming responses
        </label>
      </div>

      <div style={{
        marginTop: '12px',
        fontSize: '12px',
        color: 'var(--text-muted)',
        lineHeight: '1.4'
      }}>
        When enabled, AI responses will appear progressively as they are generated. 
        When disabled, you'll see the complete response after processing finishes.
      </div>
    </div>
  );
}