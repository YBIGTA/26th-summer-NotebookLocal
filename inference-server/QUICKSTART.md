# 🚀 QuickStart Guide

Get your hybrid PostgreSQL + Weaviate RAG system running in 3 steps!

## ⚡ 3-Step Setup

### 1. Start Databases
```bash
# Start PostgreSQL + Weaviate with Docker
./setup_docker.sh
```

### 2. Configure API Keys
```bash
# Edit environment variables
nano .env

# Add your OpenAI API key:
OPENAI_API_KEY=your_actual_api_key_here
```

### 3. Start Server
```bash
# Install dependencies with UV (much faster!)
uv sync

# Start the server (auto-creates database tables)
python start_server.py
```

## 🎉 That's It!

Your server is now running at:
- **API**: http://localhost:8000
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

✅ **Hybrid Search**: BM25 + semantic search via Weaviate  
✅ **Metadata Management**: Rich document info in PostgreSQL  
✅ **Auto-initialization**: Tables created automatically  
✅ **API Endpoints**: Full REST API for document processing  
✅ **Obsidian Integration**: Ready for Obsidian plugin  
✅ **Citation Support**: Page numbers and source tracking  

## 🆘 Need Help?

- **Setup Issues**: Check [DATABASE_SETUP.md](DATABASE_SETUP.md)
- **API Issues**: Visit http://localhost:8000/docs for Swagger UI
- **Database Issues**: See troubleshooting in DATABASE_SETUP.md

Happy coding! 🎯