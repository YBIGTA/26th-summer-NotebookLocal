# vLLM Configuration Centralization

## 🎯 Problem Solved

**Before:** vLLM settings were scattered across 5+ files:
- ❌ `config.json` - Model's native config
- ❌ `generation_config.json` - Default generation settings  
- ❌ `qwen_text.yaml` - App config
- ❌ `start_qwen_text.sh` - Manual startup script
- ❌ `qwen_text_adapter.py` - Runtime code

**After:** ✅ Single source of truth in `configs/models/qwen_text.yaml`

## 🏗️ Architecture

### Centralized Configuration Structure

```yaml
# configs/models/qwen_text.yaml

# 🎯 SINGLE SOURCE OF TRUTH - All vLLM settings here
vllm_settings:
  # Server settings
  server_url: http://localhost:8001
  port: 8001
  host: 0.0.0.0
  model_path: ./models/Qwen3-14B-unsloth-bnb-4bit
  served_model_name: Qwen3-14B-unsloth-bnb-4bit
  
  # Memory & Performance
  max_model_len: 8192                # Context window
  gpu_memory_utilization: 0.6        # 60% GPU memory usage
  max_num_seqs: 64                   # Concurrent sequences
  tensor_parallel_size: 1            # Multi-GPU setup
  
  # Model Loading
  quantization: bitsandbytes         # Quantization method
  load_format: bitsandbytes          # Loading format
  dtype: auto                        # Data type
  trust_remote_code: true            # Allow custom code
  
  # Optimization
  disable_log_requests: true         # Reduce logging
  
  # Environment Variables
  environment:
    PYTORCH_CUDA_ALLOC_CONF: "expandable_segments:True"
    VLLM_SKIP_P2P_CHECK: "1"
    TRANSFORMERS_OFFLINE: "1"

# App-level settings
model_params:                        # Inference parameters
  temperature: 0.6
  max_tokens: 8192
  top_p: 0.95
  # ... other params
```

### How It Works

#### 1. **Adapter Code** (`src/adapters/qwen_text_adapter.py`)
```python
# Reads from centralized config
self.vllm_settings = self.config.get('vllm_settings', {})

# Builds vLLM command dynamically
cmd = [
    "python", "-m", "vllm.entrypoints.openai.api_server",
    "--model", self.vllm_settings.get('model_path'),
    "--port", str(self.vllm_settings.get('port')),
    "--max-model-len", str(self.vllm_settings.get('max_model_len')),
    # ... all other settings from config
]
```

#### 2. **Manual Script** (`scripts/start_qwen_text.sh`)
```bash
# Function to read YAML values
get_yaml_value() {
    python -c "
import yaml
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
# Navigate nested keys like 'vllm_settings.max_model_len'
"
}

# Read all settings from YAML
MAX_MODEL_LEN=$(get_yaml_value "vllm_settings.max_model_len" "8192")
GPU_MEMORY_UTIL=$(get_yaml_value "vllm_settings.gpu_memory_utilization" "0.6")
# ... all other settings

# Use in command
python -m vllm.entrypoints.openai.api_server \
    --max-model-len "$MAX_MODEL_LEN" \
    --gpu-memory-utilization "$GPU_MEMORY_UTIL" \
    # ... all flags from config
```

## 🔧 Usage

### Change Any Setting - One Place
Want to adjust memory usage? 
```yaml
vllm_settings:
  gpu_memory_utilization: 0.8  # ← Change here only
```
→ **Both auto-start and manual script use new value automatically**

Want bigger context window?
```yaml
vllm_settings:
  max_model_len: 16384  # ← Change here only  
```
→ **Everything updates automatically**

Want different quantization?
```yaml
vllm_settings:
  quantization: gptq        # ← Change here only
  load_format: gptq         # ← Update related settings
```
→ **Consistent across all launch methods**

### Supported Settings

| Category | Settings | Purpose |
|----------|----------|---------|
| **Server** | `server_url`, `port`, `host` | Connection settings |
| **Model** | `model_path`, `served_model_name` | Model identification |
| **Memory** | `max_model_len`, `gpu_memory_utilization`, `max_num_seqs` | Resource management |
| **Loading** | `quantization`, `load_format`, `dtype`, `trust_remote_code` | Model loading behavior |
| **Performance** | `tensor_parallel_size`, `disable_log_requests` | Optimization flags |
| **Environment** | `PYTORCH_CUDA_ALLOC_CONF`, `VLLM_SKIP_P2P_CHECK` | System environment |

## 🚀 Benefits

### ✅ **Consistency**
- No more mismatched settings between script and code
- Same configuration used everywhere
- Single source of truth eliminates conflicts

### ✅ **Maintainability** 
- Change one value → everything updates
- Easy to version control configurations
- Clear separation of concerns

### ✅ **Flexibility**
- Easy to switch between different model configs
- Environment-specific settings (dev/prod)
- Runtime parameter validation

### ✅ **Debugging**
- All settings visible in one place  
- Easy to compare configurations
- Clear logs showing which config is used

## 🔍 Configuration Flow

```
configs/models/qwen_text.yaml
           ↓
    ┌─────────────┬─────────────┐
    ↓             ↓             ↓
Adapter Code  Manual Script  Environment
(auto-start)   (manual run)   Variables
    ↓             ↓             ↓
    └─────────────┴─────────────┘
                  ↓
            vLLM Server
        (same configuration)
```

## 🎛️ Advanced Usage

### Multi-Model Setup
```yaml
# configs/models/qwen-14b.yaml
vllm_settings:
  model_path: ./models/Qwen3-14B-unsloth-bnb-4bit
  port: 8001
  max_model_len: 8192

# configs/models/qwen-30b.yaml  
vllm_settings:
  model_path: ./models/Qwen3-30B-A3B-bnb-4bit
  port: 8002
  max_model_len: 4096  # Smaller context for larger model
```

### Environment-Specific Configs
```yaml
# configs/models/qwen_dev.yaml - Development
vllm_settings:
  gpu_memory_utilization: 0.5    # Conservative for dev
  max_num_seqs: 16              # Fewer sequences
  disable_log_requests: false   # Enable logging

# configs/models/qwen_prod.yaml - Production  
vllm_settings:
  gpu_memory_utilization: 0.8    # Aggressive for prod
  max_num_seqs: 128             # More sequences
  disable_log_requests: true    # Disable logging
```

## 🎯 Result

**Before:** 😫 Hunt through 5 files to change context length
**After:** 😎 Change `max_model_len: 8192` in one file → Done!

**Perfect centralization achieved!** 🎉