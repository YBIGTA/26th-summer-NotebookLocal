// Clean CopilotView - Simple chat interface with API calls
import React, { useState, useEffect, useRef } from "react";
import { ItemView, WorkspaceLeaf } from "obsidian";
import { Root, createRoot } from "react-dom/client";
import { ApiClient, ChatRequest } from "@/api/ApiClient-clean";
import { CHAT_VIEWTYPE } from "@/constants";

interface Message {
  id: string;
  content: string;
  sender: 'user' | 'assistant';
  timestamp: Date;
  sources?: string[];
}

interface CopilotViewProps {
  apiClient: ApiClient;
}

function ChatInterface({ apiClient }: CopilotViewProps) {
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
        chat_id: `chat_${Date.now()}`,
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
        content: `Error: ${error.message}`,
        sender: 'assistant',
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="copilot-chat-container" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div className="chat-header" style={{ padding: '10px', borderBottom: '1px solid var(--background-modifier-border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div 
            style={{ 
              width: '8px', 
              height: '8px', 
              borderRadius: '50%', 
              backgroundColor: isConnected ? '#4ade80' : '#ef4444' 
            }}
          />
          <span style={{ fontSize: '14px', fontWeight: '500' }}>
            Copilot Chat {isConnected ? '(Connected)' : '(Disconnected)'}
          </span>
          <button 
            onClick={checkConnection}
            style={{ 
              marginLeft: 'auto', 
              padding: '4px 8px', 
              fontSize: '12px',
              border: '1px solid var(--background-modifier-border)',
              backgroundColor: 'var(--background-secondary)',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Test Connection
          </button>
        </div>
      </div>

      {/* Messages */}
      <div 
        className="chat-messages" 
        style={{ 
          flex: 1, 
          overflow: 'auto', 
          padding: '10px',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px'
        }}
      >
        {messages.length === 0 && (
          <div style={{ 
            textAlign: 'center', 
            color: 'var(--text-muted)', 
            marginTop: '20px',
            fontSize: '14px'
          }}>
            {isConnected 
              ? "Start a conversation with your documents..." 
              : "Connect to the inference server to begin chatting"
            }
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
                maxWidth: '80%',
                padding: '8px 12px',
                borderRadius: '8px',
                backgroundColor: message.sender === 'user' 
                  ? 'var(--interactive-accent)' 
                  : 'var(--background-secondary)',
                color: message.sender === 'user' 
                  ? 'var(--text-on-accent)' 
                  : 'var(--text-normal)',
              }}
            >
              <div style={{ whiteSpace: 'pre-wrap', fontSize: '14px' }}>
                {message.content}
              </div>
              
              {message.sources && message.sources.length > 0 && (
                <div style={{ 
                  marginTop: '8px', 
                  fontSize: '12px', 
                  color: 'var(--text-muted)',
                  borderTop: '1px solid var(--background-modifier-border)',
                  paddingTop: '4px'
                }}>
                  Sources: {message.sources.join(', ')}
                </div>
              )}
              
              <div style={{ 
                fontSize: '11px', 
                color: 'var(--text-muted)', 
                marginTop: '4px',
                textAlign: 'right'
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
                padding: '8px 12px',
                borderRadius: '8px',
                backgroundColor: 'var(--background-secondary)',
                color: 'var(--text-muted)',
                fontSize: '14px',
              }}
            >
              Thinking...
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div 
        className="chat-input" 
        style={{ 
          padding: '10px', 
          borderTop: '1px solid var(--background-modifier-border)',
          display: 'flex',
          gap: '8px'
        }}
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder={isConnected ? "Ask about your documents..." : "Connect to server first"}
          disabled={!isConnected || isLoading}
          style={{
            flex: 1,
            minHeight: '40px',
            maxHeight: '120px',
            padding: '8px',
            border: '1px solid var(--background-modifier-border)',
            borderRadius: '6px',
            backgroundColor: 'var(--background-primary)',
            color: 'var(--text-normal)',
            resize: 'vertical',
            fontSize: '14px',
          }}
        />
        <button
          onClick={sendMessage}
          disabled={!input.trim() || !isConnected || isLoading}
          style={{
            padding: '8px 16px',
            border: 'none',
            borderRadius: '6px',
            backgroundColor: 'var(--interactive-accent)',
            color: 'var(--text-on-accent)',
            cursor: isConnected && input.trim() ? 'pointer' : 'not-allowed',
            opacity: (!input.trim() || !isConnected || isLoading) ? 0.5 : 1,
            fontSize: '14px',
            fontWeight: '500',
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}

export default class CopilotView extends ItemView {
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
    return "Copilot Chat";
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