# 🛠️ Debug and Development Tools

This directory contains utilities for debugging, testing, and inspecting the inference server. These tools help you monitor performance, identify bottlenecks, and troubleshoot issues.

## 🧰 Available Tools

### 🔧 `debug_tools.py` - API Testing & System Health
Comprehensive testing of the server's API endpoints and functionality with performance monitoring.

```bash
# Run complete system test (recommended)
python tools/debug_tools.py full

# Individual component tests
python tools/debug_tools.py health                    # Basic health check
python tools/debug_tools.py detailed-health           # Detailed system status
python tools/debug_tools.py db-stats                  # Database statistics
python tools/debug_tools.py upload test.pdf           # Test PDF upload with timing
python tools/debug_tools.py question "What is this?"  # Test Q&A functionality
```

**What you'll see:**
- ✅ API response times and status codes
- 📊 Processing performance metrics
- 🔍 Component health status
- ❌ Detailed error information if something fails

### 🗃️ `db_inspect.py` - Database Inspection & Management
Direct PostgreSQL database inspection with hybrid storage support.

```bash
# Database inspection
python tools/db_inspect.py stats               # Comprehensive database statistics
python tools/db_inspect.py documents           # List all processed documents
python tools/db_inspect.py chunks              # Show text chunks (default: 10)
python tools/db_inspect.py chunks 50           # Show specific number of chunks
python tools/db_inspect.py chunks DOC_UUID     # Show chunks for specific document
python tools/db_inspect.py search "keyword"    # Search through document content

# Database management (use with caution!)
python tools/db_inspect.py clear               # Clear all data from both databases
```

**What you'll see:**
- 📊 Document counts, chunk statistics, processing times
- 📄 Document titles, source types, ingestion dates
- 🔍 Full-text search results with document context
- 💾 PostgreSQL + Weaviate storage details

## 🚀 Usage Guidelines

### Development Workflow
1. **Environment Setup**: `./setup_local_dev.sh`
2. **Enable Debug Logging**: Add to `.env`:
   ```bash
   DEBUG_MODE=true
   LOG_API_REQUESTS=true
   LOG_DATABASE_OPS=true
   LOG_PROCESSING_DETAILS=true
   ```
3. **Start Server**: `python start_server.py`
4. **System Test**: `python tools/debug_tools.py full`
5. **Monitor Data**: `python tools/db_inspect.py stats`

### Performance Debugging
When you suspect performance issues (like long processing times):

1. **Enable full logging** in `.env`
2. **Process a test document**: `python tools/debug_tools.py upload test.pdf`
3. **Watch the server console** for timing information:
   ```
   ⏱️ START: Process 5 images
   🚀 API REQUEST: OpenAI.vision (2.34s each)
   ✅ SUCCESS: Process 5 images (12.45s total)
   ```
4. **Check database impact**: `python tools/db_inspect.py stats`

### Troubleshooting Common Issues
- **Slow processing**: Look for long OpenAI API calls in debug logs
- **Empty results**: Use `db_inspect.py documents` to verify storage
- **Connection issues**: Run `debug_tools.py detailed-health`
- **Database problems**: Check `docker-compose logs postgres weaviate`

### 🔍 Performance Monitoring
The unified logging system shows you exactly where time is spent:
- **PDF Extraction**: Direct text from PDF (fast)
- **Image Processing**: AI vision on images (slow, uses OpenAI API)
- **Database Operations**: Storage timing
- **API Calls**: OpenAI request/response times with token counts

### ⚠️ Safety Notes
- `db_inspect.py clear` will delete ALL data from both PostgreSQL and Weaviate
- API testing tools require the server to be running
- Database inspection works even when server is down
- Debug logging may expose sensitive information - disable in production

### 📊 Quick Health Check
```bash
# One-liner to test everything
python tools/debug_tools.py full && python tools/db_inspect.py stats
```

This gives you a complete picture of your system's health and performance!