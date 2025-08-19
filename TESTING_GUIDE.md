# Testing Guide for NotebookLocal

This guide provides step-by-step instructions for testing the Obsidian plugin and inference server integration.

## Prerequisites

- Node.js 16+ installed
- Python 3.9+ installed
- Obsidian desktop app installed
- OpenAI API key

## 1. Testing Obsidian Plugin

### Setup

```bash
cd obsidian-plugin/
npm install
npm run build
```

### Install in Obsidian

1. **Copy plugin to Obsidian**:
   ```bash
   # Create plugins directory if it doesn't exist
   mkdir -p ~/.obsidian/plugins/obsidian-copilot/
   
   # Copy built files
   cp main.js ~/.obsidian/plugins/obsidian-copilot/
   cp manifest.json ~/.obsidian/plugins/obsidian-copilot/
   cp styles.css ~/.obsidian/plugins/obsidian-copilot/
   ```

2. **Enable in Obsidian**:
   - Open Obsidian Settings → Community Plugins
   - Disable Safe Mode (if enabled)
   - Find "Obsidian Copilot" and enable it

### Plugin Tests

#### Basic Functionality
- [ ] Plugin loads without errors
- [ ] Settings page opens (Settings → Plugin Options → Obsidian Copilot)
- [ ] Commands appear in Command Palette (Ctrl/Cmd + P)
- [ ] Chat interface opens via ribbon icon or command

#### UI Components
- [ ] Chat interface renders correctly
- [ ] Settings form shows all configuration options
- [ ] Modal dialogs open and close properly
- [ ] Responsive design works on different screen sizes

#### Development Mode
For active development:
```bash
# Create symlink to plugins directory
ln -s "$(pwd)" ~/.obsidian/plugins/obsidian-copilot

# Run development mode with hot reload
npm run dev

# Test changes by reloading Obsidian
# Ctrl/Cmd + P → "Reload app without saving"
```

## 2. Testing Inference Server

### Setup

```bash
cd inference-server/

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### Environment Configuration (.env)

```bash
# Required
OPENAI_API_KEY=your_openai_api_key_here

# Optional - Weaviate (uses simple storage if not configured)
WEAVIATE_URL=http://localhost:8080
WEAVIATE_API_KEY=your_weaviate_api_key_here
```

### Start Server

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### Server Tests

#### Health Check
```bash
curl http://localhost:8000/api/v1/health
# Expected: {"status": "healthy", "timestamp": "..."}
```

#### API Documentation
- [ ] Visit http://localhost:8000/docs (Swagger UI)
- [ ] Visit http://localhost:8000/redoc (ReDoc)
- [ ] All endpoints documented correctly

#### Core Endpoints

**Upload Document**:
```bash
curl -X POST "http://localhost:8000/api/v1/process" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test_document.pdf"
```

**Ask Question**:
```bash
curl -X POST "http://localhost:8000/api/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the main topics discussed?"}'
```

#### Obsidian-Specific Endpoints

**Chat**:
```bash
curl -X POST "http://localhost:8000/api/v1/obsidian/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Explain the concept",
    "chat_id": "test_session",
    "stream": false
  }'
```

**Document Search**:
```bash
curl -X POST "http://localhost:8000/api/v1/obsidian/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning",
    "limit": 10
  }'
```

**Document Management**:
```bash
# List documents
curl http://localhost:8000/api/v1/obsidian/documents

# Index status
curl http://localhost:8000/api/v1/obsidian/index/status
```

## 3. Integration Testing

### Plugin-Server Connection

1. **Start inference server** (port 8000)
2. **Configure plugin**:
   - Open Obsidian Settings → Obsidian Copilot
   - Set Server URL: `http://localhost:8000`
   - Test connection

### End-to-End Workflow

#### Document Upload Flow
1. Upload PDF via plugin interface
2. Verify document appears in server's document list
3. Check processing status

#### Chat Flow
1. Open chat interface in plugin
2. Send a question about uploaded document
3. Verify response contains relevant information
4. Check response includes source references

#### Search Flow
1. Use search functionality in plugin
2. Enter query related to uploaded content
3. Verify search results are relevant
4. Test different similarity thresholds

### Test Scenarios

#### Basic Integration
- [ ] Plugin connects to server successfully
- [ ] Document upload works through plugin
- [ ] Chat responses are received and displayed
- [ ] Search functionality returns results

#### Error Handling
- [ ] Server offline: Plugin shows appropriate error
- [ ] Invalid API key: Proper error message
- [ ] Network timeout: Graceful handling
- [ ] File upload errors: User-friendly feedback

#### Performance
- [ ] Document processing completes within reasonable time
- [ ] Chat responses stream in real-time
- [ ] Search queries return quickly (<2 seconds)
- [ ] UI remains responsive during operations

## 4. Korean PDF Testing

### Test Korean Documents
- [ ] Upload Korean PDF documents
- [ ] Verify text extraction works correctly
- [ ] Test Q&A with Korean content
- [ ] Check search functionality with Korean queries

### Font Handling
- [ ] No font warnings in server logs
- [ ] Text appears correctly in responses
- [ ] Mixed Korean/English documents work

## 5. Troubleshooting

### Common Issues

**Plugin not loading**:
- Check browser console (F12) for errors
- Verify all files copied to plugins directory
- Restart Obsidian

**Server connection failed**:
- Verify server is running: `curl http://localhost:8000/api/v1/health`
- Check firewall settings
- Confirm correct URL in plugin settings

**Document upload fails**:
- Check file format (PDF only)
- Verify server has disk space
- Check server logs for detailed errors

**Chat not working**:
- Ensure documents are uploaded first
- Verify OpenAI API key is valid
- Check API timeout settings

### Debug Mode

**Plugin Debug**:
```javascript
// In browser console
localStorage.setItem('obsidian-copilot-debug', 'true');
```

**Server Debug**:
```bash
# Start with debug logging
uvicorn api.main:app --reload --log-level debug
```

## 6. Development Testing

### Plugin Development
```bash
# Run tests
npm test

# Type checking
npm run build  # Includes TypeScript compilation

# Linting
npm run lint
```

### Server Development
```bash
# Run automated setup
python setup.py

# Manual testing
pytest  # If tests are available

# Code formatting
black .
```

## 7. Performance Testing

### Load Testing
- Test with multiple concurrent users
- Upload large PDF files
- Send multiple chat requests simultaneously
- Monitor memory usage

### Stress Testing
- Upload many documents consecutively
- Test search with large document corpus
- Verify system stability under load

---

## Test Checklist Summary

### Pre-Integration
- [ ] Obsidian plugin builds successfully
- [ ] Plugin loads in Obsidian
- [ ] Inference server starts without errors
- [ ] Server health endpoint responds

### Basic Integration
- [ ] Plugin connects to server
- [ ] Document upload works
- [ ] Chat functionality works
- [ ] Search returns results

### Advanced Features
- [ ] Korean PDF support works
- [ ] Streaming responses work
- [ ] Error handling is graceful
- [ ] Performance is acceptable

### Production Ready
- [ ] All tests pass
- [ ] No console errors
- [ ] Documentation is accurate
- [ ] Configuration is secure

---

**Note**: Always test with both English and Korean documents to verify full functionality of the Korean PDF support features.