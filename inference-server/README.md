# NotebookLocal Inference Server

A comprehensive PDF processing and RAG system with hybrid storage, modular LLM routing, and advanced monitoring capabilities.

## 🚀 Features

- **🗄️ Hybrid Storage**: PostgreSQL metadata + Weaviate vector database
- **🔍 Advanced Search**: BM25 + semantic search with metadata filtering  
- **🤖 Multi-LLM Support**: OpenAI, Anthropic, and local model routing
- **📄 PDF Intelligence**: Dual text extraction (direct + AI vision)
- **🇰🇷 Korean Support**: Advanced PyMuPDF integration for Korean PDFs
- **📊 Unified Logging**: Comprehensive request/response monitoring
- **🐳 Docker Ready**: One-command database deployment

## 📦 Quick Start

```bash
# 1. Setup environment and databases
./setup_local_dev.sh

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Start server
python start_server.py
```

## 🏗️ Architecture Overview

### PDF Processing Pipeline
```
PDF Input → PDFProcessor → ImageProcessor → TextProcessor → HybridStore
    │            │              │              │             │
    │         Direct Text   AI Vision Text  Chunking     PostgreSQL
    │         Extraction    (OpenAI API)    Embedding     + Weaviate
    │
    └─── Images ────────────────┘
```

**Key Insights**:
1. **Dual Text Extraction**: 
   - **PDFProcessor**: Direct text from PDF (fast, accurate for typed text)
   - **ImageProcessor**: AI vision extracts text from images/diagrams (slower, uses OpenAI API)

2. **Smart Duplicate Detection**: 
   - Automatically detects duplicate PDFs using MD5 checksum
   - Skips reprocessing identical files, even with different filenames
   - Saves processing time and storage space

## 📂 Project Structure

```
inference-server/
├── 🔧 Configuration
│   ├── config.py              # Central configuration
│   ├── .env.example           # Environment template
│   └── configs/               # LLM adapter configs
│
├── 🗄️ Database Layer
│   ├── src/database/          # PostgreSQL models & connection
│   └── docker-compose.yml     # PostgreSQL + Weaviate setup
│
├── 📊 Storage Layer
│   └── src/storage/
│       ├── hybrid_store.py    # Coordinates PostgreSQL + Weaviate
│       └── vector_store.py    # Weaviate operations
│
├── ⚙️ Processing Layer
│   └── src/processors/
│       ├── pdf_processor.py   # PDF text + image extraction
│       ├── image_processor.py # AI vision text extraction (OpenAI)
│       ├── text_processor.py  # Text chunking
│       └── embedder.py        # Vector embeddings
│
├── 🔄 Workflow Layer
│   └── src/workflows/
│       ├── document_workflow.py # PDF processing pipeline
│       └── qa_workflow.py       # Question answering
│
├── 🤖 LLM Layer
│   └── src/llm/               # Modular LLM routing system
│       ├── core/router.py     # Route to different models
│       └── adapters/          # OpenAI, Anthropic, local models
│
├── 🌐 API Layer
│   └── api/
│       ├── main.py            # FastAPI app
│       └── routes.py          # All endpoints
│
├── 🔍 Monitoring & Debug
│   ├── src/utils/logger.py    # Unified logging system
│   └── tools/                 # Debug and inspection tools
│
└── 📚 Documentation
    ├── README.md              # This file
    ├── QUICKSTART.md          # Setup guide
    ├── DATABASE_SETUP.md      # Database configuration
    └── MONITORING_GUIDE.md    # Logging configuration
```

## ⚡ Key Features Explained

### 🔄 Smart Duplicate Detection

The system automatically prevents reprocessing identical PDFs:

**How it works:**
1. **File Checksum**: Calculates MD5 hash of uploaded file content
2. **Database Lookup**: Checks if checksum exists in PostgreSQL
3. **Smart Response**: If found, returns existing document info instead of reprocessing

**Benefits:**
- ⚡ **Performance**: Avoids redundant processing (saves minutes per duplicate)
- 💾 **Storage**: Prevents duplicate chunks and embeddings
- 🔍 **Fast Detection**: Database index makes lookup milliseconds

**Example Response:**
```json
{
  "doc_uid": "12345678-1234-5678-9012-123456789abc",
  "status": "exists",
  "chunks": 25,
  "images": 3
}
```

**What triggers duplicate detection:**
- ✅ Same file uploaded twice
- ✅ Same file with different filename  
- ✅ Identical content from different sources
- ❌ Modified files (treated as new documents)

### 📄 Page-Aware Processing

New architecture processes PDFs page-by-page for better context:

1. **Page Division**: Each PDF page processed individually
2. **Image Integration**: AI descriptions merged into page text before chunking
3. **Context Preservation**: Chunks maintain page number metadata
4. **Better Search**: Semantic search can locate content by page

## 🔌 API Endpoints

### Core Endpoints
- **📄 Process PDF**: `POST /api/v1/process` - Upload and process PDF files
- **❓ Ask Question**: `POST /api/v1/ask` - Query processed documents
- **🔍 Search**: `POST /api/v1/obsidian/search` - Semantic document search
- **📊 Health Check**: `GET /api/v1/health` - System status

### Obsidian Plugin Integration
- **💬 Chat**: `POST /api/v1/obsidian/chat` - RAG-enhanced chat
- **📋 Documents**: `GET /api/v1/obsidian/documents` - List processed files
- **🗑️ Delete**: `DELETE /api/v1/obsidian/documents/{id}` - Remove documents

### Debug Endpoints
- **🩺 Health Detail**: `GET /api/v1/debug/health-detailed` - Detailed system status
- **📊 DB Stats**: `GET /api/v1/debug/db-stats` - Database statistics

## ⚙️ Configuration

### Environment Variables (.env)
```bash
# Database Configuration
DATABASE_URL=postgresql://inference_user:password@localhost:5432/inference_db
WEAVIATE_URL=http://localhost:8080

# API Keys
OPENAI_API_KEY=your_openai_key_here

# Logging Configuration (for debugging)
DEBUG_MODE=false
LOG_API_REQUESTS=false
LOG_DATABASE_OPS=false
LOG_PROCESSING_DETAILS=false
```

### Enable Debug Logging
```bash
# Enable detailed logging for troubleshooting
DEBUG_MODE=true
LOG_API_REQUESTS=true
LOG_DATABASE_OPS=true
LOG_PROCESSING_DETAILS=true
```

## 🩺 Troubleshooting

### Performance Issues
- **Slow PDF processing**: Check OpenAI API rate limits and image count
- **Long delays**: Enable debug logging to see which step is slow
- The ImageProcessor makes OpenAI Vision API calls for every image - this is often the bottleneck

### Database Issues
```bash
# Check database status
docker-compose ps

# View database logs
docker-compose logs postgres weaviate

# Test connections
python tools/db_inspect.py
```

### Common Issues
- **Database connection**: Ensure Docker containers are running
- **Korean text issues**: Verify PyMuPDF installation and font support
- **API rate limits**: Monitor OpenAI usage in debug logs

For detailed instructions, see [QUICKSTART.md](QUICKSTART.md), [DATABASE_SETUP.md](DATABASE_SETUP.md), and [MONITORING_GUIDE.md](MONITORING_GUIDE.md).