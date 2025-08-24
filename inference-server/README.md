# Inference Server - Context-Aware Intelligence System

The **Inference Server** is the core backend of the NotebookLocal RAG system featuring **Context-Aware Intelligence** - an advanced AI architecture that understands *why* you're asking something, not just *what* you're asking. Instead of generic search → retrieve → answer, it models **five fundamental ways humans interact with knowledge**.

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

## 🧠 **Context-Aware Intelligence Architecture**

### **Ideological Foundation: Second Brain Philosophy**

Your system treats the vault as a **"second brain"** that should understand *why* you're asking something, not just *what* you're asking. It models **five fundamental ways humans interact with knowledge**:

1. **🤔 UNDERSTAND** - "What does this mean?" (traditional Q&A)
2. **🧭 NAVIGATE** - "What should I read next?" (discovery & exploration)  
3. **✏️ TRANSFORM** - "Make this better" (editing & improvement)
4. **🔍 SYNTHESIZE** - "What patterns emerge?" (analysis across notes)
5. **🔧 MAINTAIN** - "Fix my vault" (organization & health)

This mirrors how you naturally think about your notes - sometimes you want answers, sometimes you want to explore, sometimes you want to improve content.

### **Technical Architecture: Intent Routing Flow**

```mermaid
graph TD
    A[User Message] --> B[Intent Detector]
    B --> C{Pattern Confident?}
    C -->|Yes| D[Use Pattern Result]
    C -->|No| E[LLM Classification]
    E --> F[Combine Pattern + LLM]
    F --> G[Context Engine]
    G --> H[Build Context Pyramid]
    H --> I[Route to Capability Engine]
    I --> J[Generate Response with Sources]
```

#### **1. Intent Detection Pipeline**

**Pattern-Based Detection (Fast):**
- Regex patterns for each intent type
- "what/how/why" → UNDERSTAND  
- "find/search" → NAVIGATE
- "rewrite/improve" → TRANSFORM
- etc.

**LLM-Based Detection (Nuanced):**
- Falls back to LLM when patterns aren't confident enough
- Uses configurable prompts from `configs/prompts.yaml`
- Returns JSON with intent, confidence, sub-capability, reasoning

**Example:**
```python
# Pattern matching finds "what" and "explain" → UNDERSTAND intent
# But LLM can detect nuanced cases like:
# "I'm struggling to understand the connection between X and Y"
# → NAVIGATE intent (finding connections) rather than UNDERSTAND
```

#### **2. Context Pyramid Construction**

The **most sophisticated part** - your `ContextEngine` builds a "pyramid" of relevance-ranked information:

```
Layer 0: @mentions (files/folders explicitly referenced)  ← Highest Priority
Layer 1: Current note (if editing)
Layer 2: Linked notes ([[wikilinks]] from current note)  
Layer 3: Semantically similar notes (vector search)
Layer 4: Recent notes (temporal context)
Layer 5: Tagged notes (#shared-tags)                     ← Lowest Priority
```

**Token Budget Management:**
- 60% reserved for @mentions and current note
- 30% for linked notes and semantic results  
- 10% for recent/tagged context
- Smart truncation prevents context overflow

#### **3. Capability Engine Routing**

Each intent type has a specialized engine with **sub-capabilities**:

```
🤔 UNDERSTAND Engine:
  ├── question_answer (direct Q&A)
  ├── explanation (deeper explanations)  
  ├── verification (fact-checking)
  └── definition (concept clarification)

🧭 NAVIGATE Engine:
  ├── search (find specific content)
  ├── discover (explore related ideas)
  ├── recommend (suggest next reading)
  └── browse (general exploration)

✏️ TRANSFORM Engine:
  ├── rewrite (rephrase content)
  ├── restructure (reorganize)
  ├── format (style changes)
  └── improve (enhance clarity)

🔍 SYNTHESIZE Engine:
  ├── summarize (distill key points)
  ├── analyze (extract patterns)
  ├── compare (contrast ideas)
  └── timeline (temporal analysis)

🔧 MAINTAIN Engine:
  ├── health_check (vault diagnostics)
  ├── fix_links (repair broken links)
  ├── organize (structural cleanup)
  └── find_duplicates (identify redundancy)
```

## 🎯 **The Five Core Intelligence Functions**

### **1. 🤔 UNDERSTAND Engine - "What does this mean?"**

**Philosophy:** Answer questions using vault content as ground truth. Never invent information not in the vault.

**Core Behaviors:**
- Always cite which notes information comes from
- Understand questions in context of current work
- Detect when information is missing and say so
- Provide grounded, fact-based responses

**Sub-capabilities:**
- **question_answer**: Direct Q&A from vault content
- **explanation**: Deeper explanations of concepts
- **verification**: Fact-checking against your notes
- **definition**: Define terms based on your usage

**Example Query:** *"What did I conclude about transformers in my AI research? @research/papers"*

**Response Format:**
```
Based on your research notes, you concluded that transformers revolutionized NLP through:

1. **Self-attention mechanisms** (from ai-research.md)
   - Allow parallel processing unlike RNNs
   - Can focus on any part of the sequence

2. **Positional encoding** (from attention-mechanisms.md)  
   - Solves the position problem without recurrence
   - Your note mentions this was the "breakthrough insight"

Sources: 📄 ai-research.md, 🔗 attention-mechanisms.md
```

### **2. 🧭 NAVIGATE Engine - "What should I read next?"**

**Philosophy:** Help users discover and explore their knowledge. Find forgotten content and suggest connections.

**Core Behaviors:**
- Find notes user forgot they wrote
- Suggest missing connections between notes
- Identify related content by meaning, not just keywords
- Recommend reading paths and exploration routes

**Sub-capabilities:**
- **search**: Find specific content with semantic + keyword search
- **discover**: Rediscover forgotten connections and insights
- **recommend**: Suggest personalized reading paths
- **browse**: Explore vault structure and organization

**Example Query:** *"I feel like I've written about learning strategies before but can't remember what I concluded"*

**Response Format:**
```
🔮 Rediscovered Insights:

You actually wrote extensively about learning strategies! Here's what I found:

📋 **Forgotten Conclusions:**
- In "study-methods.md", you concluded spaced repetition works best for you
- In "productivity.md", you noted morning learning sessions are 3x more effective

🔗 **Hidden Connections:**  
- Your note on "flow states" mentions the same focus techniques
- You independently discovered the Feynman technique in 2 different notes

🎯 **Recommended Next Steps:**
1. **multihead-attention.md** - Natural next step after attention basics
2. **vision-transformers.md** - You love cross-domain applications
```

### **3. ✏️ TRANSFORM Engine - "Make this better"**

**Philosophy:** Intelligently edit and restructure content while preserving the user's voice and important elements.

**Core Behaviors:**
- Always preserve [[links]] and #tags exactly
- Maintain user's voice and style
- Show preview before applying changes
- Support rewrite, restructure, format, and improve operations

**Sub-capabilities:**
- **rewrite**: Rephrase content for clarity or different audience
- **restructure**: Reorganize information with better flow
- **format**: Apply markdown formatting and styling
- **improve**: General content enhancement and cleanup

**Example Query:** *"Make this explanation of attention mechanisms clearer for beginners"*

**Response Format:**
```
✏️ **Improved Version:**

## Attention Mechanisms in AI (Beginner-Friendly)

**What it is:** Think of attention like a spotlight in a dark room...
[Clear, restructured content with preserved [[links]] and #tags]

**Key Changes Made:**
- Added beginner-friendly analogies
- Simplified technical jargon  
- Improved paragraph flow
- Preserved all your [[wikilinks]] and #machinelearning tags
```

### **4. 🔍 SYNTHESIZE Engine - "What patterns emerge?"**

**Philosophy:** Extract patterns and generate insights across multiple notes that the user hasn't explicitly connected.

**Core Behaviors:**
- Find patterns across time periods
- Identify recurring themes and contradictions  
- Spot evolving thinking patterns
- Generate insights user hasn't explicitly noted

**Sub-capabilities:**
- **summarize**: Distill key points across multiple notes
- **analyze**: Extract hidden patterns and themes
- **compare**: Contrast ideas and identify contradictions
- **timeline**: Show how thinking evolved over time

**Example Query:** *"What patterns emerge from my productivity experiments over the past year?"*

**Response Format:**
```
🔍 **Productivity Patterns Analysis**

**📈 Evolution Over Time:**
- Jan-Mar 2024: Focus on time-blocking (initial enthusiasm)
- Apr-Jun 2024: Shift to energy management (burnout period)
- Jul-Sep 2024: Integration of both approaches (maturation)

**🎯 Recurring Themes:**
1. **Morning advantage** - mentioned in 8 different experiments
2. **Context switching costs** - consistently your biggest challenge
3. **External accountability** - works when you actually use it

**⚡ Key Insight You Haven't Explicitly Noted:**
Your most successful periods combine morning deep work with afternoon social accountability - but you've never tried intentionally scheduling both together.
```

### **5. 🔧 MAINTAIN Engine - "Fix my vault"**

**Philosophy:** Keep vault healthy and well-organized. Identify issues proactively without forcing solutions.

**Core Behaviors:**
- Identify issues without user asking
- Suggest fixes, don't force them
- Preserve user's organizational system
- Batch similar fixes for efficiency

**Sub-capabilities:**
- **health_check**: Comprehensive vault health analysis
- **fix_links**: Repair broken [[wikilinks]] and references
- **organize**: Structural cleanup and organization suggestions
- **find_duplicates**: Identify redundant or similar content

**Example Query:** *"Check my vault health and suggest improvements"*

**Response Format:**
```
🔧 **Vault Health Report**

**Overall Status:** 🟡 Good (7.2/10)

**📊 Health Metrics:**
- 847 notes total
- 23 broken [[links]] found
- 5 orphaned notes (no incoming links)
- 3 potential duplicates detected

**🔧 Suggested Improvements:**
1. **Fix broken links** (Priority: High)
   - [[transformer-attention]] → Should be [[attention-mechanisms]]  
   - [[daily-2024-13-01]] → Invalid date format

2. **Organize loose notes** (Priority: Medium)
   - 12 notes in root could move to appropriate folders
   - Consider creating an index for your AI research cluster

3. **Merge duplicates** (Priority: Low)
   - "attention-mechanisms.md" and "attention-models.md" have 85% overlap
```

## 🌟 **Key Innovations**

### **1. @Mention System**
```python
# Highest priority context - user explicitly wants this content
mentioned_files = ["research/transformers.md", "notes/ai-conclusions.md"] 
mentioned_folders = ["research/papers/"]
# Gets 60% of token budget automatically
```
When you use `@filename.md` or `@folder/` in your queries, those files get **highest priority** in the context pyramid, ensuring the AI focuses on exactly what you want.

### **2. Configurable Everything**
```yaml
# configs/routing.yaml
intelligence:
  use_chat_default: true  # Use single model for all operations
  engines:
    understand:
      temperature: 0.3    # Precise for Q&A
    transform: 
      temperature: 0.7    # Creative for editing
  context:
    max_tokens: 8000
    token_limits:
      navigate: 9600      # 20% more for discovery
      synthesize: 12000   # 50% more for pattern finding
```

### **3. No Fallback Architecture**
```python
# Your system explicitly validates config - no silent defaults
if 'temperature' not in self.engine_config:
    raise ValueError(f"temperature not configured for engine {self.engine_name}")
```
Every parameter must be explicitly configured. No hidden defaults that might cause unexpected behavior.

### **4. Context Validation & Quality Assessment**
```python
def _estimate_confidence(self, context_pyramid, intent, response_length):
    base_confidence = intent.confidence
    # Boost for rich context, penalize for truncation
    context_boost = len(context_pyramid.items) * 0.05 
    if context_pyramid.truncated:
        context_boost -= 0.1
```
Smart confidence scoring based on context quality, ensuring you know when responses are well-grounded vs. uncertain.

### **5. Vault-Native Understanding**
- **[[Wikilinks]]**: Follows your note connections automatically
- **#Tags**: Understands your categorization system  
- **@Mentions**: Direct file/folder references get priority
- **Temporal Context**: Considers when notes were created/modified
- **Folder Structure**: Respects your organizational system

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
│   ├── intelligence/            # Context-Aware Intelligence System
│   │   ├── __init__.py
│   │   ├── intent_detector.py   # Intent routing with pattern + LLM
│   │   ├── context_engine.py    # Context pyramid construction  
│   │   ├── prompt_manager.py    # Configurable Jinja2 templates
│   │   └── engines/             # Five core capability engines
│   │       ├── base_engine.py   # Shared engine functionality
│   │       ├── understand_engine.py    # Q&A with vault grounding
│   │       ├── navigate_engine.py      # Discovery and exploration
│   │       ├── transform_engine.py     # Content editing
│   │       ├── synthesize_engine.py    # Pattern extraction  
│   │       └── maintain_engine.py      # Vault health
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
│   ├── vault/                   # Enhanced file management
│   │   ├── __init__.py
│   │   ├── file_queue_manager.py   # Thread-safe queue with locking
│   │   └── file_watcher.py         # Real-time file change detection  
│   └── workflows/               # LangChain workflow implementations
│       ├── __init__.py
│       └── qa_workflow.py       # Question-answering pipeline
│
├── configs/                     # Configuration files
│   ├── routing.yaml            # Model routing and intelligence settings
│   └── prompts.yaml            # Jinja2 prompt templates
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

## 🚀 **Why This Architecture Is Powerful**

1. **🧠 Intent-Aware**: Understands *why* you're asking, not just *what*
2. **🎯 Context-Smart**: Builds relevance pyramids instead of random retrieval  
3. **🔧 Modular**: Each capability is specialized and configurable
4. **📚 Vault-Native**: Understands your note structure (links, tags, @mentions)
5. **📈 Adaptive**: Learns from your patterns and adjusts accordingly

**The Result:** An AI that feels like it **actually understands your vault** rather than just searching through it. It's like having a research assistant who has read everything you've ever written and knows how you think.

### **Complete Request Flow Example**

**User:** *"What did I conclude about transformers in my AI research? @research/papers"*

1. **Intent Detection:**
   - Pattern: "what" + "conclude" → UNDERSTAND intent
   - Sub-capability: "question_answer"
   - Confidence: 0.8

2. **Context Building:**
   - Layer 0: `@research/papers` folder gets highest priority (60% tokens)
   - Layer 3: Semantic search for "transformers" + "AI research"
   - Layer 4: Recent notes in case of new insights

3. **Engine Processing:**
   - Routes to `UnderstandEngine.question_answer()`
   - Uses context pyramid to generate answer
   - Cites specific sources from context

4. **Response:**
   - Direct answer with vault citations
   - Confidence score based on context quality
   - Suggested actions: "Explore connections", "Find related papers"

---

**Built for the NotebookLocal RAG System**
- **Context-Aware Intelligence** with 5 specialized capability engines
- **Advanced Intent Routing** with pattern + LLM classification
- **Vault-Native Understanding** of your knowledge structure
- **Real-time File Management** with queue-based processing
- **Configurable Architecture** with no hidden defaults

For integration with the Obsidian plugin, see: [📝 Plugin README](../notebook-local/README.md)