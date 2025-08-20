# 🔍 Monitoring & Debugging Guide

This guide shows you how to monitor your inference server and see exactly what's happening at each step of the pipeline.

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Understanding the Logs](#understanding-the-logs)
3. [Testing Tools](#testing-tools)
4. [Database Inspection](#database-inspection)
5. [API Monitoring](#api-monitoring)
6. [Troubleshooting](#troubleshooting)

---

## 🚀 Quick Start

### Run a Complete System Test
```bash
# Test everything at once
python debug_tools.py full
```

This will check:
- ✅ Server health
- ✅ Database connectivity  
- ✅ PDF processing (if test.pdf exists)
- ✅ Question answering
- ✅ System components

### Check What's in Your Database
```bash
# See all documents and statistics
python db_inspect.py stats

# List all documents
python db_inspect.py documents

# Show recent chunks
python db_inspect.py chunks 10
```

---

## 📊 Understanding the Logs

### What You'll See in the Server Logs

When you upload a PDF, you'll see detailed step-by-step logging:

#### 1. API Request Logging
```
🌐 API REQUEST [a1b2c3d4]: /process - PDF upload started
   📁 Filename: test.pdf  
   📄 File size: 2547328 bytes
📥 [a1b2c3d4]: Reading uploaded file...
✅ [a1b2c3d4]: File read successfully - 2,547,328 bytes
💾 [a1b2c3d4]: Temporary file created: /tmp/tmp8x9y2z.pdf
```

#### 2. Document Processing Workflow
```
🚀 STARTING DOCUMENT PROCESSING WORKFLOW
📁 File: /tmp/tmp8x9y2z.pdf

🔍 STEP 1: Starting PDF extraction for: /tmp/tmp8x9y2z.pdf
📄 File size: 2.43 MB
✅ STEP 1 COMPLETED:
   📝 Text extracted: 15,847 characters
   🖼️  Images found: 3
   ⏱️  Time taken: 1.23s
```

#### 3. Text Processing & Chunking
```
⚙️  STEP 2: Starting text processing and image description
📝 Processing 15,847 characters into chunks
✂️  Created 12 text chunks (avg size: 1321 chars)
🖼️  Processing 3 images for descriptions
📝 Generated 3 image descriptions
✅ STEP 2 COMPLETED:
   📄 Text chunks: 12
   🖼️  Image descriptions: 3
   ⏱️  Time taken: 4.56s
```

#### 4. Embedding & Storage
```
💾 STEP 3: Starting embedding generation and storage
🔢 Total items to embed: 15 (12 chunks + 3 descriptions)
🗃️  Using hybrid storage (PostgreSQL + Weaviate)
📄 Document title: test
📁 File path: /tmp/tmp8x9y2z.pdf
✅ STEP 3 COMPLETED - Hybrid Storage:
   📄 Document ID: 550e8400-e29b-41d4-a716-446655440000
   💾 PostgreSQL chunks: 15
   🧠 Weaviate vectors: 15
   ⏱️  Time taken: 2.34s
```

#### 5. Final Results
```
🎉 WORKFLOW COMPLETED:
   ⏱️  Total time: 8.13s
   📊 Final result: {'chunks': 12, 'images': 3, 'status': 'success'}
🎉 API SUCCESS [a1b2c3d4]: Processing completed
   ⏱️  Total API time: 8.45s
```

### Error Logging

When something goes wrong, you'll see detailed error information:

```
❌ STEP 1 FAILED: PDF extraction error
   Error: [Errno 2] No such file or directory: '/tmp/missing.pdf'
   Traceback: 
   File "/path/to/pdf_processor.py", line 45, in extract
     with open(pdf_path, 'rb') as f:
   FileNotFoundError: [Errno 2] No such file or directory
```

---

## 🧪 Testing Tools

### 1. `debug_tools.py` - API Testing

#### Test Individual Components
```bash
# Check if server is running
python debug_tools.py health

# Get detailed system status
python debug_tools.py detailed-health

# Check database statistics
python debug_tools.py db-stats

# Upload and process a PDF
python debug_tools.py upload test.pdf

# Test question answering
python debug_tools.py question "What is the main topic?"

# Run all tests
python debug_tools.py full
```

#### Example Output
```
🔍 Testing server health...
✅ Health check: 200
   Response: {'status': 'healthy', 'timestamp': '2024-01-20T10:30:45'}

🔍 Testing PDF upload: test.pdf
   File size: 2.43 MB
📤 Uploading PDF...
✅ Upload successful in 8.45s:
   Filename: test.pdf
   Chunks: 12
   Images: 3
   Status: success
```

### 2. `db_inspect.py` - Database Investigation

#### Check What's Stored
```bash
# Overall statistics
python db_inspect.py stats

# List all documents
python db_inspect.py documents

# Show text chunks (first 10)
python db_inspect.py chunks 10

# Show chunks for specific document
python db_inspect.py chunks 550e8400-e29b-41d4-a716-446655440000

# Search for content
python db_inspect.py search "machine learning"
```

#### Example Database Stats Output
```
🔍 Database statistics...
📊 OVERALL STATS:
   Documents: 5
   Chunks: 67
   Avg chunks per doc: 13.4

📄 DOCUMENT TYPES:
   pdf: 5

🌍 LANGUAGES:
   auto: 5

📏 CHUNK SIZES:
   Min: 245 characters
   Max: 1,847 characters
   Average: 1,203 characters

⏰ RECENT DOCUMENTS:
   test.pdf (2024-01-20 10:30:45)
   manual.pdf (2024-01-20 09:15:22)
```

---

## 🌐 API Monitoring

### Debug Endpoints

Your server now has special debug endpoints for monitoring:

#### 1. Detailed Health Check
```bash
curl http://localhost:8000/api/v1/debug/health-detailed
```

Response shows status of each component:
```json
{
  "timestamp": "2024-01-20T10:30:45",
  "system_status": "healthy",
  "components": {
    "postgresql": {
      "status": "connected",
      "can_query": true,
      "sample_query_success": true
    },
    "vector_store": {
      "status": "available", 
      "type": "HybridStore"
    },
    "llm_router": {
      "status": "available",
      "adapters_count": 4
    }
  }
}
```

#### 2. Database Statistics
```bash
curl http://localhost:8000/api/v1/debug/db-stats
```

Get real-time database information:
```json
{
  "total_documents": 5,
  "total_chunks": 67,
  "documents_by_type": {"pdf": 5},
  "recent_documents": [
    {
      "title": "test.pdf",
      "source_type": "pdf", 
      "chunks": 12,
      "ingested_at": "2024-01-20T10:30:45"
    }
  ],
  "chunk_size_distribution": {
    "small": 1,
    "medium": 3,
    "large": 1
  }
}
```

---

## 🔧 Troubleshooting

### Common Issues & What to Look For

#### 1. PDF Processing Fails
**Look for in logs:**
```
❌ STEP 1 FAILED: PDF extraction error
```

**Quick check:**
```bash
python debug_tools.py upload your_file.pdf
```

#### 2. Database Connection Issues
**Look for in logs:**
```
❌ Database setup failed: No module named 'sqlalchemy'
```

**Quick check:**
```bash
python debug_tools.py detailed-health
python db_inspect.py stats
```

#### 3. Empty Results After Processing
**Look for in logs:**
```
⚠️  No text extracted from PDF!
⚠️  No content to embed - document appears empty
```

**Quick check:**
```bash
python db_inspect.py documents
python db_inspect.py chunks 5
```

#### 4. Question Answering Not Working
**Look for in logs:**
```
❌ Error in LLM generation: API key not found
```

**Quick check:**
```bash
python debug_tools.py question "test question"
curl http://localhost:8000/api/v1/debug/health-detailed
```

### Step-by-Step Debugging Process

1. **Check if server is running:**
   ```bash
   python debug_tools.py health
   ```

2. **Verify all components:**
   ```bash
   python debug_tools.py detailed-health
   ```

3. **Check database content:**
   ```bash
   python db_inspect.py stats
   ```

4. **Test document processing:**
   ```bash
   python debug_tools.py upload test.pdf
   ```

5. **Watch live logs:**
   - Keep your server terminal open
   - Watch the step-by-step processing logs
   - Look for ❌ error indicators

6. **Inspect results:**
   ```bash
   python db_inspect.py documents
   python db_inspect.py chunks 10
   ```

---

## 📈 Performance Monitoring

### What to Monitor

#### Processing Times
- **Step 1 (PDF extraction):** Usually 1-3s for small PDFs
- **Step 2 (Text processing):** 2-5s depending on content
- **Step 3 (Embedding/storage):** 3-10s depending on chunk count
- **Total API time:** Should be sum of all steps + overhead

#### Resource Usage
- **Memory:** Watch for increasing memory usage with large PDFs
- **Database growth:** Monitor chunk count vs performance
- **API response times:** Should remain consistent

#### Error Rates
- **Failed uploads:** Check file format/corruption
- **Database errors:** Connection or schema issues
- **LLM errors:** API key or model availability

### Log Patterns to Watch

#### Good Processing
```
🚀 STARTING DOCUMENT PROCESSING WORKFLOW
✅ STEP 1 COMPLETED: (reasonable time)
✅ STEP 2 COMPLETED: (reasonable chunk count)  
✅ STEP 3 COMPLETED: (successful storage)
🎉 WORKFLOW COMPLETED: (total time reasonable)
```

#### Problematic Patterns
```
❌ STEP X FAILED: (any step failure)
⚠️  No text extracted: (empty documents)
⚠️  No content to embed: (processing failure)
💥 WORKFLOW FAILED: (complete failure)
```

---

## 📝 Log File Locations

- **Server logs:** Console output (where you ran `python start_server.py`)
- **API request logs:** Same console, look for request IDs like `[a1b2c3d4]`
- **Database logs:** Check Docker logs: `docker-compose logs postgres`
- **Weaviate logs:** Check Docker logs: `docker-compose logs weaviate`

---

## 🎯 Quick Reference Commands

```bash
# Essential monitoring commands
python debug_tools.py full              # Complete system test
python db_inspect.py stats              # Database overview
curl localhost:8000/api/v1/debug/health-detailed  # Component status

# Upload and test
python debug_tools.py upload test.pdf   # Test document processing
python debug_tools.py question "test"   # Test Q&A

# Database investigation
python db_inspect.py documents          # Show all documents
python db_inspect.py search "keyword"   # Search content

# Troubleshooting
python debug_tools.py health            # Basic connectivity
python debug_tools.py detailed-health   # Component details
```

This monitoring system gives you complete visibility into your inference server's operation. You can see exactly what happens at each step, identify bottlenecks, and debug issues quickly with real data instead of guesswork!