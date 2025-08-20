# NotebookLocal Inference Server

A hybrid PostgreSQL + Weaviate RAG system with modular LLM routing and local model support.

## 🚀 Features

- **🗄️ Hybrid Database**: PostgreSQL metadata + Weaviate vectors
- **🔍 Hybrid Search**: BM25 + semantic search with metadata filtering  
- **🤖 Modular LLM**: OpenAI, Anthropic, and local model support
- **⚡ VLLM Ready**: Optimized for local model inference
- **🇰🇷 Korean PDFs**: Advanced PyMuPDF integration
- **🐳 Docker Setup**: One-command deployment

## 📦 Quick Start

```bash
# 1. Run unified setup (installs UV, starts Docker, installs dependencies)
./setup_local_dev.sh

# 2. Configure API keys
nano .env  # Add your OPENAI_API_KEY

# 3. Start server
python start_server.py
```

## 🔌 API Endpoints

- **Docs**: http://localhost:8000/docs
- **Process PDF**: `POST /api/v1/process`
- **Ask Question**: `POST /api/v1/ask`
- **Obsidian Chat**: `POST /api/v1/obsidian/chat`
- **Search**: `POST /api/v1/obsidian/search`

## 🛠️ Local Model Development

```bash
# Add VLLM for local inference
uv add vllm

# Add specific models
uv add transformers accelerate bitsandbytes

# Development setup
./setup_local_dev.sh
```

## 🏗️ Architecture

```
PostgreSQL (metadata) ←→ Weaviate (vectors)
       ↓                     ↓
   Documents               Embeddings
   Chunks                 Hybrid Search
   Tags, Citations        BM25 + Semantic
```

## 📂 Project Structure

```
inference-server/
├── src/
│   ├── database/           # PostgreSQL models
│   ├── storage/           # Hybrid storage coordinator  
│   ├── workflows/         # Document & QA workflows
│   ├── processors/        # PDF, text, embeddings
│   └── llm/              # Modular LLM routing
├── api/                  # FastAPI routes
├── docker-compose.yml    # Database setup
└── pyproject.toml       # UV dependencies
```

## 🔧 Configuration

Edit `.env` file:
```bash
DATABASE_URL=postgresql://inference_user:password@localhost:5432/inference_db
WEAVIATE_URL=http://localhost:8080
OPENAI_API_KEY=your_key_here
```

## 🩺 Troubleshooting

```bash
# Check services
docker-compose ps

# View logs  
docker-compose logs

# Test connections
curl http://localhost:8080/v1/.well-known/live  # Weaviate
psql $DATABASE_URL -c "SELECT 1"               # PostgreSQL
```

For detailed setup instructions, see [QUICKSTART.md](QUICKSTART.md) and [DATABASE_SETUP.md](DATABASE_SETUP.md).