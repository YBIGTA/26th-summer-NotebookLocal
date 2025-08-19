import { ChatMessage } from "@/types/message";
import { BaseChainRunner } from "./BaseChainRunner";
import { apiClient } from "@/api/ApiClient";
import { getSettings } from "@/settings/model";

/**
 * API-based QA Chain Runner that replaces VaultQAChainRunner
 * Routes all processing to the FastAPI RAG server instead of local processing
 */
export class ApiVaultQAChainRunner extends BaseChainRunner {
  async run(
    userMessage: ChatMessage,
    abortController: AbortController,
    updateCurrentAiMessage: (message: string) => void,
    addMessage: (message: ChatMessage) => void,
    options: {
      debug?: boolean;
      ignoreSystemMessage?: boolean;
      updateLoading?: (loading: boolean) => void;
    }
  ): Promise<string> {
    const settings = getSettings();
    
    try {
      options.updateLoading?.(true);

      // Check if server is available
      const isConnected = await apiClient.testConnection();
      if (!isConnected) {
        const errorMessage = `Cannot connect to RAG server at ${settings.serverUrl || 'localhost:8000'}. Please check your server configuration in settings.`;
        updateCurrentAiMessage(errorMessage);
        return errorMessage;
      }

      // Check if index has documents
      const indexStatus = await apiClient.getIndexStatus();
      if (indexStatus.is_empty) {
        const emptyMessage = "No documents have been processed yet. Please upload some PDFs to the server first.";
        updateCurrentAiMessage(emptyMessage);
        return emptyMessage;
      }

      // Handle streaming vs non-streaming
      if (settings.enableStreaming) {
        return await this.handleStreamingResponse(
          userMessage,
          updateCurrentAiMessage,
          abortController,
          options
        );
      } else {
        return await this.handleRegularResponse(
          userMessage,
          updateCurrentAiMessage,
          options
        );
      }

    } catch (error) {
      const errorMessage = `Error communicating with RAG server: ${error.message}`;
      console.error('ApiVaultQAChainRunner error:', error);
      updateCurrentAiMessage(errorMessage);
      return errorMessage;
    } finally {
      options.updateLoading?.(false);
    }
  }

  private async handleRegularResponse(
    userMessage: ChatMessage,
    updateCurrentAiMessage: (message: string) => void,
    options: { debug?: boolean }
  ): Promise<string> {
    const chatResponse = await apiClient.chat({
      message: userMessage.message,
      chat_id: this.generateChatId(),
      context: this.extractContextFromMessage(userMessage),
    });

    const response = chatResponse.message;
    updateCurrentAiMessage(response);

    if (options.debug && chatResponse.sources?.length) {
      const debugInfo = `\n\n---\nSources: ${chatResponse.sources.join(', ')}`;
      updateCurrentAiMessage(response + debugInfo);
      return response + debugInfo;
    }

    return response;
  }

  private async handleStreamingResponse(
    userMessage: ChatMessage,
    updateCurrentAiMessage: (message: string) => void,
    abortController: AbortController,
    options: { debug?: boolean }
  ): Promise<string> {
    let fullResponse = '';
    let lastUpdateTime = 0;
    const UPDATE_THROTTLE = 50; // Update UI every 50ms max

    return new Promise((resolve, reject) => {
      // Handle abort signal
      const onAbort = () => {
        reject(new Error('Request was aborted'));
      };
      abortController.signal.addEventListener('abort', onAbort);

      apiClient.chatStream(
        {
          message: userMessage.message,
          chat_id: this.generateChatId(),
          context: this.extractContextFromMessage(userMessage),
          stream: true,
        },
        // onChunk
        (chunk: string) => {
          if (abortController.signal.aborted) return;
          
          fullResponse += chunk;
          
          // Throttle UI updates for better performance
          const now = Date.now();
          if (now - lastUpdateTime > UPDATE_THROTTLE) {
            updateCurrentAiMessage(fullResponse);
            lastUpdateTime = now;
          }
        },
        // onComplete
        () => {
          abortController.signal.removeEventListener('abort', onAbort);
          updateCurrentAiMessage(fullResponse); // Final update
          resolve(fullResponse);
        },
        // onError
        (error: Error) => {
          abortController.signal.removeEventListener('abort', onAbort);
          const errorMessage = `Streaming error: ${error.message}`;
          updateCurrentAiMessage(errorMessage);
          reject(new Error(errorMessage));
        }
      );
    });
  }

  private generateChatId(): string {
    return `obsidian_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private extractContextFromMessage(message: ChatMessage): Record<string, any> | undefined {
    // Extract any context information from the message
    // This could include file paths, selected text, etc.
    const context: Record<string, any> = {};

    // Add timestamp
    context.timestamp = new Date().toISOString();
    
    // Add message metadata if available
    if (message.sender) context.sender = message.sender;
    if (message.isVisible !== undefined) context.isVisible = message.isVisible;

    // You can extend this to include Obsidian-specific context like:
    // - Current file path
    // - Selected text
    // - Linked files
    // - Tags
    
    return Object.keys(context).length > 0 ? context : undefined;
  }

  /**
   * Override the handleResponse method to use API-based processing
   */
  protected async handleResponse(
    response: string,
    userMessage: ChatMessage,
    abortController: AbortController,
    addMessage: (message: ChatMessage) => void,
    updateCurrentAiMessage: (message: string) => void
  ): Promise<string> {
    // For API-based responses, we don't need additional processing
    // The server already handles all the complex logic
    return response;
  }
}