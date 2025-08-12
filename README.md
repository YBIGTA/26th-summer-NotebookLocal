# LLM Router

A unified API router for multiple language model providers with **automatic vLLM server management**. Routes requests intelligently between OpenAI, Anthropic Claude, and local Qwen models while maintaining full OpenAI API compatibility.

## ✨ Key Features

- **🤖 Multi-Provider Support**: OpenAI GPT, Anthropic Claude, Local Qwen models
- **🚀 Auto-Startup**: Automatically starts vLLM servers when local models are needed
- **🔄 Intelligent Routing**: Content-aware routing (text/vision/complexity-based)
- **⚡ OpenAI Compatible**: Drop-in replacement for OpenAI API (`/v1/chat/completions`)
- **🔗 Fallback Chain**: Automatic failover between adapters
- **📡 Streaming Support**: Real-time response streaming for all adapters
- **👁️ Vision Support**: Multi-modal content with automatic vision model routing
- **⚖️ Load Balancing**: Priority-based adapter selection
- **🔍 Health Monitoring**: Comprehensive adapter health checks

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+**
- **GPU with 20GB+ VRAM** (for local models)
- **API Keys** (for cloud models)

### Installation

**Option 1: uv (Recommended - Fast & Modern)**

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies and create virtual environment
uv sync

# Run the router
uv run python src/main.py
```

**Option 2: Traditional pip**

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the router  
python src/main.py
```

### Configuration

1. **Set up API keys** (optional for cloud models):
   ```bash
   export OPENAI_API_KEY="your-openai-key"
   export ANTHROPIC_API_KEY="your-anthropic-key"
   ```

2. **Place local models** (optional for offline inference):
   ```
   models/
   ├── Qwen3-14B-unsloth-bnb-4bit/          # Text model (8-12GB VRAM)
   └── Qwen2.5-VL-7B-Instruct-unsloth-bnb-4bit/  # Vision model (8-12GB VRAM)
   ```

3. **Start the router**:
   ```bash
   uv run python src/main.py
   ```
   
   Server starts at: http://localhost:8000

## 📡 API Usage

### Basic Text Completion

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 100
  }'
```

### Explicit Model Selection

```bash
# Use specific OpenAI model
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Complex reasoning task"}]
  }'

# Use local Qwen model (auto-starts vLLM server)
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-14b", 
    "messages": [{"role": "user", "content": "Fast local inference"}]
  }'
```

### Vision Requests

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "What do you see in this image?"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
      ]
    }]
  }'
```

### Streaming Response

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-14b",
    "messages": [{"role": "user", "content": "Stream this response"}],
    "stream": true
  }'
```

## 🧠 Intelligent Routing

The router automatically selects the best adapter based on:

### 1. Explicit Model Selection
```
gpt-4, gpt-3.5-turbo → openai
claude-3-5-sonnet → anthropic  
qwen3-14b → qwen_text (auto-starts vLLM)
```

### 2. Content-Based Routing
- **Vision content** → `qwen_vision` (auto-starts vision server)
- **Complex text** (>2000 chars) → `anthropic` (Claude reasoning)
- **Simple text** → `qwen_text` (fast local model)

### 3. Fallback Chain
If primary adapter fails: `qwen_text` → `anthropic` → `openai` → `qwen_vision`

## 🔧 Auto-Startup Feature

### How It Works

When you request a local model:

1. **Router checks** if vLLM server is running
2. **Auto-starts** vLLM server if needed (2-3 minutes first time)
3. **Processes request** once server is ready
4. **Subsequent requests** are fast (<5 seconds)

### Configuration

Edit `configs/models/qwen_text.yaml`:
```yaml
auto_start: true    # Enable auto-startup (default)
auto_start: false   # Disable (use manual scripts)
```

### Manual Scripts (Fallback)

⚠️ **Updated Scripts**: Now require explicit parameters with no defaults.

```bash
# Start local model servers manually (parameters now required)
./scripts/start_vllm.sh text      # REQUIRED: specify 'text' or 'vision'
./scripts/start_qwen_text.sh      # Text model startup (all params required)
./scripts/stop_vllm.sh           # Stop all servers

# The scripts will now fail with clear error messages if any 
# required configuration parameters are missing
```

## 📊 Supported Models

### Cloud Models
| Provider | Models | Capabilities |
|----------|--------|-------------|
| **OpenAI** | GPT-4, GPT-4 Turbo, GPT-3.5 Turbo | Text, Function calling |
| **Anthropic** | Claude 3.5 Sonnet, Claude 3 Opus, Claude 3.5 Haiku | Text, Reasoning, Analysis |

### Local Models (Auto-Startup)
| Model | Type | VRAM | Port | Features |
|-------|------|------|------|---------|
| **Qwen3-14B-unsloth-bnb-4bit** | Text | 8-12GB | 8001 | Fast inference, 27K context |
| **Qwen2.5-VL-7B-Instruct** | Vision | 8-12GB | 8002 | Image analysis, OCR, 32K context |

⚠️ **Configuration Note**: All model parameters are now **mandatory** - no default values are provided. Missing configuration will result in clear error messages.

## 🏗️ Project Structure

```
llm-router/
├── src/
│   ├── main.py                    # FastAPI application entry point
│   ├── core/
│   │   ├── router.py             # Main routing logic
│   │   ├── base_adapter.py       # Abstract adapter base class
│   │   └── exceptions.py         # Custom exceptions
│   ├── adapters/                 # Model adapters
│   │   ├── openai_adapter.py     # OpenAI/GPT models
│   │   ├── anthropic_adapter.py  # Claude models
│   │   ├── qwen_text_adapter.py  # Local Qwen text (with auto-startup)
│   │   └── qwen_vision_adapter.py # Local Qwen vision (with auto-startup)
│   ├── models/                   # Pydantic data models
│   │   ├── requests.py           # Request schemas
│   │   └── responses.py          # Response schemas  
│   └── utils/                    # Utilities
│       ├── config_loader.py      # YAML config loader
│       └── logger.py             # Logging setup
├── configs/                      # Configuration files
│   ├── server.yaml               # Server settings
│   ├── adapters.yaml             # Adapter enable/disable
│   ├── routing.yaml              # Routing rules
│   └── models/                   # Model-specific configs
│       ├── openai.yaml           # OpenAI settings
│       ├── anthropic.yaml        # Anthropic settings  
│       ├── qwen_text.yaml        # Qwen text + auto-startup
│       └── qwen_vision.yaml      # Qwen vision + auto-startup
├── scripts/                      # Utility scripts
│   ├── start_qwen_text.sh        # Manual vLLM text server startup
│   ├── start_qwen_vision.sh      # Manual vLLM vision server startup
│   └── stop_vllm.sh              # Stop vLLM servers
├── models/                       # Local model files (user-provided)
├── test_router.py                # Comprehensive testing
├── test_autostart.py             # Auto-startup validation
├── test.md                       # Testing guide
└── pyproject.toml                # Dependencies (uv/pip)
```

## 🧪 Testing

### Quick Auto-Startup Test

```bash
# Comprehensive auto-startup validation
uv run python test_autostart.py
```

### Full Testing Suite

```bash
# Test all models and routing logic
uv run python test_router.py
```

### Manual Health Check

```bash
# Check all adapter status
curl http://localhost:8000/v1/health | jq

# Expected output:
{
  "openai": true,       # if API key configured
  "anthropic": true,    # if API key configured  
  "qwen_text": true,    # if model exists and auto-start works
  "qwen_vision": true   # if model exists and auto-start works
}
```

## ⚙️ Configuration

### Routing Rules (`configs/routing.yaml`)

```yaml
rules:
  # Model mappings
  explicit_models:
    - models: [gpt-4, gpt-3.5-turbo]
      adapter: openai
    - models: [claude-3-5-sonnet-20241022]
      adapter: anthropic
      
  # Content routing
  vision_default: qwen_vision
  complexity_threshold: 2000
  complex_default: anthropic
  default_adapter: qwen_text

# Fallback order
fallback_chain: [qwen_text, anthropic, openai, qwen_vision]
```

### Auto-Startup Settings (`configs/models/qwen_text.yaml`)

⚠️ **IMPORTANT: NO DEFAULT PARAMETERS** - All configuration values are now **REQUIRED** and must be explicitly set.

```yaml
# ALL PARAMETERS ARE REQUIRED - NO DEFAULTS PROVIDED
name: qwen3-14b
model_id: Qwen3-14B-unsloth-bnb-4bit

# vLLM Server Configuration - ALL MANDATORY
vllm_settings:
  # Basic server settings - REQUIRED
  host: 0.0.0.0
  port: 8001
  model_path: ./models/Qwen3-14B-unsloth-bnb-4bit
  served_model_name: Qwen3-14B-unsloth-bnb-4bit
  
  # Memory and performance settings - REQUIRED
  max_model_len: 27648
  gpu_memory_utilization: 0.75
  max_num_seqs: 1
  tensor_parallel_size: 1
  swap_space: 16
  
  # Model loading settings - REQUIRED
  quantization: bitsandbytes
  load_format: bitsandbytes
  dtype: auto
  trust_remote_code: true
  
  # Optimization flags - REQUIRED
  disable_log_requests: true
  disable_custom_all_reduce: true
  enforce_eager: true
  
  # Environment variables - REQUIRED
  environment:
    PYTORCH_CUDA_ALLOC_CONF: "expandable_segments:True,max_split_size_mb:128"
    VLLM_SKIP_P2P_CHECK: "1"
    TRANSFORMERS_OFFLINE: "1"
    CUDA_LAUNCH_BLOCKING: "1"
    PYTORCH_NO_CUDA_MEMORY_CACHING: "0"
    VLLM_DISABLE_CUDA_GRAPHS: "1"
    VLLM_USE_V1: "0"
    VLLM_DISABLE_COMPILATION: "1"
    TORCH_COMPILE_DISABLE: "1"
    VLLM_WORKER_MULTIPROC_METHOD: "spawn"

# Application Settings - REQUIRED
auto_start: true
timeout: 60

# Inference Parameters - ALL REQUIRED
model_params:
  temperature: 0.6
  max_tokens: 4096
  top_p: 0.95
  top_k: 20
  repetition_penalty: 1.1
  frequency_penalty: 0.0
  presence_penalty: 0.0

# System Configuration - REQUIRED
system_prompt: "You are Qwen, a helpful AI assistant."

# Performance Tuning - REQUIRED
batch_size: 1
max_concurrent_requests: 1

# Capabilities - REQUIRED
capabilities:
  vision: false
  streaming: true
```

## 🔍 Monitoring

### Health Endpoints

```bash
# Main health check
curl http://localhost:8000/v1/health

# Alternative endpoint
curl http://localhost:8000/health
```

### Process Monitoring

```bash
# Check all processes
ps aux | grep -E "(main.py|vllm)"

# Check ports in use
netstat -tulpn | grep ":800"

# Monitor GPU usage (for local models)
watch -n 1 nvidia-smi
```

### Logs

```bash
# View server logs
tail -f logs/router.log

# Monitor auto-startup process
uv run python src/main.py | grep "Starting vLLM"
```

## 🚨 Troubleshooting

### Configuration Errors (NEW)

**Problem**: `Missing required configuration key` or `ERROR: Missing required...`

**Solutions**:
```bash
# Check your config files have ALL required parameters
# No defaults are provided - every parameter must be explicitly set

# For qwen_text.yaml, ensure all sections are present:
# - vllm_settings (with ALL sub-parameters)
# - model_params (with ALL inference parameters)
# - environment variables (ALL 10 required)
# - capabilities, system_prompt, etc.

# Scripts will now fail fast with clear error messages
# Check the error output for the specific missing parameter
```

### Local Models Won't Start

**Problem**: `Model not found` or `vLLM server failed to start`

**Solutions**:
```bash
# Check model files exist
ls -la models/Qwen3-14B-unsloth-bnb-4bit/

# Check GPU memory
nvidia-smi

# Check vLLM installation
python -c "import vllm; print('vLLM OK')"

# Manual startup for debugging (now requires explicit parameter)
./scripts/start_vllm.sh text  # REQUIRED parameter
./scripts/start_qwen_text.sh  # All config values must be present
```

### API Key Issues

**Problem**: Cloud models returning authorization errors

**Solutions**:
```bash
# Check environment variables
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY

# Or set in .env file
echo 'OPENAI_API_KEY=your-key' > .env
echo 'ANTHROPIC_API_KEY=your-key' >> .env
```

### Port Conflicts

**Problem**: `Address already in use: port 8000`

**Solutions**:
```bash
# Find process using port
lsof -i :8000

# Kill process
kill $(lsof -t -i:8000)

# Or use different port in configs/server.yaml
port: 8001
```

## 📈 Performance

### Expected Response Times
- **Local models** (after startup): 100-500ms
- **OpenAI API**: 500-2000ms  
- **Anthropic API**: 800-3000ms
- **Vision processing**: 1000-5000ms

### First Request Timing
- **Qwen Text** (cold start): 2-3 minutes
- **Qwen Vision** (cold start): 3-5 minutes
- **Subsequent requests**: <5 seconds

### Memory Requirements
- **Qwen3-14B**: 8-12GB VRAM
- **Qwen2.5-VL**: 8-12GB VRAM  
- **Router process**: ~100MB RAM

## 📚 Advanced Usage

### Custom Routing Rules

Edit `configs/routing.yaml` to customize routing behavior:

```yaml
rules:
  # Route math questions to Claude
  explicit_models:
    - models: [math-solver]
      adapter: anthropic
      
  # Lower complexity threshold
  complexity_threshold: 1000
```

### Load Testing

```bash
# Install apache bench
sudo apt install apache2-utils

# Test concurrent requests
ab -n 100 -c 10 \
  -p test_payload.json \
  -T application/json \
  http://localhost:8000/v1/chat/completions
```

### Docker Deployment

```dockerfile
FROM python:3.12
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
EXPOSE 8000
CMD ["python", "src/main.py"]
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Run tests: `uv run python test_router.py`
4. Commit changes: `git commit -m 'Add amazing feature'`
5. Push branch: `git push origin feature/amazing-feature`
6. Open Pull Request

## 📄 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

- **FastAPI** - Modern web framework
- **vLLM** - High-performance LLM inference
- **LangChain** - LLM abstraction layer
- **Qwen Team** - Open-source models
- **OpenAI** - API compatibility standard
- **Anthropic** - Claude models

---

**Start routing your LLM requests intelligently!** 🚀

For detailed testing instructions, see [test.md](test.md).