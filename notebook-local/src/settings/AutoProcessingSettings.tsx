// Auto-Processing Settings Component
import React, { useState } from "react";
import { getSettings, setSettings } from "./model-clean";

interface AutoProcessingSettingsProps {
  onSettingsChange?: () => void;
}

export function AutoProcessingSettings({ onSettingsChange }: AutoProcessingSettingsProps) {
  const settings = getSettings();
  const [ignoreConfig, setIgnoreConfig] = useState(settings.autoProcessingIgnoreConfig);
  const [frequencyLimit, setFrequencyLimit] = useState(settings.frequencyLimit);

  const handleIgnoreConfigChange = (value: string) => {
    setIgnoreConfig(value);
    setSettings({ autoProcessingIgnoreConfig: value });
    if (onSettingsChange) {
      onSettingsChange();
    }
  };

  const handleFrequencyLimitChange = (value: number) => {
    setFrequencyLimit(value);
    setSettings({ frequencyLimit: value });
    if (onSettingsChange) {
      onSettingsChange();
    }
  };

  const resetToDefault = () => {
    const defaultConfig = `# Auto-processing ignore patterns (like .gitignore)
# Files/folders matching these patterns will NOT be processed
# Lines starting with # are comments
# Use / for folders, no / for files  
# Supports glob patterns like *.tmp, **/*.log

# Common ignores
.obsidian/
temp/
drafts/
*.tmp
*.log
node_modules/

# Personal files
personal/
private/

# Use ! for exceptions (process even if parent is ignored)
# !important-personal.md`;
    
    setIgnoreConfig(defaultConfig);
    setSettings({ autoProcessingIgnoreConfig: defaultConfig });
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
        Auto-Processing Configuration
      </h3>
      
      <div style={{ marginBottom: '20px' }}>
        <div style={{
          marginBottom: '8px',
          fontSize: '12px',
          color: 'var(--text-muted)',
          lineHeight: '1.4'
        }}>
          <strong>How it works:</strong> All files in your vault are automatically processed when changed, 
          <em> except</em> those matching the ignore patterns below. This is similar to how .gitignore works.
        </div>
      </div>

      {/* Frequency Limit Setting */}
      <div style={{ 
        marginBottom: '20px',
        padding: '12px',
        backgroundColor: 'var(--background-secondary)',
        border: '1px solid var(--background-modifier-border)',
        borderRadius: '8px'
      }}>
        <label style={{
          display: 'block',
          marginBottom: '8px',
          fontSize: '14px',
          fontWeight: '500',
          color: 'var(--text-normal)'
        }}>
          Processing Frequency Limit: {frequencyLimit} seconds
        </label>
        <input
          type="range"
          min="10"
          max="300"
          step="10"
          value={frequencyLimit}
          onChange={(e) => handleFrequencyLimitChange(parseInt(e.target.value))}
          style={{
            width: '100%',
            cursor: 'pointer'
          }}
        />
        <div style={{
          fontSize: '12px',
          color: 'var(--text-muted)',
          marginTop: '4px'
        }}>
          Minimum time between processing the same file. Higher values prevent excessive processing during heavy editing.
        </div>
      </div>

      {/* Ignore Patterns Configuration */}
      <div style={{ 
        marginBottom: '16px'
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '8px'
        }}>
          <label style={{
            fontSize: '14px',
            fontWeight: '500',
            color: 'var(--text-normal)'
          }}>
            Ignore Patterns (gitignore-style)
          </label>
          <button
            onClick={resetToDefault}
            style={{
              padding: '4px 12px',
              fontSize: '12px',
              border: '1px solid var(--background-modifier-border)',
              backgroundColor: 'var(--background-secondary)',
              color: 'var(--text-normal)',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
            onMouseOver={(e) => {
              (e.target as HTMLElement).style.backgroundColor = 'var(--background-modifier-hover)';
            }}
            onMouseOut={(e) => {
              (e.target as HTMLElement).style.backgroundColor = 'var(--background-secondary)';
            }}
          >
            Reset to Default
          </button>
        </div>
        
        <textarea
          value={ignoreConfig}
          onChange={(e) => handleIgnoreConfigChange(e.target.value)}
          placeholder="Enter ignore patterns here..."
          style={{
            width: '100%',
            height: '300px',
            padding: '12px',
            fontSize: '13px',
            fontFamily: 'var(--font-monospace, "Consolas", "Monaco", monospace)',
            lineHeight: '1.4',
            border: '1px solid var(--background-modifier-border)',
            borderRadius: '8px',
            backgroundColor: 'var(--background-primary)',
            color: 'var(--text-normal)',
            resize: 'vertical'
          }}
        />
      </div>

      <div style={{
        padding: '12px',
        backgroundColor: 'var(--background-secondary)',
        border: '1px solid var(--background-modifier-border)',
        borderRadius: '8px',
        fontSize: '12px',
        color: 'var(--text-muted)',
        lineHeight: '1.4'
      }}>
        <div style={{ fontWeight: '500', marginBottom: '8px', color: 'var(--text-normal)' }}>
          💡 Pattern Examples:
        </div>
        <div style={{ marginBottom: '4px' }}><code>temp/</code> - Ignore entire temp folder</div>
        <div style={{ marginBottom: '4px' }}><code>*.tmp</code> - Ignore all .tmp files</div>
        <div style={{ marginBottom: '4px' }}><code>**/*.log</code> - Ignore .log files in any subfolder</div>
        <div style={{ marginBottom: '4px' }}><code>!important.md</code> - Exception: process this file even if parent folder is ignored</div>
        <div style={{ marginTop: '8px', fontStyle: 'italic' }}>
          Changes take effect immediately. Use the toggle in the Files tab to enable/disable auto-processing.
        </div>
      </div>
    </div>
  );
}