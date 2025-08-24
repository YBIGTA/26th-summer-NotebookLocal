/**
 * ContextPreviewPanel - Show intelligence system status and capabilities
 * 
 * Features:
 * - Display available capabilities (UNDERSTAND, NAVIGATE, etc.)
 * - Show recent intelligence responses
 * - @mention syntax help
 */

import React from 'react';

interface ContextPreviewPanelProps {
  className?: string;
}

export const ContextPreviewPanel: React.FC<ContextPreviewPanelProps> = ({
  className = ""
}) => {
  const capabilities = [
    {
      name: 'UNDERSTAND',
      icon: '🤔',
      description: 'Answer questions using your vault as ground truth',
      examples: ['What did I conclude about this topic?', 'Explain this idea from my notes']
    },
    {
      name: 'NAVIGATE', 
      icon: '🗺️',
      description: 'Find and discover content in your vault',
      examples: ['Find everything about API design', 'Show me related notes']
    },
    {
      name: 'TRANSFORM',
      icon: '✨', 
      description: 'Edit and improve your content intelligently',
      examples: ['Make this clearer', 'Restructure for better flow']
    },
    {
      name: 'SYNTHESIZE',
      icon: '🔄',
      description: 'Extract patterns and insights across multiple notes', 
      examples: ['Summarize my research findings', 'What patterns emerge?']
    },
    {
      name: 'MAINTAIN',
      icon: '🔧',
      description: 'Keep your vault healthy and organized',
      examples: ['Check for broken links', 'Find duplicate content']
    }
  ];

  const mentionSyntax = [
    {
      syntax: '@filename.md',
      description: 'Reference a specific file'
    },
    {
      syntax: '@folder/',
      description: 'Reference all files in a folder'
    },
    {
      syntax: '@file1.md,file2.md',
      description: 'Reference multiple files'
    }
  ];

  return (
    <div className={`context-preview-panel ${className}`} style={{ 
      padding: '16px',
      height: '100%',
      overflow: 'auto'
    }}>
      {/* Intelligence Capabilities */}
      <div style={{ marginBottom: '24px' }}>
        <h3 style={{ 
          margin: '0 0 12px 0',
          fontSize: '16px',
          fontWeight: '600',
          color: 'var(--text-normal)'
        }}>
          🧠 Intelligence Capabilities
        </h3>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {capabilities.map(cap => (
            <div key={cap.name} style={{
              padding: '12px',
              border: '1px solid var(--background-modifier-border)',
              borderRadius: '8px',
              backgroundColor: 'var(--background-secondary)'
            }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                marginBottom: '6px'
              }}>
                <span style={{ fontSize: '16px' }}>{cap.icon}</span>
                <span style={{ 
                  fontWeight: '600',
                  fontSize: '14px',
                  color: 'var(--text-normal)'
                }}>
                  {cap.name}
                </span>
              </div>
              
              <div style={{
                fontSize: '12px',
                color: 'var(--text-muted)',
                marginBottom: '8px'
              }}>
                {cap.description}
              </div>
              
              <div style={{ fontSize: '11px', color: 'var(--text-faint)' }}>
                Examples: {cap.examples.join(' • ')}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* @Mention Syntax */}
      <div>
        <h3 style={{ 
          margin: '0 0 12px 0',
          fontSize: '16px',
          fontWeight: '600',
          color: 'var(--text-normal)'
        }}>
          📎 @Mention Syntax
        </h3>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {mentionSyntax.map((item, index) => (
            <div key={index} style={{
              padding: '8px 12px',
              border: '1px solid var(--background-modifier-border)',
              borderRadius: '6px',
              backgroundColor: 'var(--background-primary)'
            }}>
              <div style={{
                fontFamily: 'var(--font-monospace)',
                fontSize: '13px',
                color: 'var(--text-accent)',
                marginBottom: '4px'
              }}>
                {item.syntax}
              </div>
              <div style={{
                fontSize: '12px',
                color: 'var(--text-muted)'
              }}>
                {item.description}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div style={{
        marginTop: '20px',
        padding: '12px',
        backgroundColor: 'var(--background-secondary)',
        borderRadius: '8px',
        fontSize: '12px',
        color: 'var(--text-muted)',
        lineHeight: '1.4'
      }}>
        💡 <strong>Intelligence System</strong><br/>
        Context is now built automatically based on your message and @mentions. 
        No manual setup required - just ask naturally!
      </div>
    </div>
  );
};