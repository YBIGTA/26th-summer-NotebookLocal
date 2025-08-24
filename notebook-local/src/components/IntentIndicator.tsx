/**
 * IntentIndicator - Shows detected intent and confidence to help users understand system behavior.
 */

import React from "react";

interface IntentIndicatorProps {
  intentType: string;
  subCapability: string;
  confidence: number;
  visible: boolean;
}

export function IntentIndicator({ intentType, subCapability, confidence, visible }: IntentIndicatorProps) {
  if (!visible) return null;
  
  // Map intent types to icons and colors
  const intentInfo = {
    'understand': { icon: '🤔', color: '#3b82f6', label: 'Understanding' },
    'navigate': { icon: '🧭', color: '#10b981', label: 'Navigating' },
    'transform': { icon: '✏️', color: '#f59e0b', label: 'Transforming' },
    'synthesize': { icon: '🔍', color: '#8b5cf6', label: 'Synthesizing' },
    'maintain': { icon: '🔧', color: '#ef4444', label: 'Maintaining' },
    'error': { icon: '❌', color: '#6b7280', label: 'Error' }
  };
  
  const info = intentInfo[intentType as keyof typeof intentInfo] || intentInfo.error;
  
  // Confidence indicator
  const confidenceColor = confidence >= 0.8 ? '#10b981' : confidence >= 0.6 ? '#f59e0b' : '#ef4444';
  
  return (
    <div 
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '6px 12px',
        fontSize: '11px',
        backgroundColor: 'var(--background-secondary)',
        border: `1px solid ${info.color}20`,
        borderRadius: '6px',
        margin: '4px 0',
        opacity: 0.8
      }}
    >
      <span style={{ fontSize: '14px' }}>{info.icon}</span>
      
      <span style={{ color: info.color, fontWeight: '500' }}>
        {info.label}
      </span>
      
      {subCapability !== 'general' && (
        <span style={{ color: 'var(--text-muted)', fontSize: '10px' }}>
          {subCapability.replace('_', ' ')}
        </span>
      )}
      
      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '4px' }}>
        <div 
          style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            backgroundColor: confidenceColor
          }}
        />
        <span style={{ color: 'var(--text-muted)', fontSize: '10px' }}>
          {Math.round(confidence * 100)}%
        </span>
      </div>
    </div>
  );
}