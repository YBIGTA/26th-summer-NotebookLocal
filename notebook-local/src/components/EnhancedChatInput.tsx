/**
 * EnhancedChatInput - Simplified chat input for natural language + @mentions
 * 
 * Features:
 * - Natural language input with @mention support
 * - Auto-resize textarea
 * - Send on Enter (Shift+Enter for new line)
 */

import React, { useState, useRef } from 'react';

interface EnhancedChatInputProps {
  onSendMessage: (message: string) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}

export const EnhancedChatInput: React.FC<EnhancedChatInputProps> = ({
  onSendMessage,
  placeholder = "Ask naturally about your vault, or use @mentions for specific files...",
  disabled = false,
  className = ""
}) => {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  
  // Handle input change with auto-resize
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    
    // Auto-resize textarea
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  };

  // Handle key events
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Send message
  const handleSendMessage = () => {
    if (!input.trim() || disabled) return;
    
    onSendMessage(input.trim());
    setInput('');
    
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  // Show @mention hints
  const renderMentionHints = () => {
    const hasAtMention = input.includes('@');
    
    if (!hasAtMention) return null;
    
    return (
      <div style={{ 
        fontSize: '11px', 
        color: 'var(--text-muted)', 
        padding: '4px 12px',
        borderTop: '1px solid var(--background-modifier-border)',
        backgroundColor: 'var(--background-secondary)'
      }}>
        💡 Use @file.md for files, @folder/ for folders, @file1.md,file2.md for multiple files
      </div>
    );
  };

  return (
    <div className={`enhanced-chat-input ${className}`}>
      <div style={{ 
        display: 'flex', 
        padding: '12px',
        gap: '8px',
        alignItems: 'flex-end'
      }}>
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          style={{
            flex: 1,
            minHeight: '38px',
            maxHeight: '120px',
            padding: '8px 12px',
            border: '1px solid var(--background-modifier-border)',
            borderRadius: '8px',
            backgroundColor: 'var(--background-primary)',
            color: 'var(--text-normal)',
            resize: 'none',
            fontSize: '14px',
            lineHeight: '1.4',
            outline: 'none'
          }}
        />
        
        <button
          onClick={handleSendMessage}
          disabled={disabled || !input.trim()}
          style={{
            padding: '8px 16px',
            border: 'none',
            borderRadius: '8px',
            backgroundColor: disabled || !input.trim() 
              ? 'var(--background-modifier-border)' 
              : 'var(--interactive-accent)',
            color: disabled || !input.trim() 
              ? 'var(--text-muted)' 
              : 'var(--text-on-accent)',
            cursor: disabled || !input.trim() ? 'not-allowed' : 'pointer',
            fontSize: '14px',
            fontWeight: '500',
            minWidth: '60px'
          }}
        >
          Send
        </button>
      </div>
      
      {renderMentionHints()}
    </div>
  );
};