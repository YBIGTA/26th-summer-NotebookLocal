# Testing Guide

This guide explains how to test the LLM Router with **automatic vLLM server startup** to verify that routing works correctly and all adapters are functioning properly.

## 🚀 Quick Test Commands

### 1. Start the Router

```bash
# Using uv (recommended)
uv run python src/main.py

# Or traditional method
source venv/bin/activate && python src/main.py
```

The router will start on `http://localhost:8000`. **Local models auto-start when needed** - no manual shell scripts required!

### 2. Health Check

```bash
# Check all adapters
curl http://localhost:8000/v1/health | jq

# Expected output:
{
  "openai": true,      # if API key configured
  "anthropic": true,   # if API key configured  
  "qwen_text": true,   # if model exists and auto-start enabled
  "qwen_vision": true  # if model exists and auto-start enabled
}
```

## 🧪 Automated Testing

### New: Auto-Startup Test (Recommended)

**Test auto-startup feature specifically:**

```bash
# Quick auto-startup validation
uv run python test_autostart.py
```

This test:
- ✅ Cleans any existing vLLM processes
- ✅ Verifies router is running  
- ✅ Tests local model auto-startup (2-3 min first request)
- ✅ Verifies subsequent requests are fast
- ✅ Shows which processes are running

**Note:** Text adapter uses fully centralized config, vision adapter uses mixed approach.

### Comprehensive Test Suite

**Test all models and routing:**

```bash
# Enhanced test with auto-startup awareness
uv run python test_router.py
```

This tests:
- ✅ Health check endpoint
- ✅ Cloud models (OpenAI, Anthropic) 
- ✅ Local models with auto-startup (5 min timeout)
- ✅ Vision content routing
- ✅ Streaming responses
- ✅ Performance timing

## 🎯 Manual Testing Scenarios

### Test 1: Auto-Startup (Local Models)

**Should auto-start vLLM server on first request:**

```bash
# Kill any existing vLLM processes first
pkill -f vllm

# Test Qwen text auto-startup
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen3-14B-unsloth-bnb-4bit",
    "messages": [{"role": "user", "content": "Hello! Say hi briefly."}],
    "max_tokens": 20
  }' | jq '.model'
```

**Expected behavior:**
- ⏱️ First request: 2-3 minutes (server starting)
- 🚀 Router logs: "Starting vLLM server for Qwen3-14B..."
- ✅ Response includes model name
- 🔍 `ps aux | grep vllm` shows running process

**Test subsequent request (should be fast):**

```bash
# Same request again
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen3-14B-unsloth-bnb-4bit", 
    "messages": [{"role": "user", "content": "Count to 3"}],
    "max_tokens": 10
  }' | jq '.model'
```

**Expected:** ⚡ Fast response (< 5 seconds)

### Test 2: Default Routing (Simple Text)

**Should route to:** `qwen_text` (local model with auto-startup)

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello! How are you?"}],
    "max_tokens": 50
  }' | jq '.model'
```

**Expected output:** `"Qwen3-14B-unsloth-bnb-4bit"`

### Test 3: Explicit Model Selection

**Cloud models (require API keys):**

```bash
# Test OpenAI routing
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "What model are you?"}],
    "max_tokens": 50
  }' | jq '.model'

# Test Anthropic routing  
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-sonnet-20241022", 
    "messages": [{"role": "user", "content": "What model are you?"}],
    "max_tokens": 50
  }' | jq '.model'
```

### Test 4: Vision Content Detection

**Should route to:** `qwen_vision` (auto-starts vision server)

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "Describe this image"},
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
          }
        }
      ]
    }],
    "max_tokens": 100
  }' | jq '.model'
```

**Expected:** Vision server auto-starts (3-5 min first time), returns `"Qwen2.5-VL-7B-Instruct-unsloth-bnb-4bit"`

### Test 5: Streaming Response

**Should work with auto-startup:**

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen3-14B-unsloth-bnb-4bit",
    "messages": [{"role": "user", "content": "Count from 1 to 5"}],
    "stream": true,
    "max_tokens": 100
  }'
```

**Expected:** Server-sent events with streaming chunks (auto-starts if needed)

## 🔧 Auto-Startup Configuration

### Enable/Disable Auto-Startup

Edit `configs/models/qwen_text.yaml`:

```yaml
# Enable auto-startup (default)
auto_start: true

# Disable auto-startup (manual shell scripts required)
auto_start: false
```

Same for `configs/models/qwen_vision.yaml`.

### Verify Auto-Startup Settings

```bash
# Check current configuration
grep -A 3 -B 3 auto_start configs/models/*.yaml

# Expected output:
# configs/models/qwen_text.yaml:auto_start: true
# configs/models/qwen_vision.yaml:auto_start: true
```

## 🔍 Debugging Auto-Startup Issues

### Common Auto-Startup Problems

#### 1. Model Files Not Found

**Problem:** `Model not found at ./models/Qwen3-14B-unsloth-bnb-4bit`

**Solutions:**
```bash
# Check model files exist
ls -la models/Qwen3-14B-unsloth-bnb-4bit/
ls -la models/Qwen2.5-VL-7B-Instruct-unsloth-bnb-4bit/

# Update model_path in config if needed
# Edit configs/models/qwen_text.yaml:
model_path: /path/to/your/model
```

#### 2. Auto-Startup Timeout

**Problem:** `vLLM server failed to start within 2 minutes`

**Solutions:**
```bash
# Check GPU memory
nvidia-smi

# Free up GPU memory
pkill -f python  # Kill other GPU processes

# Check model size vs available VRAM
# Qwen3-14B needs ~8-12GB VRAM
# Qwen2.5-VL needs ~8-12GB VRAM
```

#### 3. Port Already in Use

**Problem:** `Address already in use: port 8001`

**Solutions:**
```bash
# Check what's using the port
netstat -tulpn | grep :8001

# Kill process using port
kill $(lsof -t -i:8001)

# Or use different port in config
# Edit configs/models/qwen_text.yaml:
server_url: http://localhost:8003  # Different port
```

#### 4. vLLM Installation Issues

**Problem:** `ModuleNotFoundError: No module named 'vllm'`

**Solutions:**
```bash
# Install vLLM
uv add vllm

# Or with pip
pip install vllm

# Check installation
python -c "import vllm; print('vLLM installed')"
```

### Manual Fallback

If auto-startup fails, use manual shell scripts:

```bash
# Start servers manually
./scripts/start_qwen_text.sh    # Port 8001
./scripts/start_qwen_vision.sh  # Port 8002

# Disable auto-startup in configs
# Set auto_start: false in YAML files
```

## 📊 Auto-Startup Test Results

### Expected Timing

| Scenario | First Request | Subsequent Requests |
|----------|---------------|-------------------|
| Qwen Text (cold start) | 2-3 minutes | < 5 seconds |
| Qwen Vision (cold start) | 3-5 minutes | < 10 seconds |
| Cloud APIs | 0.5-3 seconds | 0.5-3 seconds |
| Server already running | < 5 seconds | < 5 seconds |

### Process Verification

```bash
# Check all processes are running
ps aux | grep -E "(main.py|vllm)"

# Check ports
netstat -tulpn | grep ":800"

# Expected processes:
# python src/main.py           (router on 8000)
# python -m vllm...text        (text server on 8001) 
# python -m vllm...vision      (vision server on 8002)
```

## ✅ Auto-Startup Test Checklist

Before deployment with auto-startup enabled:

- [ ] Model files exist in correct paths
- [ ] Auto-startup enabled in YAML configs (`auto_start: true`)
- [ ] Sufficient GPU memory available (check `nvidia-smi`)
- [ ] Ports 8001, 8002 are free
- [ ] vLLM installed (`python -c "import vllm"`)
- [ ] First local model request succeeds (wait 2-3 min)
- [ ] Subsequent requests are fast (< 5 sec)
- [ ] Vision model auto-starts on image requests
- [ ] Process cleanup works on router shutdown
- [ ] Manual scripts still work as fallback

## 🧪 Advanced Auto-Startup Testing

### Test Auto-Cleanup

```bash
# Start router, make request to local model
uv run python src/main.py &
curl -X POST http://localhost:8000/v1/chat/completions \
  -d '{"model":"Qwen3-14B-unsloth-bnb-4bit","messages":[{"role":"user","content":"test"}]}'

# Stop router (should cleanup vLLM processes)
pkill -f "src/main.py"
sleep 5

# Verify cleanup
ps aux | grep vllm  # Should be empty
```

### Test Multiple Models

```bash
# Test both models auto-start
curl -X POST http://localhost:8000/v1/chat/completions \
  -d '{"model":"Qwen3-14B-unsloth-bnb-4bit","messages":[{"role":"user","content":"text"}]}'

curl -X POST http://localhost:8000/v1/chat/completions \
  -d '{"messages":[{"role":"user","content":[{"type":"text","text":"vision test"},{"type":"image_url","image_url":{"url":"data:image/png;base64,..."}}]}]}'

# Both servers should be running
ps aux | grep vllm | wc -l  # Should be 2
```

### Stress Test Auto-Startup

```bash
# Kill all vLLM processes
pkill -f vllm

# Rapid requests (tests queuing during startup)
for i in {1..5}; do
  curl -X POST http://localhost:8000/v1/chat/completions \
    -d '{"model":"Qwen3-14B-unsloth-bnb-4bit","messages":[{"role":"user","content":"Request '$i'"}]}' &
done

# All should eventually succeed
```

## 📋 New Test Files

1. **`test_autostart.py`** - Auto-startup validation script
2. **`test_router.py`** - Enhanced with auto-startup timeouts  
3. **`test.md`** - This comprehensive guide

Use `test_autostart.py` for quick validation, `test_router.py` for comprehensive testing!