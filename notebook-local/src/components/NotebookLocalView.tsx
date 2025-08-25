// NotebookLocal Chat View - Enhanced chat interface with RAG context support
import React, { useState, useEffect, useRef } from "react";
import { ItemView, WorkspaceLeaf, App } from "obsidian";

// Global app reference for accessing Obsidian API
declare const app: App;
import { Root, createRoot } from "react-dom/client";
import { ApiClient, ChatRequest } from "../api/ApiClient-clean";
import { CHAT_VIEWTYPE } from "../constants-minimal";
import { getSettings } from "../settings/model-clean";
import { EnhancedChatInput } from "./EnhancedChatInput";
import { ContextPreviewPanel } from "./ContextPreviewPanel";
import { FileManagerView } from "./FileManagerView";
import { IntentIndicator } from "./IntentIndicator";
// Removed legacy imports - now using intelligence system
import { IntelligenceController, IntelligenceResponse } from "../intelligence/IntelligenceController";

interface Message {
  id: string;
  content: string;
  sender: 'user' | 'assistant';
  timestamp: Date;
  sources?: string[];
}

interface NotebookLocalViewProps {
  apiClient: ApiClient;
}

function ChatInterface({ apiClient }: NotebookLocalViewProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null);
  const [currentView, setCurrentView] = useState<'chat' | 'files' | 'context'>('chat');
  // Legacy RAG context removed
  const [lastIntelligenceResponse, setLastIntelligenceResponse] = useState<IntelligenceResponse | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  // Legacy context managers removed
  const intelligenceController = useRef(new IntelligenceController(apiClient));

  // Check connection on mount
  useEffect(() => {
    checkConnection();
  }, []);

  // Legacy RAG context initialization removed

  // Auto scroll to bottom when messages change or during streaming
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  const checkConnection = async () => {
    try {
      await apiClient.healthCheck();
      setIsConnected(true);
    } catch (error) {
      setIsConnected(false);
      console.error("Connection check failed:", error);
    }
  };

  const handleMessageSubmit = async (message: string) => {
    if (!message.trim() || isLoading || isStreaming) return;

    // Always use intelligence system - it handles @mentions intelligently
    await handleIntelligentMessage(message);
  };

  const handleIntelligentMessage = async (message: string) => {
    // Add user message to chat
    const userMessage: Message = {
      id: Date.now().toString(),
      content: message,
      sender: 'user',
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMessage]);
    
    // Get current note path
    const currentNotePath = app.workspace.getActiveFile()?.path;
    
    try {
      setIsLoading(true);
      
      // Process with intelligence controller
      const intelligenceResponse = await intelligenceController.current.processMessage(
        message,
        currentNotePath
      );
      
      // Create assistant message with intelligence response
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: intelligenceResponse.content,
        sender: 'assistant',
        timestamp: new Date(),
        sources: intelligenceResponse.sources,
      };
      
      setMessages(prev => [...prev, assistantMessage]);
      
      // Store intelligence response for UI display
      setLastIntelligenceResponse(intelligenceResponse);
      
      // Show intent and confidence in console for debugging
      console.log(`🎯 Intent: ${intelligenceResponse.intent_type}/${intelligenceResponse.sub_capability} (${intelligenceResponse.confidence.toFixed(2)})`);
      
    } catch (error) {
      console.error('Intelligent message error:', error);
      
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: `I had trouble understanding your request: ${error.message}. You can try using slash commands as a fallback.`,
        sender: 'assistant',
        timestamp: new Date(),
      };
      
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };


  const sendChatMessage = async (messageContent: string) => {
    const settings = getSettings();
    const request: ChatRequest = {
      message: messageContent,
      chat_id: `notebook_chat_${Date.now()}`,
      stream: settings.enableStreaming,
    };

    if (settings.enableStreaming) {
      // Streaming mode
      setIsStreaming(true);
      const assistantMessageId = (Date.now() + 1).toString();
      setStreamingMessageId(assistantMessageId);

      // Create initial empty assistant message
      const assistantMessage: Message = {
        id: assistantMessageId,
        content: "",
        sender: 'assistant',
        timestamp: new Date(),
        sources: [],
      };
      setMessages(prev => [...prev, assistantMessage]);

      try {
        // Create abort controller for this stream
        abortControllerRef.current = new AbortController();

        let fullContent = "";
        let sources: string[] = [];

        for await (const chunk of apiClient.chatStream(request)) {
          // Check if streaming was cancelled
          if (abortControllerRef.current?.signal.aborted) {
            break;
          }

          fullContent += chunk;
          
          // Update the streaming message content
          setMessages(prev => prev.map(msg => 
            msg.id === assistantMessageId 
              ? { ...msg, content: fullContent }
              : msg
          ));
        }

        // Final update with sources if available
        setMessages(prev => prev.map(msg => 
          msg.id === assistantMessageId 
            ? { ...msg, sources: sources }
            : msg
        ));

      } catch (error) {
        console.error("Streaming chat error:", error);
        
        const errorContent = `Connection Error: ${error.message}. Please check if the inference server is running.`;
        setMessages(prev => prev.map(msg => 
          msg.id === assistantMessageId 
            ? { ...msg, content: errorContent }
            : msg
        ));
      } finally {
        setIsStreaming(false);
        setStreamingMessageId(null);
        abortControllerRef.current = null;
      }
    } else {
      // Non-streaming mode (fallback)
      setIsLoading(true);
      
      try {
        const response = await apiClient.chat(request);

        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          content: response.message,
          sender: 'assistant',
          timestamp: new Date(),
          sources: response.sources,
        };

        setMessages(prev => [...prev, assistantMessage]);
      } catch (error) {
        console.error("Chat error:", error);
        
        const errorMessage: Message = {
          id: (Date.now() + 1).toString(),
          content: `Connection Error: ${error.message}. Please check if the inference server is running.`,
          sender: 'assistant',
          timestamp: new Date(),
        };

        setMessages(prev => [...prev, errorMessage]);
      } finally {
        setIsLoading(false);
      }
    }
  };

  const stopStreaming = () => {
    if (abortControllerRef.current && isStreaming) {
      abortControllerRef.current.abort();
      setIsStreaming(false);
      setStreamingMessageId(null);
    }
  };

  const clearChat = () => {
    setMessages([]);
  };

  const handleSendMessage = async (message: string) => {
    if (!message.trim() || isLoading || isStreaming) return;
    
    // Direct message processing with intelligence system
    await handleMessageSubmit(message);
  };

  const handleFileSelect = (file: any) => {
    // Navigate to file when selected in file manager
    const leaf = app.workspace.getLeaf(false);
    leaf.openFile(file);
  };

  // Legacy context management removed

  return (
    <div className="notebook-local-container" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header with tabs */}
      <div className="header-with-tabs" style={{ borderBottom: '1px solid var(--background-modifier-border)' }}>
        <div className="chat-header" style={{ padding: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <div 
              style={{ 
                width: '10px', 
                height: '10px', 
                borderRadius: '50%', 
                backgroundColor: isConnected ? '#10b981' : '#ef4444' 
              }}
            />
            <span style={{ fontSize: '16px', fontWeight: '600', color: 'var(--text-normal)' }}>
              NotebookLocal
            </span>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
            <span style={{ fontSize: '11px', padding: '2px 6px', backgroundColor: 'var(--interactive-accent)', color: 'white', borderRadius: '4px' }}>
              AI
            </span>
          </div>
          
          <div style={{ display: 'flex', gap: '8px' }}>
            <button 
              onClick={checkConnection}
              style={{ 
                padding: '4px 12px', 
                fontSize: '12px',
                border: '1px solid var(--background-modifier-border)',
                backgroundColor: 'var(--background-secondary)',
                color: 'var(--text-normal)',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              Test Connection
            </button>
            
            {messages.length > 0 && currentView === 'chat' && (
              <button 
                onClick={clearChat}
                style={{ 
                  padding: '4px 12px', 
                  fontSize: '12px',
                  border: '1px solid var(--background-modifier-border)',
                  backgroundColor: 'var(--background-secondary)',
                  color: 'var(--text-normal)',
                  borderRadius: '4px',
                  cursor: 'pointer'
                }}
              >
                Clear Chat
              </button>
            )}
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="tab-nav" style={{ display: 'flex', borderTop: '1px solid var(--background-modifier-border)' }}>
          {[
            { key: 'chat', label: 'Chat', icon: '💬' },
            { key: 'context', label: 'Context', icon: '📋' },
            { key: 'files', label: 'Files', icon: '📁' }
          ].map(tab => (
            <button
              key={tab.key}
              onClick={() => setCurrentView(tab.key as any)}
              style={{
                flex: 1,
                padding: '8px 12px',
                border: 'none',
                backgroundColor: currentView === tab.key ? 'var(--background-secondary)' : 'transparent',
                color: currentView === tab.key ? 'var(--text-normal)' : 'var(--text-muted)',
                borderBottom: currentView === tab.key ? '2px solid var(--interactive-accent)' : 'none',
                cursor: 'pointer',
                fontSize: '12px',
                fontWeight: currentView === tab.key ? '600' : 'normal'
              }}
            >
              {tab.icon} {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content Area */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        {currentView === 'chat' && (
          <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            {/* Chat Messages */}
            <div 
              className="chat-messages" 
              style={{ 
                flex: 1, 
                overflow: 'auto', 
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '16px'
              }}
            >
        {messages.length === 0 && (
          <div style={{ 
            textAlign: 'center', 
            color: 'var(--text-muted)', 
            marginTop: '40px',
            fontSize: '14px',
            lineHeight: '1.5'
          }}>
            {isConnected ? (
              <div>
                <div style={{ marginBottom: '8px', fontSize: '16px' }}>🧠</div>
                <div>Your intelligent vault assistant is ready!</div>
                <div style={{ fontSize: '12px', marginTop: '4px', lineHeight: '1.4' }}>
                  Ask naturally: "What did I conclude about X?" • "Find my notes about Y" • "Make this clearer"<br/>
                  Or use /commands and @mentions for precise control.
                </div>
              </div>
            ) : (
              <div>
                <div style={{ marginBottom: '8px', fontSize: '16px' }}>⚠️</div>
                <div>Connect to the inference server to begin</div>
                <div style={{ fontSize: '12px', marginTop: '4px' }}>
                  Make sure your local AI server is running on localhost:8000
                </div>
              </div>
            )}
          </div>
        )}

        {messages.map((message) => (
          <div 
            key={message.id}
            style={{
              display: 'flex',
              justifyContent: message.sender === 'user' ? 'flex-end' : 'flex-start',
            }}
          >
            <div
              style={{
                maxWidth: '85%',
                padding: '12px 16px',
                borderRadius: '12px',
                backgroundColor: message.sender === 'user' 
                  ? 'var(--interactive-accent)' 
                  : 'var(--background-secondary)',
                color: message.sender === 'user' 
                  ? 'var(--text-on-accent)' 
                  : 'var(--text-normal)',
                border: message.sender === 'assistant' 
                  ? '1px solid var(--background-modifier-border)' 
                  : 'none',
              }}
            >
              <div style={{ whiteSpace: 'pre-wrap', fontSize: '14px', lineHeight: '1.5' }}>
                {message.content}
              </div>
              
              {message.sources && message.sources.length > 0 && (
                <div style={{ 
                  marginTop: '12px', 
                  fontSize: '12px', 
                  color: 'var(--text-muted)',
                  borderTop: '1px solid var(--background-modifier-border)',
                  paddingTop: '8px'
                }}>
                  <div style={{ fontWeight: '500', marginBottom: '4px' }}>📄 Sources:</div>
                  <div>{message.sources.join(' • ')}</div>
                </div>
              )}
              
              <div style={{ 
                fontSize: '11px', 
                color: 'var(--text-muted)', 
                marginTop: '8px',
                textAlign: message.sender === 'user' ? 'right' : 'left'
              }}>
                {message.timestamp.toLocaleTimeString()}
              </div>
            </div>
          </div>
        ))}
        
        {(isLoading || isStreaming) && (
          <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
            <div
              style={{
                padding: '12px 16px',
                borderRadius: '12px',
                backgroundColor: 'var(--background-secondary)',
                color: 'var(--text-muted)',
                fontSize: '14px',
                border: '1px solid var(--background-modifier-border)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              <div>{isStreaming ? '⚡' : '🤔'}</div>
              <div>{isStreaming ? 'Streaming...' : 'Thinking...'}</div>
              {isStreaming && (
                <button
                  onClick={stopStreaming}
                  style={{
                    marginLeft: '12px',
                    padding: '4px 8px',
                    fontSize: '11px',
                    border: '1px solid var(--background-modifier-border)',
                    backgroundColor: 'var(--background-primary)',
                    color: 'var(--text-normal)',
                    borderRadius: '4px',
                    cursor: 'pointer'
                  }}
                >
                  Stop
                </button>
              )}
            </div>
          </div>
        )}
        
              <div ref={messagesEndRef} />
            </div>

            {/* Intent Indicator */}
            {lastIntelligenceResponse && (
              <div style={{ padding: '8px 16px', borderTop: '1px solid var(--background-modifier-border)' }}>
                <IntentIndicator
                  intent_type={lastIntelligenceResponse.intent_type}
                  sub_capability={lastIntelligenceResponse.sub_capability}
                  confidence={lastIntelligenceResponse.confidence}
                  visible={true}
                />
              </div>
            )}

            {/* Enhanced Chat Input */}
            <div style={{ borderTop: '1px solid var(--background-modifier-border)' }}>
              <EnhancedChatInput
                onSendMessage={handleSendMessage}
                disabled={!isConnected || isLoading || isStreaming}
                placeholder={isConnected ? "Ask naturally about your vault, or use @mentions for specific files..." : "Connect to server first"}
              />
            </div>
          </div>
        )}

        {currentView === 'context' && (
          <div style={{ height: '100%', overflow: 'auto', padding: '16px', color: 'var(--text-muted)' }}>
            <div>Context is now managed automatically by the intelligence system.</div>
            <div style={{ marginTop: '8px', fontSize: '12px' }}>Use @mentions to reference specific files or folders.</div>
          </div>
        )}

        {currentView === 'files' && (
          <div style={{ height: '100%', overflow: 'hidden' }}>
            <FileManagerView
              onFileSelect={handleFileSelect}
              apiClient={apiClient}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default class NotebookLocalView extends ItemView {
  root: Root | null = null;
  plugin: any; // Plugin reference

  constructor(leaf: WorkspaceLeaf, plugin: any) {
    super(leaf);
    this.plugin = plugin;
  }

  getViewType() {
    return CHAT_VIEWTYPE;
  }

  getDisplayText() {
    return "NotebookLocal Chat";
  }

  getIcon() {
    return "message-circle";
  }

  async onOpen() {
    const container = this.containerEl.children[1];
    container.empty();
    
    this.root = createRoot(container);
    this.root.render(
      <ChatInterface apiClient={this.plugin.getApiClient()} />
    );
  }

  async onClose() {
    this.root?.unmount();
  }
}