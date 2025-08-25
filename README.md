# NotebookLocal - Intelligent Vault Assistant

A **context-aware AI assistant** for Obsidian vaults that understands your notes and responds naturally. Built with a **service-oriented architecture** combining FastAPI intelligence backend with Obsidian plugin frontend, featuring real-time document processing and natural language interaction.

**Core Philosophy**: Transform knowledge work from command-driven to conversation-driven through intelligent document understanding and natural language processing.

## 🧠 Philosophy: Context-Aware Intelligence

Transform your vault interaction from command-driven to conversation-driven:

- **Natural Language**: "What did I conclude about this topic?" instead of `/search topic`
- **Intelligent Context**: System automatically builds relevance-ranked context pyramids
- **Smart @Mentions**: `@file1.md,file2.md` or `@folder/` for precise targeting
- **Intent Understanding**: System detects whether you want to UNDERSTAND, NAVIGATE, TRANSFORM, SYNTHESIZE, or MAINTAIN

## 🏗️ Intelligence Architecture

```mermaid
graph TB
    subgraph "🧠 Intelligence System"
        UI[Natural Language Input]
        ID[Intent Detector]
        CR[Capability Router]
        CE[Context Engine]
        
        subgraph "5 Core Capabilities"
            UE[UNDERSTAND Engine]
            NE[NAVIGATE Engine] 
            TE[TRANSFORM Engine]
            SE[SYNTHESIZE Engine]
            ME[MAINTAIN Engine]
        end
    end
    
    subgraph "📚 Knowledge Base"
        PG[(PostgreSQL)]
        VDB[Vector Store]
        FILES[Vault Files]
    end
    
    UI --> ID
    ID --> CR
    CR --> CE
    CE --> PG
    CE --> VDB
    CR --> UE
    CR --> NE
    CR --> TE
    CR --> SE
    CR --> ME
    
    FILES --> PG
```

## 🎯 Core Capabilities

### 🤔 **UNDERSTAND**
Answer questions using your vault as ground truth
```
What did I conclude about this topic?
Explain the key concepts from my research
@meeting-notes.md What were the action items?
```

### 🗺️ **NAVIGATE** 
Find and discover content across your vault
```
Find everything about API design
Show me notes related to machine learning
@research/ What patterns do you see?
```

### ✨ **TRANSFORM**
Intelligently edit and improve your content
```
Make this note clearer and more structured
Improve the flow of this argument
@draft.md Rewrite this for a technical audience
```

### 🔄 **SYNTHESIZE**
Extract insights and patterns across multiple notes
```
Summarize my research findings this month
What themes emerge from my project notes?
@notes1.md,notes2.md,notes3.md Compare these approaches
```

### 🔧 **MAINTAIN**
Keep your vault healthy and organized
```
Check for broken links in my vault
Find duplicate content across notes
Suggest better organization for my files
```

## 🎮 Natural Usage Examples

### **Instead of commands, just ask naturally:**

**Old way (commands):**
```
/rag-enable
/rag-scope selected  
@meeting-notes.md @project-docs/
/search "key insights"
```

**New way (natural + @mentions):**
```
@meeting-notes.md @project-docs/ What are the key insights from our recent discussions?
```

**The system automatically:**
1. **Understands** your intent (SYNTHESIZE capability)
2. **Gathers** relevant context from mentioned files + related content
3. **Processes** using the appropriate engine
4. **Executes** and provides insights with source citations

## 📁 Service Architecture Overview

```
26th-summer-NotebookLocal/
├── README.md                          # Service overview & philosophy
├── PIPELINE.md                        # Complete technical pipeline
├── inference-server/                  # 🐍 Python FastAPI Backend Service
│   ├── src/intelligence/             # 🧠 Intelligence Processing Core
│   │   ├── context_engine.py         # Context pyramid builder
│   │   ├── intent_detector.py        # Natural language → intent routing
│   │   ├── capability_router.py      # Route to capability engines
│   │   └── intelligence_service.py   # Main orchestration service
│   ├── src/services/                 # 🔧 Business Logic Services
│   │   ├── document_processing_service.py  # Document workflow orchestration
│   │   ├── processing_models.py      # Data models & types
│   │   └── background_processor.py   # Async processing worker
│   ├── src/workflows/                # 📋 Processing Workflows
│   │   └── document_workflow.py      # LangGraph document pipeline
│   ├── src/processors/              # ⚙️  Content Processors
│   │   ├── pdf_processor.py          # PDF text/image extraction
│   │   ├── image_processor.py        # Vision model descriptions
│   │   ├── text_processor.py         # Chunking & tokenization
│   │   └── embedder.py               # Vector embedding generation
│   ├── src/storage/                 # 💾 Data Storage Layer
│   │   ├── hybrid_store.py          # PostgreSQL + Vector hybrid
│   │   └── vector_store.py          # Weaviate/vector operations
│   ├── src/vault/                   # 📁 File Management Services
│   │   ├── file_manager.py          # File metadata management
│   │   ├── file_watcher.py          # Real-time change detection
│   │   └── file_queue_manager.py    # Processing queue management
│   ├── api/                         # 🌐 API Gateway Layer
│   │   ├── intelligence_routes.py   # Intelligence endpoints
│   │   ├── document_routes.py       # Document processing API
│   │   ├── vault_routes.py         # File management API
│   │   └── main.py                 # FastAPI application
│   └── src/llm/core/               # 🤖 LLM Integration Layer
│       ├── router.py               # Multi-model routing
│       └── providers/              # Model provider implementations
└── notebook-local/                 # 🧩 Obsidian Plugin (React Components)
    ├── src/intelligence/           # 🧠 Plugin Intelligence Controller
    │   └── IntelligenceController.ts # Natural language processing
    ├── src/components/             # 🎨 React UI Components for Obsidian
    │   ├── NotebookLocalView.tsx   # Main tabbed interface (Obsidian view)
    │   ├── FileManagerView.tsx     # File tree & processing controls
    │   ├── EnhancedChatInput.tsx   # Natural language input
    │   └── IntentIndicator.tsx     # Real-time intent feedback
    ├── src/api/                    # 🔗 API Client Layer
    │   └── ApiClient-clean.ts      # HTTP client with 14+ endpoints
    ├── src/settings/               # ⚙️  Plugin Configuration Management
    │   └── model-clean.ts          # Settings & state management
    └── main.ts                     # Obsidian Plugin Entry Point
```

### 🏛️ **Service Design Philosophy**

**1. Separation of Concerns**
- **Backend Service**: Pure intelligence processing, document workflows, data management
- **Obsidian Plugin**: User experience, real-time UI, vault integration within Obsidian
- **Clear API Boundaries**: RESTful endpoints with comprehensive error handling

**2. Service-Oriented Architecture** 
- **Microservice-like Components**: Each service handles specific business logic
- **Event-driven Processing**: File changes trigger async document workflows
- **Horizontal Scalability**: Services can be independently scaled

**3. Modern Development Stack**
- **Backend**: FastAPI + PostgreSQL + LangGraph + Vector Search
- **Obsidian Plugin**: React + TypeScript + Tailwind CSS + Obsidian API
- **Infrastructure**: Docker-ready, environment-configurable

**4. Production-Ready Features**
- **Comprehensive Logging**: Full observability across all services
- **Error Handling**: Graceful degradation and recovery
- **Background Processing**: Non-blocking document workflows
- **Real-time Updates**: WebSocket-like experience through polling

## 🚀 Quick Start

### Prerequisites
- **Python 3.8+** with pip
- **Node.js 16+** with npm  
- **PostgreSQL 12+** 
- **Obsidian** with community plugins enabled

### Installation

1. **Clone and setup backend:**
```bash
git clone <repository-url>
cd 26th-summer-NotebookLocal/inference-server
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Database setup
createdb notebooklocal
alembic upgrade head
```

2. **Configure environment:**
```bash
# Create .env file
cat > .env << EOF
DATABASE_URL=postgresql://user:password@localhost/notebooklocal
OPENAI_API_KEY=your-openai-key
MODEL_PROVIDER=openai
EOF
```

3. **Build and install plugin:**
```bash
cd ../notebook-local
npm install && npm run build
cp -r dist/* /path/to/vault/.obsidian/plugins/notebook-local/
```

4. **Start the system:**
```bash
# Start inference server
uvicorn src.main:app --host 0.0.0.0 --port 8000

# Enable plugin in Obsidian: Settings → Community plugins → "NotebookLocal"
```

## 🎯 How to Use

### **1. Just Start Talking**
Open NotebookLocal in Obsidian and ask naturally:
```
What are the main themes in my research?
Find notes about machine learning from last week
Make this paragraph clearer
```

### **2. Use @Mentions for Precision**
```
@important.md What did I conclude here?
@research/ Summarize the key findings
@file1.md,file2.md,file3.md Compare these approaches
```

### **3. Let the System Learn Your Intent**
The system automatically detects what you want:
- Questions → **UNDERSTAND** engine
- "Find" or "Show" → **NAVIGATE** engine  
- "Make" or "Improve" → **TRANSFORM** engine
- "Summarize" or "Compare" → **SYNTHESIZE** engine
- "Check" or "Fix" → **MAINTAIN** engine

## 📊 Technical Details

### **Context Pyramid System**
Files are ranked by relevance:
1. **Mentioned files** (@file.md) - Highest priority
2. **Current note** - High priority  
3. **Linked notes** - Medium-high priority
4. **Similar content** - Medium priority
5. **Recent files** - Temporal context
6. **Tagged content** - Shared topic context

### **API Endpoints**
- `POST /api/v1/intelligence/chat` - Main intelligence endpoint
- `GET /api/v1/intelligence/capabilities` - Available capabilities
- `POST /api/v1/intelligence/intent/detect` - Intent detection
- `POST /api/v1/vault/scan` - File processing

### **Database Integration**
- **PostgreSQL**: File metadata and processing status
- **Vector Store**: Semantic embeddings for content similarity
- **Real-time sync**: Obsidian file changes → automatic processing

## 🐛 Troubleshooting

**Plugin won't connect:**
- Verify inference server running on localhost:8000
- Check browser console for errors
- Test connection with the "Test Connection" button

**Files not found:**
- Ensure files are processed (Files tab shows status)
- Use exact file names in @mentions: `@filename.md`
- Check server logs for processing errors

**Responses seem off:**
- Verify current note path is detected correctly
- Try more specific @mentions to guide context
- Check Context tab to see what's included

## 🔬 Development

The system is built on **modular intelligence architecture**:

- **Easy capability expansion**: Add new engines for specific use cases
- **Context-aware processing**: Each capability gets optimized context
- **Natural language interface**: No command memorization needed
- **Precise control**: @mentions for when you need specificity

**Adding new capabilities:**
1. Create new engine in `inference-server/src/intelligence/engines/`
2. Add intent patterns to `intent_detector.py`
3. Register in `capability_router.py`

---

**🎓 Built for intelligent knowledge work**
- Context-aware responses using your vault as ground truth
- Natural conversation enhanced by precise @mentions when needed
- Automatic intent detection and routing to specialized engines
- Real-time file processing with PostgreSQL + vector storage integration

For detailed setup: [📡 Server README](./inference-server/README.md) • [📝 Plugin README](./notebook-local/README.md)