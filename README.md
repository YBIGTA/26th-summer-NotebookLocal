# NotebookLocal - RAG System with Obsidian Integration

A comprehensive **Retrieval-Augmented Generation (RAG) system** that combines local inference capabilities with advanced Obsidian vault integration for intelligent document processing and contextual chat.

## 🏗️ Architecture Overview

```mermaid
graph TB
    subgraph "Obsidian Plugin (notebook-local)"
        UI[Enhanced Chat Interface]
        FM[File Manager View]
        CP[Context Preview Panel]
        ECI[Enhanced Chat Input]
        RCM[RAG Context Manager]
        VPM[Vault Processing Manager]
        VFC[Vault File Cache]
        VFW[Vault File Watcher]
    end
    
    subgraph "Inference Server"
        API[FastAPI Routes]
        VR[Vault Routes]
        CR[Context Routes]
        LLM[LLM Router]
        VDB[Vector Database]
        PG[(PostgreSQL)]
        PROC[Document Processor]
    end
    
    subgraph "External Services"
        MODELS[Local AI Models]
        WEAVIATE[Weaviate Vector DB]
    end
    
    UI --> API
    FM --> VR
    CP --> CR
    ECI --> RCM
    VPM --> VFC
    VFW --> VFC
    API --> LLM
    VR --> PG
    CR --> PG
    API --> VDB
    API --> PROC
    LLM --> MODELS
    VDB --> WEAVIATE
```

## 🎯 **Core Components**

### 📡 **Inference Server**
- **FastAPI Backend**: Multi-modal document processing with streaming responses
- **Database Integration**: PostgreSQL with vault_files table for processing status
- **Vector Storage**: Weaviate integration for semantic search
- **API Endpoints**: 14 endpoints covering vault management and RAG context

### 📝 **Obsidian Plugin** 
- **Enhanced Chat Interface**: Tabbed UI (Chat/Context/Files) with command support
- **Real-time File Management**: Hierarchical tree view with processing status indicators
- **Context Visualization**: Interactive RAG context preview with validation
- **Command System**: 11 slash commands + 4 @ mention types

### 🤖 **Command System**
- **Slash Commands**: `/rag-toggle`, `/process-file`, `/rag-scope`, etc.
- **@ Mentions**: `@filename.md`, `@folder/`, `@#tag`, `@recent`
- **Real-time Parsing**: Command highlighting and autocomplete
- **Context Management**: Dynamic RAG context updates

## 🚀 System Flow

### 1. Complete RAG Pipeline

```mermaid
sequenceDiagram
    participant U as User
    participant O as Obsidian Plugin
    participant VFW as Vault File Watcher
    participant API as Inference Server
    participant DB as PostgreSQL
    participant VDB as Vector DB
    participant LLM as LLM Router
    
    Note over U,LLM: Document Processing Flow
    O->>VFW: File created/modified in vault
    VFW->>API: POST /api/v1/vault/scan
    API->>DB: Insert/update vault_files table
    API->>API: Process document chunks
    API->>VDB: Store embeddings
    API->>DB: Update status to 'processed'
    
    Note over U,LLM: RAG Query Flow  
    U->>O: Type: "/rag-enable @important-doc.md What are the key points?"
    O->>O: Parse commands and mentions
    O->>API: POST /api/v1/rag/context/set (update context)
    O->>API: POST /api/v1/obsidian/chat (send message)
    API->>VDB: Retrieve relevant chunks
    API->>LLM: Generate response with context
    LLM-->>API: Stream response chunks
    API-->>O: Stream to user
```

### 2. File Processing Pipeline

```mermaid
graph LR
    A[File Change Detected] --> B[Content Hash Check]
    B -->|Changed| C[Update vault_files]
    C --> D[Queue Processing]
    D --> E[Extract & Chunk]
    E --> F[Generate Embeddings]
    F --> G[Store in Vector DB]
    G --> H[Update Status: processed]
    H --> I[UI Refresh]
    
    B -->|Unchanged| J[Skip Processing]
```

### 3. Command Processing Flow

```mermaid
graph TD
    A[User Input] --> B{Command Parser}
    B -->|/rag-enable| C[Enable RAG Context]
    B -->|/rag-scope whole| D[Set Context Scope]
    B -->|@filename.md| E[Add File to Context]
    B -->|@folder/| F[Add Folder to Context]
    B -->|Regular Text| G[Send to LLM with Context]
    
    C --> H[Update UI Indicators]
    D --> H
    E --> I[Context Preview Update]
    F --> I
    G --> J[RAG-Enhanced Response]
```

## 🛠️ **Key Features**

### **File Management Interface**
- **🌳 Hierarchical Tree View**: Navigate vault files with folder structure
- **📊 Processing Status Tracking**: 5 status indicators (🟢🟡🔄⚪🔴)
- **⚡ Batch Operations**: Select and process multiple files
- **🔍 Smart Filtering**: Filter by status, file type, search query
- **🔄 Real-time Updates**: Automatic refresh with file change detection

### **RAG Context Management**
- **🎯 Flexible Scoping**: Whole vault, selected files, or folder-based
- **📋 Visual Context Preview**: See exactly what's included in RAG context
- **⚠️ Context Validation**: Token estimation and size warnings
- **📈 Processing Statistics**: Track processed vs unprocessed files

### **Enhanced Chat Experience**
- **💬 Tabbed Interface**: Separate Chat, Context, and Files views
- **⚡ Command Autocomplete**: Real-time suggestions for commands and files
- **🎨 Syntax Highlighting**: Visual command and mention highlighting
- **📡 Streaming Responses**: Real-time response generation with abort option

### **Command System**
#### **Slash Commands (11 total)**
- `/rag-toggle` - Toggle RAG on/off
- `/rag-enable` / `/rag-disable` - Control RAG state  
- `/rag-scope whole|selected|folder` - Set context scope
- `/rag-clear` - Clear current context
- `/rag-status` - Show RAG status and stats
- `/process-file <path>` - Queue specific file for processing
- `/process-folder <path>` - Process entire folder
- `/reindex-vault` - Rebuild entire search index
- `/show-files` - Display file processing status
- `/show-queue` - Show current processing queue

#### **@ Mention System (4 types)**
- `@filename.md` - Add specific file to context
- `@folder/` - Add all files in folder to context  
- `@#tag` - Add files with specific tag
- `@recent` / `@active` / `@current` / `@all` - Special collections

## 📁 Project Structure

```
26th-summer-NotebookLocal/
├── README.md                     # This overview document
├── inference-server/             # FastAPI backend server
│   ├── README.md                # Server setup and API documentation
│   ├── requirements.txt         # Python dependencies
│   ├── main.py                  # FastAPI application entry point
│   ├── api/                     # API route modules
│   │   ├── routes.py           # Main routes + vault/context integration
│   │   ├── vault_routes.py     # File management endpoints
│   │   └── context_routes.py   # RAG context endpoints  
│   ├── src/                     # Core processing logic
│   │   ├── main.py             # Document processor
│   │   ├── llm/                # LLM routing and adapters
│   │   ├── storage/            # Vector and hybrid storage
│   │   └── database/           # PostgreSQL models
│   └── migrations/             # Database schema migrations
├── notebook-local/              # Obsidian plugin
│   ├── README.md               # Plugin setup and usage guide
│   ├── manifest.json           # Obsidian plugin metadata
│   ├── package.json            # Node.js dependencies
│   └── src/                    # Plugin source code
│       ├── main.ts             # Plugin entry point
│       ├── components/         # React UI components
│       │   ├── NotebookLocalView.tsx      # Main tabbed interface
│       │   ├── EnhancedChatInput.tsx      # Command-aware input
│       │   ├── FileManagerView.tsx        # File tree with status
│       │   └── ContextPreviewPanel.tsx    # RAG context visualization
│       ├── context/            # RAG context management
│       │   ├── RagContextManager.ts       # Central context controller
│       │   └── CommandParser.ts           # Command parsing logic
│       ├── vault/              # File system integration
│       │   ├── VaultFileWatcher.ts        # Real-time file monitoring
│       │   ├── VaultFileCache.ts          # Content-based caching
│       │   └── VaultProcessingManager.ts  # Batch processing
│       └── api/                # Server communication
│           └── ApiClient-clean.ts         # HTTP client with all endpoints
└── obsidian-original/          # Reference implementation
    └── src/                    # Source components adapted for notebook-local
```

## 🚀 Quick Start

### Prerequisites
- **Python 3.8+** with pip
- **Node.js 16+** with npm
- **PostgreSQL 12+** (local or remote)
- **Obsidian** with community plugins enabled
- **Optional**: Weaviate for vector storage

### Installation

1. **Clone Repository**
```bash
git clone <repository-url>
cd 26th-summer-NotebookLocal
```

2. **Set up Inference Server**
```bash
cd inference-server
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Database setup
createdb notebooklocal  # Create PostgreSQL database
alembic upgrade head    # Run migrations to create tables
```

3. **Configure Environment**
```bash
# Create .env file in inference-server/
cat > .env << EOF
DATABASE_URL=postgresql://user:password@localhost/notebooklocal
WEAVIATE_URL=http://localhost:8080
OPENAI_API_KEY=your-openai-key-here
MODEL_PROVIDER=openai
EOF
```

4. **Install Obsidian Plugin**
```bash
cd ../notebook-local
npm install
npm run build

# Copy to Obsidian vault plugins folder
cp -r dist/* /path/to/your/vault/.obsidian/plugins/notebook-local/
```

5. **Start the System**
```bash
# Terminal 1: Start inference server
cd inference-server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Enable plugin in Obsidian
# Settings → Community plugins → Enable "NotebookLocal"
```

## 🎮 Usage Guide

### **Getting Started Workflow**

1. **Open NotebookLocal in Obsidian**
   - Click the message-circle icon in ribbon, or
   - Use command palette: "NotebookLocal: Open Chat"

2. **Enable RAG System**
   ```
   /rag-enable
   ```
   You should see: `⚡ RAG system enabled`

3. **Add Files to Context**
   ```
   @important-document.md @research-folder/ @#meeting-notes
   ```
   Switch to Context tab to see what's included

4. **Check Processing Status**  
   ```
   /show-files
   ```
   Or switch to Files tab for visual status

5. **Process Unprocessed Files**
   ```
   /process-file path/to/document.pdf
   ```
   Or select files in Files tab and click "Process"

6. **Ask Questions**
   ```
   What are the main conclusions from the research documents?
   ```

### **Advanced Usage Examples**

#### **Context Management**
```bash
/rag-scope selected              # Only use selected files
@meeting-notes.md @project-docs/ # Add specific items
/rag-status                      # Check current context
```

#### **File Processing**
```bash
/process-folder research/        # Process entire folder
/show-queue                      # See processing status
/reindex-vault                   # Rebuild everything
```

#### **Smart Queries with Context**
```bash
@quarterly-reports.md What were our key metrics this quarter?
/rag-scope folder @2024-data/ Compare this year's performance to last year
```

## 📊 Database Schema

### **vault_files Table**
```sql
CREATE TABLE vault_files (
    file_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vault_path TEXT UNIQUE NOT NULL,
    file_type VARCHAR(10),
    content_hash VARCHAR(32),
    file_size BIGINT,
    modified_at TIMESTAMP,
    processing_status VARCHAR(20) DEFAULT 'unprocessed'
        CHECK (processing_status IN ('unprocessed', 'queued', 'processing', 'processed', 'error')),
    doc_uid UUID REFERENCES documents(doc_uid),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_vault_files_status ON vault_files(processing_status);
CREATE INDEX idx_vault_files_path ON vault_files(vault_path);
CREATE INDEX idx_vault_files_modified ON vault_files(modified_at);
```

## 🔧 API Endpoints

### **Vault Management** (`/api/v1/vault/`)
- `GET /files` - List vault files with filtering
- `POST /scan` - Scan vault for changes  
- `POST /process` - Queue files for processing
- `DELETE /files/{file_id}` - Remove from queue
- `GET /status` - Get processing statistics

### **RAG Context** (`/api/v1/rag/`)
- `POST /context/set` - Set RAG context scope
- `GET /context` - Get current context
- `POST /context/validate` - Validate context selection
- `POST /context/parse-command` - Parse slash commands
- `POST /context/autocomplete` - Get autocomplete suggestions
- `POST /search` - Context-aware search

### **Chat** (`/api/v1/obsidian/`)  
- `POST /chat` - Send chat message with RAG
- `POST /chat/stream` - Streaming chat responses
- `POST /search` - Semantic document search

## 🐛 Troubleshooting

### **Common Issues**

1. **Plugin Won't Load**
   - Check Obsidian developer console (Ctrl+Shift+I)
   - Verify files are in correct plugin directory
   - Ensure community plugins are enabled

2. **Server Connection Failed**
   - Verify inference server is running on port 8000
   - Check `.env` configuration 
   - Test with: `curl http://localhost:8000/health`

3. **Files Not Processing**
   - Check database connection in server logs
   - Verify supported file types (.md, .pdf, .txt, .docx)
   - Use `/show-queue` to see processing status

4. **RAG Context Not Working**
   - Ensure files are processed (🟢 status in Files tab)
   - Check context validation in Context tab
   - Try `/rag-status` for diagnostics

### **Debug Mode**

**Enable verbose logging:**
```bash
# Inference server
export LOG_LEVEL=DEBUG
uvicorn main:app --reload

# Obsidian plugin (browser console)
localStorage.setItem('notebook-local-debug', 'true');
```

**Check processing status:**
```bash
# Database query
psql notebooklocal -c "SELECT processing_status, COUNT(*) FROM vault_files GROUP BY processing_status;"
```

## 🔬 Development

### **Adding New Commands**

1. **Define in CommandParser.ts**
```typescript
const SLASH_COMMANDS = {
  'my-command': 'Description of new command'
};
```

2. **Add execution logic in RagContextManager.ts**
```typescript
async executeSlashCommand(command: SlashCommand): Promise<string> {
  switch (command.command) {
    case 'my-command':
      return this.handleMyCommand(command.args);
  }
}
```

3. **Add API endpoint (if needed)**
```python
@router.post("/my-endpoint")
async def my_endpoint():
    return {"result": "success"}
```

### **Adding New File Types**

1. **Update supported extensions in vault_routes.py**
```python
supported_extensions = {'.md', '.pdf', '.txt', '.docx', '.your-ext'}
```

2. **Add processing logic in document processor**
3. **Update file type icons in FileManagerView.tsx**

## 📈 Performance Considerations

### **File Processing**
- **Debounced watching**: 5-second delay prevents excessive processing
- **Content-based hashing**: Only process files when content actually changes
- **Batch processing**: Queue multiple files for efficient processing
- **Status tracking**: Skip already processed files

### **Memory Management**  
- **Multi-layer caching**: Memory + disk with automatic cleanup
- **Lazy loading**: Load file tree and metadata on demand
- **Streaming responses**: Prevent memory buildup with large responses

### **Database Optimization**
- **Indexed queries**: Fast lookups on status, path, and modified time
- **Connection pooling**: Efficient database connection management
- **Batch operations**: Group multiple file updates

## 🤝 Contributing

1. **Fork the repository**
2. **Create feature branch**: `git checkout -b feature/amazing-feature`
3. **Follow existing patterns**: Adapt from obsidian-original components
4. **Update documentation**: Add to relevant README files
5. **Test thoroughly**: Verify both frontend and backend changes
6. **Submit pull request**: Include screenshots and testing notes

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Obsidian team** for the excellent plugin API and development tools
- **FastAPI** for the robust and fast backend framework
- **LangChain/LangGraph** for AI workflow orchestration
- **PostgreSQL** and **Weaviate** for reliable data storage
- **React and TypeScript** communities for frontend development tools

---

**Built for the 26th Summer Research Program**
- Advanced RAG system with Obsidian integration
- Real-time file processing and context management  
- Command-driven user experience with visual feedback
- Multi-modal document processing capabilities

For detailed component documentation:
- [📡 Inference Server README](./inference-server/README.md)
- [📝 Obsidian Plugin README](./notebook-local/README.md)