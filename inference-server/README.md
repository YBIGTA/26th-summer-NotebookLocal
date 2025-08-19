# Inference Server

The AI processing backend for the RAG Search Pipeline. This FastAPI server handles document processing, embedding generation, vector storage, and provides Q&A capabilities through RESTful API endpoints.

## 🚀 Features

- **🇰🇷 Korean PDF Support**: Advanced PyMuPDF integration for Asian fonts
- **📊 Progress Tracking**: Real-time upload progress for multiple files
- **🔄 Streaming Responses**: Real-time LLM response streaming
- **🗃️ Vector Storage**: Weaviate integration with fallback to simple storage
- **🎯 RAG Pipeline**: Complete retrieval-augmented generation workflow
- **📝 Auto Documentation**: OpenAPI/Swagger documentation
- **🌐 Web Interface**: Built-in web UI for document management

## 📦 Installation & Setup

### Quick Setup (Recommended)

```bash
# Navigate to inference server directory
cd inference-server/

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Run automated setup
python setup.py
```

The setup script will:
- Install all dependencies
- Check environment configuration
- Run basic functionality tests
- Guide you through next steps

### Manual Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# Start server
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

## 🔧 Configuration

### Environment Variables (.env)

```bash
# OpenAI Configuration (Required)
OPENAI_API_KEY=your_openai_api_key_here

# Weaviate Configuration (Optional)
WEAVIATE_URL=http://localhost:8080
WEAVIATE_API_KEY=your_weaviate_api_key_here
```

### Server Configuration (config.py)

```python
# Model Settings
LLM_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-large" 
VISION_MODEL = "gpt-4o-mini"

# Processing Settings
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
MAX_TOKENS = 4000

# Vector Store Settings
COLLECTION_NAME = "lecture_documents"
```

## 🔌 API Endpoints

### Core Endpoints

```http
# Health Check
GET /api/v1/health

# Document Processing
POST /api/v1/process
Content-Type: multipart/form-data
Body: file (PDF)

# Basic Q&A
POST /api/v1/ask
Content-Type: application/json
Body: {"question": "What are the main topics?"}
```

### Obsidian Plugin Endpoints

```http
# Chat with Context
POST /api/v1/obsidian/chat
Content-Type: application/json
Body: {
  "message": "Explain the concept",
  "chat_id": "session_123",
  "context": {"file": "document.pdf"},
  "stream": false
}

# Streaming Chat
POST /api/v1/obsidian/chat/stream
Content-Type: application/json
Body: {
  "message": "Explain the concept",
  "stream": true
}

# Document Search
POST /api/v1/obsidian/search
Content-Type: application/json
Body: {
  "query": "machine learning",
  "limit": 10,
  "similarity_threshold": 0.7
}

# Document Management
GET /api/v1/obsidian/documents
DELETE /api/v1/obsidian/documents/{document_id}

# Index Management
GET /api/v1/obsidian/index/status
POST /api/v1/obsidian/index/rebuild
```

## 📚 API Documentation

### Interactive Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Example Usage

**Upload Document**:
```bash
curl -X POST "http://localhost:8000/api/v1/process" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf"
```

**Ask Question**:
```bash
curl -X POST "http://localhost:8000/api/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the main topics discussed?"}'
```

**Check Health**:
```bash
curl "http://localhost:8000/api/v1/health"
```

## 🏗️ Architecture

### Project Structure

```
inference-server/
├── api/                    # FastAPI application
│   ├── main.py            # FastAPI app entry point
│   └── routes.py          # API endpoints
├── src/                   # Core RAG pipeline
│   ├── main.py            # LectureProcessor orchestration
│   ├── processors/        # Document processing modules
│   │   ├── pdf_processor.py    # Korean PDF support
│   │   ├── image_processor.py  # GPT-4V image descriptions
│   │   ├── text_processor.py   # Text chunking
│   │   └── embedder.py         # OpenAI embeddings
│   ├── storage/           # Vector storage implementations
│   │   └── vector_store.py     # Weaviate + simple stores
│   ├── workflows/         # LangGraph workflow definitions
│   │   ├── document_workflow.py
│   │   └── qa_workflow.py
│   └── utils/             # Utility functions
│       ├── logger.py
│       └── helpers.py
├── config.py              # Configuration with .env loading
├── requirements.txt       # Python dependencies
└── setup.py              # Automated setup script
```

### Processing Pipeline

1. **Document Upload** → PDF validation and temporary storage
2. **Content Extraction** → Text + images using PyMuPDF (Korean support)
3. **Image Processing** → GPT-4V descriptions for diagrams/charts
4. **Text Chunking** → Semantic chunking with overlap
5. **Embedding Generation** → OpenAI text-embedding-3-large
6. **Vector Storage** → Weaviate or simple vector store
7. **Index Update** → Real-time search index updates

### Q&A Pipeline

1. **Query Processing** → Input validation and preprocessing
2. **Vector Search** → Similarity search in vector store
3. **Context Assembly** → Combine relevant chunks
4. **LLM Generation** → GPT-4o-mini with retrieved context
5. **Response Streaming** → Real-time response delivery

## 🇰🇷 Korean PDF Support

### Enhanced Font Handling

The server uses **PyMuPDF** instead of pdfplumber for superior Korean font support:

```python
# Advanced Korean PDF processing
def _extract_with_pymupdf(self, pdf_path: str):
    doc = fitz.open(pdf_path)
    try:
        for page_num in range(doc.page_count):
            page = doc[page_num]
            # Better Unicode support for Korean text
            text = page.get_text()
            text_parts.append(text)
    finally:
        doc.close()
```

### Font Warning Suppression

Automatically suppresses font-related warnings:
```python
# Suppress font warnings for Korean PDFs
warnings.filterwarnings("ignore", message=".*FontBBox.*")
warnings.filterwarnings("ignore", message=".*cannot be parsed as 4 floats.*")
```

### Fallback Handling

Graceful fallback from PyMuPDF to pdfplumber if needed:
```python
# Try PyMuPDF first (best for Korean fonts)
if HAS_PYMUPDF:
    try:
        return self._extract_with_pymupdf(pdf_path)
    except Exception as e:
        logging.warning(f"PyMuPDF failed: {e}, falling back")

# Fallback to pdfplumber with error handling
return self._extract_with_pdfplumber(pdf_path)
```

## 🌐 Server Interface

The inference server provides API-only access for client applications. The primary interface is through:

- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **API Info**: http://localhost:8000/api (basic server information)
- **Health Check**: http://localhost:8000/api/v1/health

For user interface, use the Obsidian plugin or other client applications that communicate with these API endpoints.

## 🛠️ Development

### Running in Development

```bash
# Start with auto-reload
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# With debug logging
uvicorn api.main:app --reload --log-level debug

# Custom host/port
uvicorn api.main:app --host 127.0.0.1 --port 8080
```

### Environment Setup

```bash
# Development dependencies
pip install -r requirements.txt
pip install pytest black flake8 mypy

# Run tests
pytest

# Code formatting
black .

# Type checking
mypy src/
```

### Adding New Endpoints

1. **Define Models** in `api/routes.py`:
```python
class CustomRequest(BaseModel):
    field: str

class CustomResponse(BaseModel):
    result: str
```

2. **Add Endpoint**:
```python
@router.post("/custom", response_model=CustomResponse)
async def custom_endpoint(request: CustomRequest):
    result = process_custom_request(request.field)
    return CustomResponse(result=result)
```

3. **Update Documentation**: OpenAPI docs update automatically

## 🚀 Deployment

### Production Setup

```bash
# Install production dependencies
pip install gunicorn

# Run with Gunicorn
gunicorn api.main:app -w 4 -k uvicorn.workers.UvicornWorker

# Or with PM2
pm2 start "uvicorn api.main:app --host 0.0.0.0 --port 8000" --name rag-server
```

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables for Production

```bash
# Production settings
OPENAI_API_KEY=your_production_key
WEAVIATE_URL=https://your-weaviate-cluster.weaviate.network
WEAVIATE_API_KEY=your_production_weaviate_key

# Optional: Redis for caching
REDIS_URL=redis://localhost:6379

# Optional: Database for metadata
DATABASE_URL=postgresql://user:pass@localhost/ragdb
```

## 🔍 Monitoring & Debugging

### Health Checks

```bash
# Basic health check
curl http://localhost:8000/api/v1/health

# Detailed status
curl http://localhost:8000/api/v1/obsidian/index/status
```

### Logging

Configure logging in `src/utils/logger.py`:
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Performance Monitoring

Monitor key metrics:
- Response times for API endpoints
- Document processing success rates
- Vector search performance
- Memory and CPU usage

## 🤝 Contributing

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/new-endpoint`
3. **Make changes** and add tests
4. **Run tests**: `pytest`
5. **Submit pull request**

### Code Style

- Follow PEP 8 for Python code
- Use type hints for all functions
- Add docstrings for public methods
- Write tests for new functionality

---

## 📄 License

This project maintains the same license as the original Obsidian Copilot plugin.

---

**🎉 Happy coding with your modular RAG server!**