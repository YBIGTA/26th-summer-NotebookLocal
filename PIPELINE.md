# NotebookLocal - Complete RAG System Pipeline

A comprehensive overview of the entire RAG system architecture and data flow pipeline.

## 🌊 **End-to-End Pipeline Flow**

```mermaid
graph TD
    A[User Creates/Modifies File] --> B[VaultFileWatcher Detects Change]
    B --> C[Calculate MD5 Hash]
    C --> D{Content Changed?}
    D -->|Yes| E[Update vault_files Table]
    D -->|No| F[Skip Processing]
    E --> G[Set Status: queued]
    G --> H[Document Processor]
    H --> I[Extract Text + Images]
    I --> J[Generate Semantic Chunks]
    J --> K[Create Embeddings]
    K --> L[Store in Weaviate]
    L --> M[Update PostgreSQL]
    M --> N[Set Status: processed]
    
    O[User Opens Chat] --> P[Enhanced Chat Input]
    P --> Q{Contains Commands?}
    Q -->|/rag-enable| R[Execute Slash Commands]
    Q -->|@filename.md| S[Parse @ Mentions]
    Q -->|Regular text| T[RAG Query]
    
    R --> U[Update RAG Context]
    S --> U
    U --> T
    T --> V[Retrieve Context from Weaviate]
    V --> W[Generate LLM Response]
    W --> X[Stream to User]
    
    style A fill:#e1f5fe
    style X fill:#c8e6c9
    style H fill:#fff3e0
    style V fill:#f3e5f5
```

## 🏗️ **System Architecture Layers**

### **1. Frontend Layer (Obsidian Plugin)**
```
┌─────────────────────────────────────────────────────────────┐
│                    Obsidian Plugin                          │
├─────────────────┬─────────────────┬─────────────────────────┤
│   Chat View     │  Context View   │     Files View          │
│                 │                 │                         │
│ • Streaming     │ • RAG Context   │ • File Tree            │
│ • Commands      │ • Validation    │ • Status Indicators     │
│ • @mentions     │ • Statistics    │ • Batch Operations      │
└─────────────────┴─────────────────┴─────────────────────────┘
         │                    │                     │
         └────────────────────┼─────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │   ApiClient        │
                    │ (14 HTTP Endpoints)│
                    └─────────┬──────────┘
                              │
```

### **2. Backend Layer (Inference Server)**
```
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI Inference Server                  │
├─────────────────┬─────────────────┬─────────────────────────┤
│  Vault Routes   │ Context Routes  │    Chat Routes          │
│  (8 endpoints)  │ (6 endpoints)   │   (Stream + Standard)   │
└─────────────────┴─────────────────┴─────────────────────────┘
         │                    │                     │
         └────────────────────┼─────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │  Document Processor│
                    │  + LLM Router      │
                    └─────────┬──────────┘
                              │
```

### **3. Storage Layer**
```
┌─────────────────────────────────────────────────────────────┐
│                    Storage Layer                            │
├─────────────────────────┬───────────────────────────────────┤
│     PostgreSQL          │         Weaviate                  │
│                         │                                   │
│ • vault_files (status)  │ • Vector embeddings               │
│ • documents (metadata)  │ • Semantic search                 │
│ • chunks (content)      │ • Hybrid search (vector+keyword)  │
└─────────────────────────┴───────────────────────────────────┘
```

## 📊 **Data Flow by Component**

### **File Processing Pipeline**
1. **Detection** → VaultFileWatcher monitors Obsidian vault
2. **Hashing** → MD5 content comparison for change detection  
3. **Queuing** → vault_files table updated with 'queued' status
4. **Processing** → Document processor extracts and chunks content
5. **Embedding** → Generate vector embeddings for semantic search
6. **Storage** → Store vectors in Weaviate, metadata in PostgreSQL
7. **Completion** → Update status to 'processed', refresh UI

### **Command Processing Pipeline**
1. **Input** → User types in EnhancedChatInput
2. **Parsing** → CommandParser identifies /commands and @mentions
3. **Validation** → Check command syntax and file existence
4. **Execution** → RagContextManager processes commands
5. **Update** → Context state synchronized with backend
6. **Feedback** → UI updates with command results

### **RAG Query Pipeline**
1. **Context Building** → Determine active RAG context scope
2. **Vector Search** → Query Weaviate for relevant chunks
3. **Context Assembly** → Combine retrieved content for LLM
4. **Generation** → LLM generates response with context
5. **Streaming** → Real-time response delivery to user
6. **Sources** → Display document sources for transparency

## 🔧 **Key Integration Points**

### **Frontend ↔ Backend Communication**
```typescript
// 14 API Endpoints providing complete functionality
ApiClient Methods:
├── Vault Management (8)
│   ├── getVaultFiles()        // List files with status
│   ├── scanVault()           // Detect file changes
│   ├── processVaultFiles()   // Queue processing
│   └── getVaultStatus()      // Processing statistics
├── RAG Context (6) 
│   ├── setRagContext()       // Update context
│   ├── getRagContext()       // Get current context
│   ├── validateRagContext()  // Validate selection
│   └── parseCommand()        // Process commands
└── Chat & Search
    ├── chat()                // Standard responses
    └── chatStream()          // Streaming responses
```

### **Real-time Synchronization**
```typescript
// Multi-layer sync strategy
Synchronization Points:
├── File Changes → VaultFileWatcher → API call → DB update
├── Processing Status → Periodic polling → UI refresh  
├── Context Updates → Command execution → State sync
└── Chat Messages → Streaming → Real-time display
```

## 📈 **Performance Characteristics**

### **Processing Throughput**
- **File Detection**: ~50ms (debounced to 5s)
- **Content Hashing**: ~10ms for typical documents
- **Document Processing**: ~2-30s (depends on size/complexity)
- **Vector Search**: ~100-500ms 
- **LLM Response**: ~2-15s (streaming starts immediately)

### **Storage Efficiency**
- **Duplicate Detection**: MD5 hashing prevents reprocessing
- **Content Caching**: Multi-layer cache (memory + disk)
- **Database Indexing**: Optimized queries on status, path, modified_at
- **Vector Compression**: Efficient storage in Weaviate

### **Memory Management**
- **Lazy Loading**: Components load on-demand
- **Cache Expiration**: Automatic cleanup (1 hour default)
- **Streaming**: Prevents memory buildup for large responses
- **Event Cleanup**: Proper listener management

## 🛠️ **Command System Architecture**

### **Slash Commands (11 total)**
```bash
/rag-* commands (6):     # RAG system control
├── /rag-enable         # Enable RAG system  
├── /rag-disable        # Disable RAG system
├── /rag-toggle         # Toggle RAG on/off
├── /rag-scope <type>   # Set context scope
├── /rag-clear          # Clear context
└── /rag-status         # Show status

/process-* commands (3): # File processing
├── /process-file       # Queue single file
├── /process-folder     # Queue entire folder  
└── /reindex-vault      # Rebuild everything

/show-* commands (2):    # Status display
├── /show-files         # File processing status
└── /show-queue         # Processing queue
```

### **@ Mention System (4 types)**
```bash
@file-mentions:         # Specific file targeting
├── @filename.md        # Add specific file
└── @folder/            # Add folder contents

@tag-mentions:          # Tag-based selection
└── @#tag-name          # Files with specific tag

@special-mentions:      # Dynamic selections  
├── @recent             # Recently modified
├── @active             # Currently active file
├── @current            # Current editor file
└── @all                # All vault files
```

## 🔄 **State Management Flow**

### **RAG Context State**
```typescript
RagContext {
  enabled: boolean              // RAG system on/off
  scope: 'whole'|'selected'     // Context breadth
  selectedFiles: Set<string>    // Individual files
  selectedFolders: Set<string>  // Folder contents
  selectedTags: Set<string>     // Tag-based files
  temporalFilters: {            // Time-based filters
    includeRecent: boolean
    includeActive: boolean
    recentDays: number
  }
  lastUpdated: Date            // Change tracking
}
```

### **Processing Status Flow**
```
unprocessed → queued → processing → processed
     ↑          ↑          ↓           ↓
     └──────────┴── error ←───────────┘

Status Indicators:
⚪ unprocessed  # Not yet processed
🟡 queued       # Waiting in queue  
🔄 processing   # Currently processing
🟢 processed    # Ready for RAG
🔴 error        # Processing failed
```

## 🎯 **User Experience Flow**

### **Typical Workflow**
1. **Setup**: Install plugin → Configure server connection
2. **Enable**: `/rag-enable` → RAG indicator appears  
3. **Context**: `@important-docs/` → Add content to context
4. **Process**: Switch to Files tab → Process unprocessed files
5. **Query**: "What are the main themes?" → Get RAG response
6. **Iterate**: Adjust context, ask follow-up questions

### **Advanced Workflows**
```bash
# Research Session
/rag-scope selected
@research-papers/ @meeting-notes/ @#important
/rag-status
"What are the key findings from recent research?"

# Project Review  
/rag-scope whole
/show-files
"What progress have we made on the quarterly goals?"

# Focused Analysis
@project-proposal.md 
/rag-scope selected
"What are the potential risks in this proposal?"
```

## 🔐 **Security & Privacy Pipeline**

### **Data Flow Security**
- **Local First**: File content stays in your vault
- **Transport Security**: HTTPS in production
- **Processing Security**: Temporary files cleaned up
- **No Retention**: Server doesn't store personal data

### **Input Validation Pipeline**
```
User Input → Command Parser → Validation → Sanitization → Execution
         ↓                  ↓             ↓              ↓
    Syntax Check    →  File Existence → Path Safety → Safe Execution
```

---

**🎉 Complete RAG System Pipeline**

This pipeline documentation provides a comprehensive view of how the NotebookLocal RAG system processes data from file creation through intelligent responses, ensuring users understand the complete flow of their information through the system.

**Key Benefits:**
- **Transparency**: Clear understanding of data flow
- **Performance**: Optimized at each pipeline stage  
- **Reliability**: Multiple validation and error handling points
- **Privacy**: Local-first architecture with optional cloud AI
- **Usability**: Command-driven interface with visual feedback