// NotebookLocal Chat View - Clean chat interface with API calls
import React, { useState, useEffect, useRef } from "react";
import { ItemView, WorkspaceLeaf } from "obsidian";
import { Root, createRoot } from "react-dom/client";
import { ApiClient, ChatRequest } from "../api/ApiClient-clean";
import { CHAT_VIEWTYPE } from "../constants-minimal";

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
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Check connection on mount
  useEffect(() => {
    checkConnection();
  }, []);

  // Auto scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const checkConnection = async () => {
    try {
      await apiClient.healthCheck();
      setIsConnected(true);
    } catch (error) {
      setIsConnected(false);
      console.error("Connection check failed:", error);
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content: input.trim(),
      sender: 'user',
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const request: ChatRequest = {
        message: userMessage.content,
        chat_id: `notebook_chat_${Date.now()}`,
        stream: false,
      };

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
  };

  const clearChat = () => {
    setMessages([]);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="notebook-local-chat-container" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div className="chat-header" style={{ padding: '12px', borderBottom: '1px solid var(--background-modifier-border)' }}>
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
          
          {messages.length > 0 && (
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

      {/* Messages */}
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
                <div style={{ marginBottom: '8px', fontSize: '16px' }}>🚀</div>
                <div>Ready to chat with your Korean PDFs!</div>
                <div style={{ fontSize: '12px', marginTop: '4px' }}>
                  Upload documents using the command palette or start asking questions.
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
        
        {isLoading && (
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
              <div>🤔</div>
              <div>Thinking...</div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div 
        className="chat-input" 
        style={{ 
          padding: '16px', 
          borderTop: '1px solid var(--background-modifier-border)',
          display: 'flex',
          gap: '8px'
        }}
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder={isConnected ? "Ask about your Korean PDFs..." : "Connect to server first"}
          disabled={!isConnected || isLoading}
          style={{
            flex: 1,
            minHeight: '44px',
            maxHeight: '120px',
            padding: '12px',
            border: '1px solid var(--background-modifier-border)',
            borderRadius: '8px',
            backgroundColor: 'var(--background-primary)',
            color: 'var(--text-normal)',
            resize: 'vertical',
            fontSize: '14px',
            fontFamily: 'inherit',
          }}
        />
        <button
          onClick={sendMessage}
          disabled={!input.trim() || !isConnected || isLoading}
          style={{
            padding: '12px 20px',
            border: 'none',
            borderRadius: '8px',
            backgroundColor: 'var(--interactive-accent)',
            color: 'var(--text-on-accent)',
            cursor: isConnected && input.trim() ? 'pointer' : 'not-allowed',
            opacity: (!input.trim() || !isConnected || isLoading) ? 0.5 : 1,
            fontSize: '14px',
            fontWeight: '500',
            minWidth: '60px',
          }}
        >
          {isLoading ? '...' : 'Send'}
        </button>
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