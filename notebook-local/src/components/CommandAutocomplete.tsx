/**
 * CommandAutocomplete - Real-time command and mention suggestions
 * 
 * Features:
 * - Fuzzy search for files, folders, and commands
 * - Keyboard navigation (↑↓ Enter Esc)
 * - Context-aware suggestions
 * - Processing status indicators
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { TFile, TFolder } from 'obsidian';
import { CommandParser } from '../context/CommandParser';
import { RagContextManager } from '../context/RagContextManager';
import { VaultFileCache } from '../vault/VaultFileCache';

interface AutocompleteItem {
  type: 'command' | 'file' | 'folder' | 'tag' | 'special';
  id: string;
  label: string;
  description?: string;
  usage?: string;
  processingStatus?: string;
  icon?: string;
}

interface CommandAutocompleteProps {
  input: string;
  cursorPosition: number;
  onSelect: (item: AutocompleteItem, replaceStart: number, replaceEnd: number) => void;
  onClose: () => void;
  isVisible: boolean;
  maxItems?: number;
}

export const CommandAutocomplete: React.FC<CommandAutocompleteProps> = ({
  input,
  cursorPosition,
  onSelect,
  onClose,
  isVisible,
  maxItems = 10
}) => {
  const [items, setItems] = useState<AutocompleteItem[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [commandContext, setCommandContext] = useState<{
    type: 'slash' | 'mention' | null;
    start: number;
    partial: string;
  }>({ type: null, start: -1, partial: '' });

  const commandParser = useRef(CommandParser.getInstance());
  const ragContextManager = useRef(RagContextManager.getInstance());
  const fileCache = useRef(VaultFileCache.getInstance<string>());
  const containerRef = useRef<HTMLDivElement>(null);

  // Detect command context and update suggestions
  useEffect(() => {
    if (!isVisible) {
      setItems([]);
      setCommandContext({ type: null, start: -1, partial: '' });
      return;
    }

    // Check for slash command
    const slashInfo = commandParser.current.isTypingSlashCommand(input, cursorPosition);
    if (slashInfo.isTyping) {
      setCommandContext({
        type: 'slash',
        start: slashInfo.commandStart,
        partial: slashInfo.partialCommand
      });
      updateSlashCommandSuggestions(slashInfo.partialCommand);
      return;
    }

    // Check for @ mention
    const mentionInfo = commandParser.current.isTypingAtMention(input, cursorPosition);
    if (mentionInfo.isTyping) {
      setCommandContext({
        type: 'mention',
        start: mentionInfo.mentionStart,
        partial: mentionInfo.partialMention
      });
      updateMentionSuggestions(mentionInfo.partialMention);
      return;
    }

    // No active command context
    setItems([]);
    setCommandContext({ type: null, start: -1, partial: '' });
  }, [input, cursorPosition, isVisible]);

  const updateSlashCommandSuggestions = useCallback((partial: string) => {
    const suggestions = commandParser.current.getSlashCommandSuggestions(partial);
    
    const items: AutocompleteItem[] = suggestions.slice(0, maxItems).map(cmd => ({
      type: 'command',
      id: cmd.command,
      label: `/${cmd.command}`,
      description: cmd.description,
      usage: cmd.usage,
      icon: '⚡'
    }));

    setItems(items);
    setSelectedIndex(0);
  }, [maxItems]);

  const updateMentionSuggestions = useCallback(async (partial: string) => {
    const suggestions: AutocompleteItem[] = [];

    try {
      // Special mentions
      if (!partial || partial.length < 2) {
        const specials = commandParser.current.getSpecialMentions();
        specials.forEach(special => {
          if (special.toLowerCase().includes(partial.toLowerCase())) {
            suggestions.push({
              type: 'special',
              id: special,
              label: `@${special}`,
              description: getSpecialMentionDescription(special),
              icon: getSpecialMentionIcon(special)
            });
          }
        });
      }

      // Tag mentions
      if (partial.startsWith('#')) {
        // TODO: Implement tag search when tag system is available
        suggestions.push({
          type: 'tag',
          id: partial.slice(1),
          label: `@${partial}`,
          description: `Search files with tag ${partial}`,
          icon: '🏷️'
        });
      }

      // File and folder search
      if (!partial.startsWith('#') && partial.length > 0) {
        const files = await searchFiles(partial);
        const folders = await searchFolders(partial);

        // Add file suggestions
        files.slice(0, Math.floor(maxItems * 0.7)).forEach(file => {
          const metadata = fileCache.current.getMetadata(file.path);
          suggestions.push({
            type: 'file',
            id: file.path,
            label: `@${file.basename}`,
            description: file.path,
            processingStatus: metadata?.processing_status || 'unprocessed',
            icon: getFileIcon(file.extension, metadata?.processing_status || 'unprocessed')
          });
        });

        // Add folder suggestions
        folders.slice(0, Math.floor(maxItems * 0.3)).forEach(folder => {
          suggestions.push({
            type: 'folder',
            id: folder.path,
            label: `@${folder.name}/`,
            description: folder.path,
            icon: '📁'
          });
        });
      }

      // Sort by relevance (exact matches first, then by type)
      suggestions.sort((a, b) => {
        const aExact = a.label.toLowerCase().includes(partial.toLowerCase());
        const bExact = b.label.toLowerCase().includes(partial.toLowerCase());
        
        if (aExact && !bExact) return -1;
        if (!aExact && bExact) return 1;
        
        const typeOrder = { special: 0, file: 1, folder: 2, tag: 3 };
        return typeOrder[a.type] - typeOrder[b.type];
      });

      setItems(suggestions.slice(0, maxItems));
      setSelectedIndex(0);
    } catch (error) {
      console.error('Error updating mention suggestions:', error);
      setItems([]);
    }
  }, [maxItems]);

  const searchFiles = async (query: string): Promise<TFile[]> => {
    const allFiles = app.vault.getMarkdownFiles();
    const lowerQuery = query.toLowerCase();
    
    return allFiles.filter(file => 
      file.basename.toLowerCase().includes(lowerQuery) ||
      file.path.toLowerCase().includes(lowerQuery)
    ).sort((a, b) => {
      // Prioritize basename matches over path matches
      const aBasenameMatch = a.basename.toLowerCase().includes(lowerQuery);
      const bBasenameMatch = b.basename.toLowerCase().includes(lowerQuery);
      
      if (aBasenameMatch && !bBasenameMatch) return -1;
      if (!aBasenameMatch && bBasenameMatch) return 1;
      
      return a.basename.localeCompare(b.basename);
    });
  };

  const searchFolders = async (query: string): Promise<TFolder[]> => {
    const allFolders: TFolder[] = [];
    const lowerQuery = query.toLowerCase();
    
    const collectFolders = (folder: TFolder) => {
      if (folder.name.toLowerCase().includes(lowerQuery) || 
          folder.path.toLowerCase().includes(lowerQuery)) {
        allFolders.push(folder);
      }
      
      folder.children.forEach(child => {
        if (child instanceof TFolder) {
          collectFolders(child);
        }
      });
    };

    collectFolders(app.vault.getRoot());
    
    return allFolders.sort((a, b) => a.name.localeCompare(b.name));
  };

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!isVisible || items.length === 0) return;

      switch (event.key) {
        case 'ArrowUp':
          event.preventDefault();
          setSelectedIndex(prev => prev > 0 ? prev - 1 : items.length - 1);
          break;
          
        case 'ArrowDown':
          event.preventDefault();
          setSelectedIndex(prev => prev < items.length - 1 ? prev + 1 : 0);
          break;
          
        case 'Enter':
          event.preventDefault();
          if (items[selectedIndex]) {
            handleItemSelect(items[selectedIndex]);
          }
          break;
          
        case 'Escape':
          event.preventDefault();
          onClose();
          break;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isVisible, items, selectedIndex, onClose]);

  // Auto-scroll selected item into view
  useEffect(() => {
    if (containerRef.current) {
      const selectedElement = containerRef.current.children[selectedIndex] as HTMLElement;
      if (selectedElement) {
        selectedElement.scrollIntoView({ 
          behavior: 'smooth', 
          block: 'nearest' 
        });
      }
    }
  }, [selectedIndex]);

  const handleItemSelect = (item: AutocompleteItem) => {
    const replaceStart = commandContext.start;
    const replaceEnd = commandContext.start + commandContext.partial.length + 1; // +1 for / or @
    
    onSelect(item, replaceStart, replaceEnd);
  };

  const handleItemClick = (item: AutocompleteItem, index: number) => {
    setSelectedIndex(index);
    handleItemSelect(item);
  };

  if (!isVisible || items.length === 0) {
    return null;
  }

  return (
    <div 
      ref={containerRef}
      className="absolute z-50 bg-background border border-border rounded-lg shadow-lg max-h-60 overflow-y-auto min-w-64"
      style={{ 
        top: '100%', 
        left: 0,
        marginTop: '4px'
      }}
    >
      {items.map((item, index) => (
        <div
          key={item.id}
          className={`
            px-3 py-2 cursor-pointer border-l-2 transition-colors
            ${index === selectedIndex 
              ? 'bg-accent border-l-accent-foreground' 
              : 'border-l-transparent hover:bg-muted'
            }
          `}
          onClick={() => handleItemClick(item, index)}
        >
          <div className="flex items-center gap-2">
            <span className="text-sm">{item.icon}</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-medium text-sm truncate">
                  {item.label}
                </span>
                {item.processingStatus && (
                  <span className="text-xs">
                    {getProcessingStatusIndicator(item.processingStatus)}
                  </span>
                )}
              </div>
              {item.description && (
                <div className="text-xs text-muted-foreground truncate">
                  {item.description}
                </div>
              )}
              {item.usage && (
                <div className="text-xs text-muted-foreground font-mono">
                  {item.usage}
                </div>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

// Helper functions
function getSpecialMentionDescription(special: string): string {
  const descriptions = {
    recent: 'Recently modified files',
    active: 'Currently active file',
    current: 'Current file in editor',
    all: 'All files in vault'
  };
  return descriptions[special as keyof typeof descriptions] || '';
}

function getSpecialMentionIcon(special: string): string {
  const icons = {
    recent: '🕒',
    active: '📝',
    current: '📄',
    all: '🗂️'
  };
  return icons[special as keyof typeof icons] || '⭐';
}

function getFileIcon(extension: string, processingStatus: string): string {
  const statusIcons = {
    processed: '🟢',
    queued: '🟡',
    processing: '🔄',
    unprocessed: '⚪',
    error: '🔴'
  };

  const statusIcon = statusIcons[processingStatus as keyof typeof statusIcons] || '⚪';
  
  const extIcons = {
    md: '📝',
    pdf: '📄',
    txt: '📄',
    docx: '📄'
  };

  const extIcon = extIcons[extension as keyof typeof extIcons] || '📄';
  
  return `${statusIcon} ${extIcon}`;
}

function getProcessingStatusIndicator(status: string): string {
  const indicators = {
    processed: '✅',
    queued: '⏳',
    processing: '⚡',
    unprocessed: '⚪',
    error: '❌'
  };
  return indicators[status as keyof typeof indicators] || '❓';
}