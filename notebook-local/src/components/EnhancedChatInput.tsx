/**
 * EnhancedChatInput - Chat input with command parsing and highlighting
 * 
 * Features:
 * - Real-time command parsing and syntax highlighting
 * - Autocomplete for / and @ commands
 * - Visual indicators for RAG status
 * - Command execution and context management
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { CommandParser, ParsedMessage } from '../context/CommandParser';
import { RagContextManager, RagContext } from '../context/RagContextManager';
import { CommandAutocomplete } from './CommandAutocomplete';

interface EnhancedChatInputProps {
  onSendMessage: (message: string, ragContext: RagContext) => void;
  ragContext: RagContext;
  onContextChange: (context: RagContext) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}

interface AutocompleteItem {
  type: 'command' | 'file' | 'folder' | 'tag' | 'special';
  id: string;
  label: string;
  description?: string;
  usage?: string;
  processingStatus?: string;
  icon?: string;
}

export const EnhancedChatInput: React.FC<EnhancedChatInputProps> = ({
  onSendMessage,
  ragContext,
  onContextChange,
  placeholder = "Type your message... Use / for commands, @ for files",
  disabled = false,
  className = ""
}) => {
  const [input, setInput] = useState('');
  const [cursorPosition, setCursorPosition] = useState(0);
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  const [parsedMessage, setParsedMessage] = useState<ParsedMessage | null>(null);
  const [isProcessingCommand, setIsProcessingCommand] = useState(false);
  
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const commandParser = useRef(CommandParser.getInstance());
  const ragContextManager = useRef(RagContextManager.getInstance());
  
  // Parse message on input change
  useEffect(() => {
    const parsed = commandParser.current.parseMessage(input);
    setParsedMessage(parsed);
    
    // Show autocomplete if typing command or mention
    const slashInfo = commandParser.current.isTypingSlashCommand(input, cursorPosition);
    const mentionInfo = commandParser.current.isTypingAtMention(input, cursorPosition);
    
    setShowAutocomplete(slashInfo.isTyping || mentionInfo.isTyping);
  }, [input, cursorPosition]);

  // Handle cursor position updates
  const handleCursorPositionChange = useCallback(() => {
    if (textareaRef.current) {
      setCursorPosition(textareaRef.current.selectionStart || 0);
    }
  }, []);

  // Handle input change
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    handleCursorPositionChange();
    
    // Auto-resize textarea
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  };

  // Handle key events
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Don't handle special keys when autocomplete is visible
    if (showAutocomplete && ['ArrowUp', 'ArrowDown', 'Enter', 'Escape'].includes(e.key)) {
      return; // Let CommandAutocomplete handle these
    }
    
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Handle autocomplete selection
  const handleAutocompleteSelect = (item: AutocompleteItem, replaceStart: number, replaceEnd: number) => {
    const beforeCursor = input.slice(0, replaceStart);
    const afterCursor = input.slice(replaceEnd);
    const newInput = beforeCursor + item.label + ' ' + afterCursor;
    
    setInput(newInput);
    setShowAutocomplete(false);
    
    // Set cursor position after the inserted text
    const newCursorPosition = replaceStart + item.label.length + 1;
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.setSelectionRange(newCursorPosition, newCursorPosition);
        textareaRef.current.focus();
        setCursorPosition(newCursorPosition);
      }
    }, 0);
  };

  // Handle sending message
  const handleSendMessage = async () => {
    if (!input.trim() || disabled || isProcessingCommand) {
      return;
    }

    const parsed = commandParser.current.parseMessage(input);
    
    if (parsed.hasCommands) {
      await handleCommandExecution(parsed);
    } else {
      // Send regular message
      onSendMessage(parsed.cleanMessage, ragContext);
      setInput('');
    }
  };

  // Execute commands
  const handleCommandExecution = async (parsed: ParsedMessage) => {
    setIsProcessingCommand(true);
    
    try {
      const results: string[] = [];
      
      // Execute slash commands
      for (const command of parsed.slashCommands) {
        const result = await ragContextManager.current.executeSlashCommand(command);
        results.push(result);
      }
      
      // Process @ mentions
      for (const mention of parsed.atMentions) {
        const result = await ragContextManager.current.processAtMention(mention);
        results.push(result);
      }
      
      // Update context from manager
      const newContext = ragContextManager.current.getContext();
      onContextChange(newContext);
      
      // Show command results if any
      if (results.length > 0) {
        const commandResults = results.join('\n');
        
        // If there's also a clean message, send both
        if (parsed.cleanMessage.trim()) {
          onSendMessage(`${parsed.cleanMessage}\n\n--- Command Results ---\n${commandResults}`, newContext);
        } else {
          // Just show command results as system message
          onSendMessage(`--- Command Results ---\n${commandResults}`, newContext);
        }
      } else if (parsed.cleanMessage.trim()) {
        // Send just the clean message
        onSendMessage(parsed.cleanMessage, newContext);
      }
      
      setInput('');
    } catch (error) {
      console.error('Error executing commands:', error);
      onSendMessage(`Error executing commands: ${error.message || error}`, ragContext);
    } finally {
      setIsProcessingCommand(false);
    }
  };

  // Render highlighted input
  const renderHighlightedInput = () => {
    if (!parsedMessage || !parsedMessage.hasCommands) {
      return input;
    }

    let highlightedHtml = input;
    const replacements: { start: number; end: number; replacement: string }[] = [];

    // Collect all command/mention positions for highlighting
    [...parsedMessage.slashCommands, ...parsedMessage.atMentions].forEach(item => {
      const start = item.position;
      const end = item.position + item.length;
      
      let className = '';
      if ('command' in item) {
        className = 'command-highlight';
      } else if ('type' in item) {
        className = `mention-highlight mention-${item.type}`;
      }
      
      replacements.push({
        start,
        end,
        replacement: `<span class="${className}">${item.fullMatch}</span>`
      });
    });

    // Apply replacements from end to start to preserve positions
    replacements
      .sort((a, b) => b.start - a.start)
      .forEach(({ start, end, replacement }) => {
        highlightedHtml = highlightedHtml.slice(0, start) + replacement + highlightedHtml.slice(end);
      });

    return highlightedHtml;
  };

  // Get RAG status indicator
  const getRagStatusIndicator = () => {
    if (!ragContext.enabled) {
      return { icon: '🔴', text: 'RAG Disabled', className: 'text-red-500' };
    }
    
    const fileCount = ragContext.selectedFiles.size;
    const folderCount = ragContext.selectedFolders.size;
    const tagCount = ragContext.selectedTags.size;
    
    if (ragContext.scope === 'whole') {
      return { icon: '🟢', text: 'RAG: Whole Vault', className: 'text-green-500' };
    }
    
    if (fileCount + folderCount + tagCount === 0) {
      return { icon: '🟡', text: 'RAG: No Context', className: 'text-yellow-500' };
    }
    
    const contextItems = [
      fileCount > 0 && `${fileCount} files`,
      folderCount > 0 && `${folderCount} folders`,
      tagCount > 0 && `${tagCount} tags`
    ].filter(Boolean).join(', ');
    
    return { icon: '🟢', text: `RAG: ${contextItems}`, className: 'text-green-500' };
  };

  const ragStatus = getRagStatusIndicator();

  return (
    <div className={`relative ${className}`}>
      {/* RAG Status Indicator */}
      <div className="mb-2 flex items-center justify-between text-xs">
        <div className={`flex items-center gap-1 ${ragStatus.className}`}>
          <span>{ragStatus.icon}</span>
          <span>{ragStatus.text}</span>
        </div>
        {parsedMessage?.hasCommands && (
          <div className="flex items-center gap-1 text-blue-500">
            <span>⚡</span>
            <span>
              {parsedMessage.slashCommands.length} commands, {parsedMessage.atMentions.length} mentions
            </span>
          </div>
        )}
      </div>

      {/* Input Container */}
      <div className="relative">
        {/* Syntax Highlighting Layer (hidden, for visual reference) */}
        <div 
          className="absolute inset-0 pointer-events-none opacity-0 whitespace-pre-wrap break-words p-3 text-transparent"
          style={{ 
            font: 'inherit',
            lineHeight: 'inherit',
            zIndex: 1
          }}
          dangerouslySetInnerHTML={{ __html: renderHighlightedInput() }}
        />
        
        {/* Actual Input */}
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onSelect={handleCursorPositionChange}
          onClick={handleCursorPositionChange}
          placeholder={placeholder}
          disabled={disabled || isProcessingCommand}
          className={`
            w-full min-h-[3rem] max-h-32 p-3 border border-border rounded-lg
            resize-none overflow-y-auto relative z-10
            bg-background text-foreground
            focus:outline-none focus:ring-2 focus:ring-primary
            ${isProcessingCommand ? 'opacity-50 cursor-wait' : ''}
            ${parsedMessage?.hasCommands ? 'border-blue-300' : ''}
          `}
          style={{ 
            fontFamily: 'inherit',
            fontSize: 'inherit',
            lineHeight: 'inherit'
          }}
        />

        {/* Send Button */}
        <button
          onClick={handleSendMessage}
          disabled={!input.trim() || disabled || isProcessingCommand}
          className={`
            absolute right-2 bottom-2 p-2 rounded-md
            ${input.trim() && !isProcessingCommand
              ? 'bg-primary text-primary-foreground hover:bg-primary/90' 
              : 'bg-muted text-muted-foreground cursor-not-allowed'
            }
            transition-colors z-20
          `}
        >
          {isProcessingCommand ? (
            <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
          ) : (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          )}
        </button>

        {/* Command Autocomplete */}
        <CommandAutocomplete
          input={input}
          cursorPosition={cursorPosition}
          onSelect={handleAutocompleteSelect}
          onClose={() => setShowAutocomplete(false)}
          isVisible={showAutocomplete}
        />
      </div>
      
      {/* Command Help */}
      {!input && (
        <div className="mt-2 text-xs text-muted-foreground">
          <div>Use <code>/</code> for commands: <code>/rag-toggle</code>, <code>/rag-scope</code>, <code>/process-file</code></div>
          <div>Use <code>@</code> for files/folders: <code>@filename.md</code>, <code>@folder/</code>, <code>@#tag</code></div>
        </div>
      )}

      {/* Custom Styles for Syntax Highlighting */}
      <style jsx>{`
        .command-highlight {
          background-color: rgba(59, 130, 246, 0.2);
          color: rgb(59, 130, 246);
          border-radius: 3px;
          padding: 1px 2px;
        }
        
        .mention-highlight {
          border-radius: 3px;
          padding: 1px 2px;
        }
        
        .mention-file {
          background-color: rgba(34, 197, 94, 0.2);
          color: rgb(34, 197, 94);
        }
        
        .mention-folder {
          background-color: rgba(251, 191, 36, 0.2);
          color: rgb(251, 191, 36);
        }
        
        .mention-tag {
          background-color: rgba(168, 85, 247, 0.2);
          color: rgb(168, 85, 247);
        }
        
        .mention-special {
          background-color: rgba(236, 72, 153, 0.2);
          color: rgb(236, 72, 153);
        }
      `}</style>
    </div>
  );
};