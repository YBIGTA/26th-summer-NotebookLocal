# 🚀 QuickStart Guide

Get your comprehensive PDF processing and RAG system running in 3 steps!

## ⚡ 3-Step Setup

### 1. Run Setup Script
```bash
# One script does everything: UV install, Docker setup, dependencies
./setup_local_dev.sh
```

### 2. Configure Environment
```bash
# Copy environment template
cp .env.example .env

# Edit environment variables
nano .env

# Add your OpenAI API key:
OPENAI_API_KEY=your_actual_api_key_here

# Optional: Enable debug logging for troubleshooting
DEBUG_MODE=true
LOG_API_REQUESTS=true
LOG_DATABASE_OPS=true
LOG_PROCESSING_DETAILS=true
```

### 3. Start Server
```bash
# Start the server (auto-creates database tables)
python start_server.py
```

## 🎉 That's It!

Your server is now running at:
- **API**: http://localhost:8000/docs (Swagger UI)
- **Server**: http://localhost:8000
- **PostgreSQL**: localhost:5432
- **Weaviate**: http://localhost:8080

## 🧪 Test It

### Upload a PDF
```bash
curl -X POST "http://localhost:8000/api/v1/process" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@your_document.pdf"
```

### Ask a Question
```bash
curl -X POST "http://localhost:8000/api/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is this document about?"}'
```

### Check Database
```bash
# See your documents
docker-compose exec postgres psql -U inference_user -d inference_db -c "SELECT title, ingested_at FROM documents;"

# Check Weaviate
curl http://localhost:8080/v1/schema
```

## 🔧 Useful Commands

```bash
# Stop everything
docker-compose down

# Restart databases
docker-compose restart

# View logs
docker-compose logs

# Connect to database
docker-compose exec postgres psql -U inference_user -d inference_db
```

## 📚 What You Get

✅ **Dual Text Extraction**: Direct PDF text + AI vision for images/diagrams  
✅ **Hybrid Storage**: PostgreSQL metadata + Weaviate vector search  
✅ **Advanced Search**: BM25 + semantic search with metadata filtering  
✅ **Multi-LLM Support**: OpenAI, Anthropic, and local model routing  
✅ **Korean PDF Support**: Advanced PyMuPDF integration  
✅ **Unified Logging**: Comprehensive monitoring and debugging  
✅ **API Endpoints**: Full REST API + Obsidian plugin integration  
✅ **Auto-initialization**: Tables and schemas created automatically  

## 🔍 Performance Monitoring

With debug logging enabled, you'll see:
```
🚀 API REQUEST: OpenAI.vision
📥 API RESPONSE: OpenAI.vision (2.34s)
🗄️ DB: CREATE documents  
⏱️ START: Process 5 images
✅ SUCCESS: Process 5 images (12.45s)
```

This helps you identify performance bottlenecks (like slow OpenAI Vision API calls).

## 🆘 Need Help?

- **Setup Issues**: Check [DATABASE_SETUP.md](DATABASE_SETUP.md)
- **API Issues**: Visit http://localhost:8000/docs for Swagger UI  
- **Performance Issues**: Enable debug logging and see [MONITORING_GUIDE.md](MONITORING_GUIDE.md)
- **Database Issues**: See troubleshooting in DATABASE_SETUP.md

Happy coding! 🎯