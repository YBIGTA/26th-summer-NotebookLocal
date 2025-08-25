/**
 * GitIgnore-style pattern parser for auto-processing exclusions
 * Similar to .gitignore but for controlling document workflow processing
 */

export interface IgnoreRule {
  pattern: string;
  isNegation: boolean; // true for patterns starting with !
  isDirectory: boolean; // true for patterns ending with /
  regex: RegExp;
}

export class IgnoreParser {
  private rules: IgnoreRule[] = [];

  constructor(configText: string) {
    this.parseConfig(configText);
  }

  private parseConfig(configText: string): void {
    const lines = configText.split('\n');
    this.rules = [];

    for (const line of lines) {
      const trimmed = line.trim();
      
      // Skip empty lines and comments
      if (!trimmed || trimmed.startsWith('#')) {
        continue;
      }

      const isNegation = trimmed.startsWith('!');
      const pattern = isNegation ? trimmed.slice(1) : trimmed;
      const isDirectory = pattern.endsWith('/');
      const cleanPattern = isDirectory ? pattern.slice(0, -1) : pattern;

      // Convert gitignore pattern to regex
      const regex = this.patternToRegex(cleanPattern);

      this.rules.push({
        pattern: cleanPattern,
        isNegation,
        isDirectory,
        regex
      });
    }
  }

  private patternToRegex(pattern: string): RegExp {
    // Escape special regex characters except * and ?
    let regexPattern = pattern
      .replace(/[.+^${}()|[\]\\]/g, '\\$&')
      .replace(/\*/g, '.*')
      .replace(/\?/g, '.');

    // Handle ** for recursive directory matching
    regexPattern = regexPattern.replace(/\.\*\.\*/g, '.*');

    // If pattern starts with /, it's absolute from vault root
    if (pattern.startsWith('/')) {
      regexPattern = '^' + regexPattern.slice(1);
    } else {
      // Otherwise, it can match anywhere in the path
      regexPattern = '(^|/)' + regexPattern;
    }

    // Add end anchor
    regexPattern += '($|/)';

    return new RegExp(regexPattern);
  }

  /**
   * Check if a file path should be ignored from auto-processing
   * @param filePath - Vault-relative file path (e.g., "folder/file.md")
   * @returns true if file should be ignored, false if it should be processed
   */
  shouldIgnore(filePath: string): boolean {
    let shouldIgnore = false;

    // Process rules in order
    for (const rule of this.rules) {
      const matches = rule.regex.test(filePath);

      if (matches) {
        if (rule.isNegation) {
          // ! pattern - force include even if previously ignored
          shouldIgnore = false;
        } else {
          // Normal pattern - ignore this file
          shouldIgnore = true;
        }
      }
    }

    return shouldIgnore;
  }

  /**
   * Get all parsed rules for debugging
   */
  getRules(): IgnoreRule[] {
    return [...this.rules];
  }

  /**
   * Test multiple paths at once
   */
  filterIgnoredPaths(paths: string[]): { 
    toProcess: string[], 
    ignored: string[] 
  } {
    const toProcess: string[] = [];
    const ignored: string[] = [];

    for (const path of paths) {
      if (this.shouldIgnore(path)) {
        ignored.push(path);
      } else {
        toProcess.push(path);
      }
    }

    return { toProcess, ignored };
  }
}

/**
 * Create parser from current settings
 */
export function createIgnoreParserFromSettings(): IgnoreParser {
  const { getSettings } = require('../settings/model-clean');
  const settings = getSettings();
  return new IgnoreParser(settings.autoProcessingIgnoreConfig);
}