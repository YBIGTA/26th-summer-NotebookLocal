# Inference Server - FastAPI Backend for RAG System

The **Inference Server** is the core backend component that handles document processing, vector storage, and AI model integration for the NotebookLocal RAG system with advanced Obsidian vault integration.

## 🏗️ Architecture Overview

```mermaid
graph TB
    subgraph "FastAPI Application"
        MAIN[main.py - Application Entry]
        ROUTES[routes.py - Main Chat/Document APIs]
        VR[vault_routes.py - File Management]
        CR[context_routes.py - RAG Context]
    end
    
    subgraph "Core Processing"
        PROC[Document Processor]
        LLM[LLM Router]
        STORAGE[Hybrid Storage]
        WORKFLOW[QA Workflow]
    end
    
    subgraph "Database Layer"
        PG[(PostgreSQL)]
        MODELS[SQLAlchemy Models]
        MIGRATIONS[Alembic Migrations]
    end
    
    subgraph "External Services"
        WEAVIATE[Weaviate Vector DB]
        OPENAI[OpenAI API]
        LOCAL[Local Models]
    end
    
    MAIN --> ROUTES
    MAIN --> VR
    MAIN --> CR
    ROUTES --> PROC
    ROUTES --> LLM
    VR --> PG
    CR --> PG
    PROC --> STORAGE
    STORAGE --> WEAVIATE
    LLM --> OPENAI
    LLM --> LOCAL
    MODELS --> PG
    MIGRATIONS --> PG
```

## 🎯 **Core Features**

### **Document Processing Pipeline**
- **Multi-format Support**: PDF, Markdown, TXT, DOCX
- **Content Extraction**: Text + image processing with PyMuPDF
- **Semantic Chunking**: Context-aware text segmentation
- **Embedding Generation**: OpenAI text-embedding-3-large
- **Vector Storage**: Weaviate integration with hybrid search

### **Vault Management System**
- **File Watching**: Integration with Obsidian vault file changes
- **Processing Status**: 5-state tracking (unprocessed/queued/processing/processed/error)
- **Content Hashing**: MD5-based change detection
- **Batch Processing**: Queue management for multiple files
- **Database Tracking**: PostgreSQL vault_files table

### **RAG Context Management**
- **Flexible Scoping**: Whole vault, selected files, or folder-based
- **Context Validation**: Token estimation and size warnings
- **Command Processing**: Parse and execute slash commands
- **File Association**: Link vault files to processed documents
- **Real-time Updates**: Status synchronization with frontend

### **API Endpoints**
- **14 Total Endpoints**: Chat, document management, vault, and context APIs
- **Streaming Support**: Real-time response generation
- **OpenAI Compatibility**: Standard chat completions format
- **Error Handling**: Comprehensive error responses and logging

## 📁 Project Structure

```
inference-server/
├── README.md                    # This documentation
├── main.py                      # FastAPI application entry point
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment configuration template
├── alembic.ini                  # Database migration configuration
│
├── api/                         # FastAPI route modules
│   ├── __init__.py
│   ├── routes.py                # Main routes (chat, documents, health)
│   ├── vault_routes.py          # Vault file management (8 endpoints)
│   └── context_routes.py        # RAG context management (6 endpoints)
│
├── src/                         # Core processing logic
│   ├── main.py                  # Document processor class
│   ├── database/                # Database models and connection
│   │   ├── __init__.py
│   │   ├── connection.py        # PostgreSQL connection setup
│   │   └── models.py            # SQLAlchemy models
│   ├── llm/                     # LLM routing and adapters
│   │   ├── __init__.py
│   │   ├── core/
│   │   │   └── router.py        # LLM router implementation
│   │   └── models/
│   │       ├── requests.py      # Request/response models
│   │       └── responses.py
│   ├── storage/                 # Vector and hybrid storage
│   │   ├── __init__.py
│   │   └── hybrid_store.py      # Weaviate + PostgreSQL integration
│   └── workflows/               # LangChain workflow implementations
│       ├── __init__.py
│       └── qa_workflow.py       # Question-answering pipeline
│
└── migrations/                  # Database schema management
    ├── versions/
    │   ├── 001_initial_schema.py
    │   ├── 002_add_documents.py
    │   ├── 003_add_chunks.py
    │   ├── 004_update_constraints.py
    │   └── 005_add_vault_files_table.py    # Latest: vault integration
    └── env.py                   # Alembic environment configuration
```

## 🚀 Installation & Setup

### **Prerequisites**
- Python 3.8 or higher
- PostgreSQL 12+ (local or remote)
- Optional: Weaviate for vector storage
- Optional: OpenAI API key for embeddings and chat

### **1. Environment Setup**

```bash
# Clone repository and navigate
cd inference-server

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### **2. Database Setup**

```bash
# Create PostgreSQL database
createdb notebooklocal

# Run migrations to create all tables
alembic upgrade head
```

### **3. Environment Configuration**

Create `.env` file:
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/notebooklocal

# Vector Database (optional)
WEAVIATE_URL=http://localhost:8080

# AI Model Configuration
OPENAI_API_KEY=your-openai-api-key-here
MODEL_PROVIDER=openai
DEFAULT_MODEL=gpt-4

# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=true
LOG_LEVEL=INFO
```

### **4. Start the Server**

```bash
# Development mode with auto-reload
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Production mode
uvicorn main:app --host 0.0.0.0 --port 8000
```

The server will be available at `http://localhost:8000`

## 📊 Database Schema

### **Core Tables**

#### **documents**
```sql
CREATE TABLE documents (
    doc_uid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    path TEXT,
    source_type VARCHAR(50),
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    chunk_count INTEGER DEFAULT 0,
    metadata JSONB
);
```

#### **chunks**  
```sql
CREATE TABLE chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_uid UUID REFERENCES documents(doc_uid) ON DELETE CASCADE,
    text TEXT NOT NULL,
    page INTEGER,
    section TEXT,
    chunk_index INTEGER,
    embedding VECTOR(1536),  -- For OpenAI embeddings
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### **vault_files** (New in v005)
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

-- Performance indexes
CREATE INDEX idx_vault_files_status ON vault_files(processing_status);
CREATE INDEX idx_vault_files_path ON vault_files(vault_path);
CREATE INDEX idx_vault_files_modified ON vault_files(modified_at);
```

### **Database Migrations**

Run migrations to update schema:
```bash
# See current revision
alembic current

# Upgrade to latest
alembic upgrade head

# Create new migration (if developing)
alembic revision --autogenerate -m "Description of changes"
```

## 🔧 API Documentation

### **Vault Management APIs** (`/api/v1/vault/`)

#### **GET /files**
List vault files with filtering and pagination.

**Parameters:**
- `status` (optional): Filter by processing status
- `file_type` (optional): Filter by file type
- `limit` (default: 100): Maximum files to return
- `offset` (default: 0): Pagination offset

**Response:**
```json
[
  {
    "file_id": "uuid",
    "vault_path": "folder/document.md",
    "file_type": "md",
    "content_hash": "md5-hash",
    "file_size": 1024,
    "modified_at": "2024-01-01T10:00:00",
    "processing_status": "processed",
    "doc_uid": "uuid-if-processed",
    "error_message": null,
    "created_at": "2024-01-01T09:00:00",
    "updated_at": "2024-01-01T10:30:00"
  }
]
```

#### **POST /scan**
Scan vault directory for file changes.

**Request:**
```json
{
  "vault_path": "/path/to/obsidian/vault",
  "force_rescan": false
}
```

**Response:**
```json
{
  "message": "Vault scan completed",
  "changes": {
    "new_files": ["new-doc.md"],
    "modified_files": ["updated-doc.md"],  
    "deleted_files": ["removed-doc.md"],
    "total_scanned": 150
  }
}
```

#### **POST /process**
Queue files for processing.

**Request:**
```json
{
  "file_paths": ["document1.pdf", "folder/document2.md"],
  "force_reprocess": false
}
```

#### **GET /status**
Get processing status summary.

**Response:**
```json
{
  "total_files": 100,
  "processed": 85,
  "queued": 5,
  "processing": 2,
  "unprocessed": 8,
  "error": 0,
  "last_scan": "2024-01-01T10:00:00"
}
```

### **RAG Context APIs** (`/api/v1/rag/`)

#### **POST /context/set**
Set RAG context scope and selection.

**Request:**
```json
{
  "enabled": true,
  "scope": "selected",
  "selected_files": ["important-doc.md"],
  "selected_folders": ["research/"],
  "selected_tags": ["meeting-notes"],
  "temporal_filters": {
    "include_recent": true,
    "recent_days": 7
  }
}
```

#### **GET /context**
Get current RAG context.

#### **POST /context/validate**
Validate context selection and get statistics.

**Response:**
```json
{
  "is_valid": true,
  "warnings": ["Large context size (~50,000 tokens)"],
  "errors": [],
  "stats": {
    "total_files": 25,
    "total_processed": 23,
    "estimated_tokens": 45000
  }
}
```

#### **POST /context/parse-command**
Parse slash commands and @ mentions.

**Request:**
```json
{
  "command": "/rag-enable",
  "context": { /* optional current context */ }
}
```

#### **POST /context/autocomplete**
Get autocomplete suggestions.

**Request:**
```json
{
  "query": "meet",
  "context_type": "file",
  "limit": 10
}
```

### **Chat APIs** (`/api/v1/obsidian/`)

#### **POST /chat**
Send chat message with RAG context.

**Request:**
```json
{
  "message": "What are the key findings?",
  "chat_id": "optional-session-id",
  "stream": false
}
```

#### **POST /chat/stream**
Streaming chat responses.

**Response:** Server-sent events format:
```
data: {"content": "The key", "chat_id": "123", "done": false}
data: {"content": " findings are...", "chat_id": "123", "done": false}
data: {"content": "", "chat_id": "123", "done": true}
```

## 🚀 **Document Processing Pipeline**

### **Complete Processing Flow**

```mermaid
sequenceDiagram
    participant V as Vault File Watcher
    participant API as Inference Server
    participant DB as PostgreSQL
    participant PROC as Document Processor
    participant VDB as Vector DB
    
    V->>API: POST /vault/scan (file changes detected)
    API->>DB: Update vault_files table
    API->>DB: Set status = 'queued'
    
    Note over API,VDB: Processing Pipeline
    API->>PROC: process_document(file_path)
    PROC->>PROC: Extract text/images
    PROC->>PROC: Generate chunks
    PROC->>PROC: Create embeddings
    PROC->>VDB: Store vectors
    PROC->>DB: Store document metadata
    API->>DB: Set status = 'processed'
```

### **1. File Ingestion**
```python
# main.py - Document processor
async def process_document(self, file_path: str):
    # Extract text and metadata
    content = self.extract_content(file_path)
    
    # Generate semantic chunks
    chunks = self.chunk_content(content)
    
    # Create embeddings
    embeddings = await self.generate_embeddings(chunks)
    
    # Store in vector database
    doc_uid = await self.store_document(chunks, embeddings)
    
    return {"doc_uid": doc_uid, "chunks": len(chunks)}
```

### **2. Supported File Types**
- **PDF**: PyMuPDF for text extraction with image handling
- **Markdown**: Native parsing with frontmatter support
- **Text**: Plain text files with encoding detection
- **DOCX**: Microsoft Word document processing

### **3. Chunking Strategy**
```python
# Semantic chunking with overlap
CHUNK_SIZE = 1000  # tokens
CHUNK_OVERLAP = 200  # tokens
MIN_CHUNK_SIZE = 100  # minimum viable chunk
```

### **4. Vector Storage**
```python
# hybrid_store.py - Weaviate integration
class HybridStore:
    def store_document(self, doc_uid, chunks, embeddings):
        # Store in Weaviate for vector search
        # Store metadata in PostgreSQL for relationships
        
    def search(self, query, k=5, alpha=0.7):
        # Hybrid search: vector + keyword
        # Return ranked results with metadata
```

## 🤖 LLM Integration

### **LLM Router Architecture**
```python
# llm/core/router.py
class LLMRouter:
    def __init__(self):
        self.adapters = {
            'openai': OpenAIAdapter(),
            'anthropic': AnthropicAdapter(),  
            'local': LocalModelAdapter()
        }
    
    async def route(self, request: ChatRequest):
        # Route to appropriate model based on request
        # Handle streaming and non-streaming responses
```

### **Model Providers**
- **OpenAI**: GPT-4, GPT-3.5-turbo with streaming
- **Anthropic**: Claude models (if configured)
- **Local Models**: Via vLLM or similar serving frameworks

### **RAG-Enhanced Chat Flow**
```python
# Example RAG-enhanced chat processing
async def obsidian_chat(request: ObsidianChatRequest):
    # 1. Convert to OpenAI format
    openai_request = convert_obsidian_to_openai(request)
    
    # 2. Add RAG context from vector search
    openai_request = add_rag_context(openai_request, request.message)
    
    # 3. Route to appropriate model
    response = await llm_router.route(openai_request)
    
    # 4. Convert back to Obsidian format
    return convert_openai_to_obsidian(response)
```

### **Context Integration**
```python
def add_rag_context(openai_request: ChatRequest, user_message: str) -> ChatRequest:
    """Add RAG context from vector search to OpenAI request."""
    # Get context using the existing workflow
    state = {"question": user_message}
    state = qa_workflow._retrieve(state)
    context = state.get("context", "")
    
    if context:
        # Add system message with context
        system_message = Message(
            role="system", 
            content=f"Context:\n{context}\n\nAnswer based on the provided context."
        )
        openai_request.messages.insert(0, system_message)
    
    return openai_request
```

## 🔧 Configuration

### **Environment Variables**

**Required:**
```bash
DATABASE_URL=postgresql://user:pass@host:port/dbname
```

**Optional:**
```bash
# Vector Database
WEAVIATE_URL=http://localhost:8080
WEAVIATE_API_KEY=optional-api-key

# AI Models
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=your-key-here
MODEL_PROVIDER=openai  # openai, anthropic, local
DEFAULT_MODEL=gpt-4

# Server
HOST=0.0.0.0
PORT=8000
DEBUG=false
LOG_LEVEL=INFO

# Processing
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
MAX_CONCURRENT_PROCESSING=5
```

### **Model Configuration**
```python
# src/llm/core/router.py
MODEL_CONFIG = {
    'openai': {
        'model': 'gpt-4',
        'temperature': 0.7,
        'max_tokens': 2048
    },
    'embedding': {
        'model': 'text-embedding-3-large',
        'dimensions': 1536
    }
}
```

## 📊 Monitoring & Debugging

### **Health Checks**

```bash
# Basic health
curl http://localhost:8000/health

# Detailed system health
curl http://localhost:8000/debug/health-detailed

# Database statistics  
curl http://localhost:8000/debug/db-stats
```

### **Health Check Response**
```json
{
  "timestamp": "2024-01-01T10:00:00",
  "system_status": "healthy",
  "components": {
    "postgresql": {
      "status": "connected",
      "can_query": true
    },
    "vector_store": {
      "status": "available",
      "type": "HybridStore"
    },
    "llm_router": {
      "status": "available",
      "adapters_count": 2
    }
  }
}
```

### **Database Statistics**
```json
{
  "timestamp": "2024-01-01T10:00:00",
  "total_documents": 42,
  "total_chunks": 1250,
  "documents_by_type": {
    "pdf": 15,
    "md": 20,
    "txt": 7
  },
  "chunk_size_distribution": {
    "small": 12,
    "medium": 25,
    "large": 5
  }
}
```

### **Logging Configuration**
```python
# Set log level
export LOG_LEVEL=DEBUG

# Key log points
- Document processing pipeline
- Database operations
- Vector storage operations  
- LLM routing decisions
- API request/response timing
```

## 🐛 Troubleshooting

### **Common Issues**

1. **Database Connection Failed**
   ```bash
   # Check PostgreSQL is running
   pg_isready -h localhost -p 5432
   
   # Verify connection string
   psql "postgresql://user:pass@localhost/notebooklocal"
   ```

2. **Weaviate Connection Issues**
   ```bash
   # Check Weaviate status
   curl http://localhost:8080/v1/meta
   
   # Start Weaviate with Docker
   docker run -p 8080:8080 semitechnologies/weaviate:latest
   ```

3. **Document Processing Errors**
   ```bash
   # Check supported file types
   SUPPORTED_EXTENSIONS = {'.md', '.pdf', '.txt', '.docx'}
   
   # Verify file permissions
   ls -la /path/to/problematic/file
   ```

4. **Memory Issues with Large Documents**
   ```python
   # Adjust chunk size
   CHUNK_SIZE = 500  # Smaller chunks
   MAX_CONCURRENT_PROCESSING = 2  # Reduce parallelism
   ```

### **Debug Commands**
```bash
# Check database schema
alembic current
alembic history

# Verify API endpoints
curl -X GET http://localhost:8000/api/v1/vault/status

# Test document processing
curl -X POST http://localhost:8000/api/v1/vault/scan \
  -H "Content-Type: application/json" \
  -d '{"vault_path": "/path/to/vault"}'

# Check processing status
curl -X GET http://localhost:8000/api/v1/vault/files?status=processed
```

### **Common Error Messages**

1. **"Table 'vault_files' doesn't exist"**
   ```bash
   # Run the latest migration
   alembic upgrade head
   ```

2. **"OpenAI API rate limit exceeded"**
   ```bash
   # Check your API usage and adjust processing rate
   # Consider using local models for embeddings
   ```

3. **"Weaviate connection refused"**
   ```bash
   # Start Weaviate locally
   docker run -p 8080:8080 semitechnologies/weaviate:latest
   ```

## 🚀 Deployment

### **Development Mode**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### **Production Mode**
```bash
# With Gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# With Docker
docker build -t notebooklocal-server .
docker run -p 8000:8000 --env-file .env notebooklocal-server
```

### **Docker Configuration**
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### **Docker Compose with Dependencies**
```yaml
version: '3.8'
services:
  inference-server:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/notebooklocal
      - WEAVIATE_URL=http://weaviate:8080
    depends_on:
      - postgres
      - weaviate

  postgres:
    image: postgres:13
    environment:
      - POSTGRES_DB=notebooklocal
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  weaviate:
    image: semitechnologies/weaviate:latest
    ports:
      - "8080:8080"
    environment:
      - QUERY_DEFAULTS_LIMIT=25
      - AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true

volumes:
  postgres_data:
```

## 🔬 Development

### **Adding New Endpoints**

1. **Create route in appropriate module**:
```python
# api/vault_routes.py
@router.post("/new-endpoint")
async def new_endpoint(db: Session = Depends(get_db)):
    return {"result": "success"}
```

2. **Add to main router**:
```python
# api/routes.py
router.include_router(vault_router)
```

3. **Update API client** (in notebook-local):
```typescript
// api/ApiClient-clean.ts
async newEndpoint(): Promise<any> {
  const response = await fetch(`${this.baseUrl}/api/v1/vault/new-endpoint`);
  return await response.json();
}
```

### **Database Schema Changes**

1. **Create migration**:
```bash
alembic revision --autogenerate -m "Add new table"
```

2. **Review generated migration**:
```python
# migrations/versions/xxx_add_new_table.py
def upgrade():
    op.create_table('new_table', ...)

def downgrade():
    op.drop_table('new_table')
```

3. **Apply migration**:
```bash
alembic upgrade head
```

### **Testing**
```bash
# Run tests (if implemented)
pytest tests/

# Manual API testing
curl -X POST http://localhost:8000/api/v1/test \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'

# Load testing
ab -n 100 -c 10 http://localhost:8000/health
```

## 📈 Performance Optimization

### **Database Optimization**
- **Indexes**: On frequently queried columns (status, path, modified_at)
- **Connection Pooling**: SQLAlchemy connection pool management
- **Batch Operations**: Group multiple file updates
- **Query Optimization**: Use EXPLAIN ANALYZE for slow queries

```sql
-- Example performance analysis
EXPLAIN ANALYZE SELECT * FROM vault_files WHERE processing_status = 'processed';

-- Add custom indexes if needed
CREATE INDEX idx_vault_files_custom ON vault_files(processing_status, modified_at);
```

### **Vector Search Optimization**  
- **Weaviate Memory**: Tune VECTOR_CACHE_MAX_OBJECTS
- **Distance Metrics**: Use appropriate metrics for your data
- **Result Caching**: Cache frequent search results
- **Batch Embeddings**: Process multiple documents together

### **Document Processing**
- **Parallel Processing**: Process multiple files concurrently
- **Streaming**: Handle large documents in chunks
- **Content Hashing**: Skip reprocessing unchanged files
- **Queue Management**: Prioritize processing by importance

```python
# Example optimization settings
PROCESSING_CONFIG = {
    'max_concurrent_files': 5,
    'chunk_size': 1000,
    'overlap': 200,
    'enable_caching': True,
    'cache_ttl': 3600  # 1 hour
}
```

## 🔐 Security Considerations

### **API Security**
- **Rate Limiting**: Prevent abuse of processing endpoints
- **Input Validation**: Sanitize file paths and content
- **Authentication**: Add API key authentication for production
- **File Type Validation**: Restrict to supported formats only

### **Database Security**
- **Connection Security**: Use SSL for PostgreSQL connections
- **Access Control**: Limit database user permissions
- **Data Encryption**: Encrypt sensitive data at rest
- **Backup Security**: Secure backup files

### **File Processing Security**
- **Path Traversal**: Prevent directory traversal attacks
- **File Size Limits**: Prevent DoS via large files
- **Content Scanning**: Check for malicious content
- **Temporary File Cleanup**: Remove temp files securely

---

**Built for the NotebookLocal RAG System**
- FastAPI backend with comprehensive vault integration
- Real-time processing status tracking
- Advanced RAG context management  
- Scalable document processing pipeline

For integration with the Obsidian plugin, see: [📝 Plugin README](../notebook-local/README.md)