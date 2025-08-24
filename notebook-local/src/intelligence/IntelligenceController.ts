/**
 * IntelligenceController - Main orchestrator for natural language vault assistance.
 *
 * This replaces command-driven interaction with intent-based conversation.
 * Users can just talk naturally and the system figures out what they want.
 */

import {
  ApiClient,
  IntelligenceResponse,
  IntentHint,
  CapabilityInfo,
} from "../api/ApiClient-clean";

export class IntelligenceController {
  private apiClient: ApiClient;
  private conversationHistory: string[] = [];
  private sessionId: string;

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient;
    this.sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Parse @mentions from message for intelligent context building.
   */
  private parseIntelligentMentions(message: string): {
    cleanMessage: string;
    mentionedFiles: string[];
    mentionedFolders: string[];
  } {
    const mentionedFiles: string[] = [];
    const mentionedFolders: string[] = [];
    let cleanMessage = message;

    // Enhanced @mention regex that handles multiple files and folders
    const mentionRegex = /@([^@\s]+)/g;
    let match;

    while ((match = mentionRegex.exec(message)) !== null) {
      const mention = match[1];

      if (mention.endsWith("/")) {
        // Folder mention: @folder/ or @path/to/folder/
        mentionedFolders.push(mention.slice(0, -1)); // Remove trailing /
      } else if (mention.includes(",")) {
        // Multiple files: @file1.md,file2.md,file3.md
        const files = mention.split(",").map((f) => f.trim());
        mentionedFiles.push(...files);
      } else {
        // Single file: @filename.md or @path/to/file.md
        mentionedFiles.push(mention);
      }
    }

    // Remove @mentions from message for clean processing
    cleanMessage = message.replace(mentionRegex, "").trim();

    return { cleanMessage, mentionedFiles, mentionedFolders };
  }

  /**
   * Main entry point: process natural language message with full intelligence.
   */
  async processMessage(
    message: string,
    currentNotePath?: string,
    options: { maxTokens?: number } = {},
  ): Promise<IntelligenceResponse> {
    console.log(
      `🧠 Processing intelligent message: "${message.substring(0, 50)}..."`,
    );

    try {
      // Parse @mentions intelligently
      const { cleanMessage, mentionedFiles, mentionedFolders } =
        this.parseIntelligentMentions(message);

      // Add to conversation history (use clean message)
      this.conversationHistory.push(cleanMessage);

      // Keep history manageable (last 10 messages)
      if (this.conversationHistory.length > 10) {
        this.conversationHistory = this.conversationHistory.slice(-10);
      }

      // Show user what mentions were detected
      if (mentionedFiles.length > 0 || mentionedFolders.length > 0) {
        console.log(
          `📎 Detected mentions - Files: [${mentionedFiles.join(", ")}], Folders: [${mentionedFolders.join(", ")}]`,
        );
      }

      // Call the new intelligence endpoint
      const intelligenceResponse = await this.apiClient.intelligenceChat({
        message: cleanMessage,
        current_note_path: currentNotePath,
        conversation_history: this.conversationHistory.slice(0, -1), // Don't include current message
        session_id: this.sessionId,
        max_tokens: options.maxTokens,
        mentioned_files: mentionedFiles,
        mentioned_folders: mentionedFolders,
      });

      // Add response to conversation history for context
      this.conversationHistory.push(
        `[Assistant ${intelligenceResponse.intent_type}]: ${intelligenceResponse.content.substring(0, 100)}...`,
      );

      console.log(
        `✅ Intelligence response: ${intelligenceResponse.intent_type} (confidence: ${intelligenceResponse.confidence.toFixed(2)})`,
      );

      return intelligenceResponse;
    } catch (error) {
      console.error("Intelligence processing error:", error);

      // Return error response in expected format
      return {
        content: `I encountered an error processing your request: ${error.message}`,
        sources: [],
        confidence: 0.0,
        intent_type: "error",
        sub_capability: "error",
        metadata: { error: error.message },
        suggested_actions: [
          "Try rephrasing your question",
          "Check if server is running",
        ],
        session_id: this.sessionId,
      };
    }
  }

  /**
   * Get intent hints as user types (for autocomplete/suggestions).
   */
  async getIntentHints(
    partialMessage: string,
    currentNotePath?: string,
  ): Promise<IntentHint | null> {
    // Don't query for very short messages
    if (partialMessage.trim().length < 5) {
      return null;
    }

    try {
      const hint = await this.apiClient.detectIntent({
        message: partialMessage,
        current_note_path: currentNotePath,
        conversation_history: this.conversationHistory.slice(-3), // Last 3 for context
      });
      return hint;
    } catch (error) {
      console.warn("Intent hint detection failed:", error);
      return null;
    }
  }

  /**
   * Get information about available capabilities.
   */
  async getCapabilities(): Promise<CapabilityInfo | null> {
    try {
      return await this.apiClient.getIntelligenceCapabilities();
    } catch (error) {
      console.error("Failed to get capabilities:", error);
      return null;
    }
  }

  /**
   * Build context pyramid for debugging/preview.
   */
  async buildContextPreview(
    query: string,
    currentNotePath?: string,
    maxTokens?: number,
  ): Promise<any> {
    try {
      return await this.apiClient.buildContext({
        query,
        current_note_path: currentNotePath,
        max_tokens: maxTokens,
      });
    } catch (error) {
      console.error("Context preview failed:", error);
      return null;
    }
  }

  /**
   * Clear conversation history.
   */
  clearHistory(): void {
    this.conversationHistory = [];
    console.log("🧹 Conversation history cleared");
  }

  /**
   * Get current conversation context.
   */
  getConversationContext(): string[] {
    return [...this.conversationHistory];
  }

  /**
   * Check if message looks like it needs intelligence processing.
   */
  isIntelligentMessage(message: string): boolean {
    const cleanMessage = message.trim().toLowerCase();

    // Skip if it's just a slash command
    if (cleanMessage.startsWith("/")) {
      return false;
    }

    // Skip very short messages
    if (cleanMessage.length < 3) {
      return false;
    }

    // Process natural language messages
    return true;
  }

  /**
   * Get suggested message completions based on intent.
   */
  getMessageSuggestions(partialMessage: string): string[] {
    const message = partialMessage.toLowerCase();

    // Quick pattern-based suggestions
    const suggestions: string[] = [];

    if (message.includes("what")) {
      suggestions.push("What did I conclude about this topic?");
      suggestions.push("What are the main themes in my research?");
    }

    if (message.includes("find")) {
      suggestions.push("Find everything about [topic]");
      suggestions.push("Find my notes from last week");
    }

    if (message.includes("make") || message.includes("improve")) {
      suggestions.push("Make this clearer and more professional");
      suggestions.push("Improve the structure of this note");
    }

    if (message.includes("summarize") || message.includes("summary")) {
      suggestions.push("Summarize my progress this week");
      suggestions.push("Summarize the key findings from my research");
    }

    if (message.includes("check") || message.includes("fix")) {
      suggestions.push("Check my vault for broken links");
      suggestions.push("Check for duplicate content");
    }

    return suggestions.slice(0, 3); // Return top 3 suggestions
  }
}
