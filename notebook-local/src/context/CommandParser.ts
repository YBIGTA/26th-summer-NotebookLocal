/**
 * CommandParser - Parse slash commands and @ mentions for RAG context
 * 
 * Supports:
 * - Slash commands: /rag-toggle, /rag-scope, /process-file, etc.
 * - At mentions: @filename.md, @folder/, @#tag, @recent, @active
 */

export interface SlashCommand {
  command: string;
  args: string[];
  position: number;
  length: number;
  fullMatch: string;
}

export interface AtMention {
  type: 'file' | 'folder' | 'tag' | 'special';
  target: string;
  query: string;
  position: number;
  length: number;
  fullMatch: string;
}

export interface ParsedMessage {
  cleanMessage: string;
  slashCommands: SlashCommand[];
  atMentions: AtMention[];
  hasCommands: boolean;
}

export class CommandParser {
  private static instance: CommandParser;

  // Slash command patterns
  private readonly slashCommandRegex = /\/([a-zA-Z][\w-]*)\s*([^\n\r]*)/g;
  
  // At mention patterns
  private readonly atMentionRegex = /@(#?[\w\-\/\.]+[\w\-\/]*)(\w*)/g;
  
  // Supported slash commands
  private readonly supportedSlashCommands = new Set([
    'rag-toggle',
    'rag-enable', 
    'rag-disable',
    'rag-scope',
    'rag-clear',
    'rag-status',
    'process-file',
    'process-folder',
    'reindex-vault',
    'show-files',
    'show-queue'
  ]);

  // Special mention types
  private readonly specialMentions = new Set([
    'recent',
    'active',
    'current',
    'all'
  ]);

  private constructor() {}

  static getInstance(): CommandParser {
    if (!CommandParser.instance) {
      CommandParser.instance = new CommandParser();
    }
    return CommandParser.instance;
  }

  /**
   * Parse a message for slash commands and @ mentions
   */
  parseMessage(input: string): ParsedMessage {
    const slashCommands = this.parseSlashCommands(input);
    const atMentions = this.parseAtMentions(input);
    
    // Remove commands from message to get clean content
    let cleanMessage = input;
    
    // Remove slash commands (from end to start to preserve positions)
    [...slashCommands]
      .sort((a, b) => b.position - a.position)
      .forEach(cmd => {
        const before = cleanMessage.slice(0, cmd.position);
        const after = cleanMessage.slice(cmd.position + cmd.length);
        cleanMessage = before + after;
      });

    // Remove @ mentions (from end to start to preserve positions)  
    [...atMentions]
      .sort((a, b) => b.position - a.position)
      .forEach(mention => {
        const before = cleanMessage.slice(0, mention.position);
        const after = cleanMessage.slice(mention.position + mention.length);
        cleanMessage = before + after;
      });

    // Clean up extra whitespace
    cleanMessage = cleanMessage.replace(/\s+/g, ' ').trim();

    return {
      cleanMessage,
      slashCommands,
      atMentions,
      hasCommands: slashCommands.length > 0 || atMentions.length > 0
    };
  }

  /**
   * Parse slash commands from input
   */
  parseSlashCommands(input: string): SlashCommand[] {
    const commands: SlashCommand[] = [];
    let match;

    // Reset regex lastIndex
    this.slashCommandRegex.lastIndex = 0;

    while ((match = this.slashCommandRegex.exec(input)) !== null) {
      const [fullMatch, command, argsString] = match;
      const position = match.index;
      
      // Only include supported commands
      if (this.supportedSlashCommands.has(command)) {
        const args = this.parseCommandArgs(argsString);
        
        commands.push({
          command,
          args,
          position,
          length: fullMatch.length,
          fullMatch
        });
      }
    }

    return commands;
  }

  /**
   * Parse @ mentions from input
   */
  parseAtMentions(input: string): AtMention[] {
    const mentions: AtMention[] = [];
    let match;

    // Reset regex lastIndex
    this.atMentionRegex.lastIndex = 0;

    while ((match = this.atMentionRegex.exec(input)) !== null) {
      const [fullMatch, target, query] = match;
      const position = match.index;
      
      const mentionInfo = this.parseAtMentionTarget(target);
      
      mentions.push({
        ...mentionInfo,
        query: query || '',
        position,
        length: fullMatch.length,
        fullMatch
      });
    }

    return mentions;
  }

  /**
   * Parse command arguments from argument string
   */
  private parseCommandArgs(argsString: string): string[] {
    if (!argsString.trim()) {
      return [];
    }

    // Simple argument parsing - splits on whitespace but respects quotes
    const args: string[] = [];
    let current = '';
    let inQuotes = false;
    let quoteChar = '';

    for (let i = 0; i < argsString.length; i++) {
      const char = argsString[i];
      
      if (!inQuotes && (char === '"' || char === "'")) {
        inQuotes = true;
        quoteChar = char;
      } else if (inQuotes && char === quoteChar) {
        inQuotes = false;
        quoteChar = '';
      } else if (!inQuotes && /\s/.test(char)) {
        if (current.trim()) {
          args.push(current.trim());
          current = '';
        }
      } else {
        current += char;
      }
    }

    if (current.trim()) {
      args.push(current.trim());
    }

    return args;
  }

  /**
   * Parse @ mention target to determine type
   */
  private parseAtMentionTarget(target: string): Pick<AtMention, 'type' | 'target'> {
    // Tag mention: @#tagname
    if (target.startsWith('#')) {
      return {
        type: 'tag',
        target: target.slice(1) // Remove #
      };
    }

    // Special mentions: @recent, @active, @current, @all
    if (this.specialMentions.has(target)) {
      return {
        type: 'special',
        target
      };
    }

    // Folder mention: @folder/ or @folder/subfolder/
    if (target.endsWith('/')) {
      return {
        type: 'folder',
        target: target.slice(0, -1) // Remove trailing /
      };
    }

    // File mention: @filename.md, @path/filename.md
    return {
      type: 'file',
      target
    };
  }

  /**
   * Validate if a slash command is supported
   */
  isValidSlashCommand(command: string): boolean {
    return this.supportedSlashCommands.has(command);
  }

  /**
   * Get list of supported slash commands
   */
  getSupportedSlashCommands(): string[] {
    return Array.from(this.supportedSlashCommands);
  }

  /**
   * Get list of special mention types
   */
  getSpecialMentions(): string[] {
    return Array.from(this.specialMentions);
  }

  /**
   * Get command suggestions based on partial input
   */
  getSlashCommandSuggestions(partial: string): Array<{
    command: string;
    description: string;
    usage: string;
  }> {
    const lowerPartial = partial.toLowerCase();
    const suggestions: Array<{ command: string; description: string; usage: string }> = [];

    const commandInfo = {
      'rag-toggle': {
        description: 'Toggle RAG on/off for this conversation',
        usage: '/rag-toggle'
      },
      'rag-enable': {
        description: 'Enable RAG for this conversation',
        usage: '/rag-enable'
      },
      'rag-disable': {
        description: 'Disable RAG for this conversation', 
        usage: '/rag-disable'
      },
      'rag-scope': {
        description: 'Set RAG context scope',
        usage: '/rag-scope [whole|folder|file]'
      },
      'rag-clear': {
        description: 'Clear current RAG context selection',
        usage: '/rag-clear'
      },
      'rag-status': {
        description: 'Show current RAG configuration',
        usage: '/rag-status'
      },
      'process-file': {
        description: 'Queue specific file for processing',
        usage: '/process-file <filename>'
      },
      'process-folder': {
        description: 'Queue entire folder for processing',
        usage: '/process-folder <foldername>'
      },
      'reindex-vault': {
        description: 'Rebuild entire RAG index',
        usage: '/reindex-vault'
      },
      'show-files': {
        description: 'Show file processing status',
        usage: '/show-files [status]'
      },
      'show-queue': {
        description: 'Show current processing queue',
        usage: '/show-queue'
      }
    };

    // Filter commands that match the partial input
    this.supportedSlashCommands.forEach(command => {
      if (command.toLowerCase().includes(lowerPartial) || lowerPartial === '') {
        const info = commandInfo[command as keyof typeof commandInfo];
        if (info) {
          suggestions.push({
            command,
            description: info.description,
            usage: info.usage
          });
        }
      }
    });

    return suggestions.sort((a, b) => a.command.localeCompare(b.command));
  }

  /**
   * Check if input is currently typing a command
   */
  isTypingSlashCommand(input: string, cursorPosition: number): { 
    isTyping: boolean; 
    commandStart: number;
    partialCommand: string;
  } {
    // Find the last slash before cursor position
    let lastSlashIndex = -1;
    for (let i = cursorPosition - 1; i >= 0; i--) {
      if (input[i] === '/') {
        lastSlashIndex = i;
        break;
      }
      if (input[i] === ' ' || input[i] === '\n') {
        break; // Found whitespace before slash
      }
    }

    if (lastSlashIndex === -1) {
      return { isTyping: false, commandStart: -1, partialCommand: '' };
    }

    // Check if there's whitespace before the slash (command should be at word boundary)
    if (lastSlashIndex > 0 && !/\s/.test(input[lastSlashIndex - 1])) {
      return { isTyping: false, commandStart: -1, partialCommand: '' };
    }

    // Extract the partial command
    const partialCommand = input.slice(lastSlashIndex + 1, cursorPosition);
    
    // Check if partial contains spaces (means we're in arguments)
    if (partialCommand.includes(' ')) {
      return { isTyping: false, commandStart: -1, partialCommand: '' };
    }

    return {
      isTyping: true,
      commandStart: lastSlashIndex,
      partialCommand
    };
  }

  /**
   * Check if input is currently typing an @ mention
   */
  isTypingAtMention(input: string, cursorPosition: number): {
    isTyping: boolean;
    mentionStart: number;
    partialMention: string;
  } {
    // Find the last @ before cursor position  
    let lastAtIndex = -1;
    for (let i = cursorPosition - 1; i >= 0; i--) {
      if (input[i] === '@') {
        lastAtIndex = i;
        break;
      }
      if (input[i] === ' ' || input[i] === '\n') {
        break; // Found whitespace before @
      }
    }

    if (lastAtIndex === -1) {
      return { isTyping: false, mentionStart: -1, partialMention: '' };
    }

    // Extract the partial mention
    const partialMention = input.slice(lastAtIndex + 1, cursorPosition);

    return {
      isTyping: true,
      mentionStart: lastAtIndex,
      partialMention
    };
  }
}