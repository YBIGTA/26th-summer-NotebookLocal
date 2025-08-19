# vLLM Configuration Centralization

## 🎯 Implementation Status

**Text Adapter** (✅ Fully Centralized):
- ✅ All vLLM settings read from `qwen_text.yaml`
- ✅ No defaults - all parameters required
- ✅ Scripts read from centralized config
- ✅ Runtime validation enforced

**Vision Adapter** (⚠️ Partially Centralized):
- ⚠️ Basic settings in `qwen_vision.yaml`
- ⚠️ Many vLLM parameters hardcoded in adapter
- ⚠️ Scripts use hardcoded values
- ⚠️ Falls back to defaults

## 🏗️ Architecture

### Text Adapter - Fully Centralized Structure

```yaml
# configs/models/qwen_text.yaml

# 🎯 SINGLE SOURCE OF TRUTH - All vLLM settings here (TEXT ONLY)
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

#### 1. **Text Adapter Code** (`src/adapters/qwen_text_adapter.py`) - ✅ Fully Centralized
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

#### 2. **Text Script** (`scripts/start_qwen_text.sh`) - ✅ Fully Centralized
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

#### 3. **Vision Adapter Code** (`src/adapters/qwen_vision_adapter.py`) - ⚠️ Partially Centralized
```python
# Vision adapter uses mixed approach
self.server_url = self.config.get('server_url', 'http://localhost:8002')  # Fallback
self.model_path = self.config.get('model_path', './models/...')  # Fallback

# Many vLLM parameters are hardcoded:
cmd = [
    "--max-model-len", "32768",  # Hardcoded
    "--gpu-memory-utilization", "0.8",  # Hardcoded
    "--max-num-seqs", "128",  # Hardcoded
    # ... more hardcoded values
]
```

#### 4. **Vision Script** (`scripts/start_qwen_vision.sh`) - ⚠️ Hardcoded
```bash
# All parameters are hardcoded in script
MODEL_PATH="./models/Qwen2.5-VL-7B-Instruct-unsloth-bnb-4bit"
PORT=8002
# No YAML reading
```

## 🔧 Usage

### Text Adapter - Change Any Setting in One Place
Want to adjust memory usage? 
```yaml
vllm_settings:
  gpu_memory_utilization: 0.8  # ← Change here only
```
→ **Both auto-start and manual script use new value automatically**

### Vision Adapter - Mixed Approach
Want to adjust memory usage?
```python
# Must change in adapter code:
"--gpu-memory-utilization", "0.8",  # ← Hardcoded in adapter
```
→ **Only affects auto-start, manual script still uses hardcoded values**

### Text Adapter Examples (Fully Centralized)
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

### Vision Adapter Examples (Partially Centralized)
Want bigger context window?
```python
# Must change in adapter code:
"--max-model-len", "16384",  # ← Hardcoded in adapter
```
→ **Only affects auto-start, manual script needs separate update**

### Supported Settings (Text Adapter Only)

| Category | Settings | Purpose |
| **Server** | `server_url`, `port`, `host` | Connection settings |
| **Model** | `model_path`, `served_model_name` | Model identification |
| **Memory** | `max_model_len`, `gpu_memory_utilization`, `max_num_seqs` | Resource management |
| **Loading** | `quantization`, `load_format`, `dtype`, `trust_remote_code` | Model loading behavior |
| **Performance** | `tensor_parallel_size`, `disable_log_requests` | Optimization flags |
| **Environment** | `PYTORCH_CUDA_ALLOC_CONF`, `VLLM_SKIP_P2P_CHECK` | System environment |

## 🚀 Benefits

### Text Adapter (✅ Fully Centralized)
#### ✅ **Consistency**
- No mismatched settings between script and code
- Same configuration used everywhere
- Single source of truth eliminates conflicts

#### ✅ **Maintainability** 
- Change one value → everything updates
- Easy to version control configurations
- Clear separation of concerns

#### ✅ **Flexibility**
- Easy to switch between different model configs
- Environment-specific settings (dev/prod)
- Runtime parameter validation

#### ✅ **Debugging**
- All settings visible in one place  
- Easy to compare configurations
- Clear logs showing which config is used

### Vision Adapter (⚠️ Partially Centralized)
#### ⚠️ **Mixed Approach**
- Basic settings in YAML, advanced in code
- Some consistency between auto-start and config
- Manual script independent of config

#### ⚠️ **Limitations**
- vLLM parameters require code changes
- Script and adapter can diverge
- Less flexible than text adapter

## 🔍 Configuration Flow

### Text Adapter (✅ Centralized)
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

### Vision Adapter (⚠️ Partially Centralized)
```
configs/models/qwen_vision.yaml    Hardcoded Values
           ↓                          ↓
    ┌─────────────┐              ┌─────────────┐
    ↓             ↓              ↓             ↓
Adapter Code  (Basic Config)  Manual Script  (Hardcoded)
(auto-start)   (YAML only)     (manual run)   (No YAML)
    ↓             ↓              ↓             ↓
    └─────────────┬──────────────┴─────────────┘
                  ↓
            vLLM Server
       (mixed configuration)
```

## 🎛️ Advanced Usage

### Multi-Model Setup
```yaml
# configs/models/qwen-14b.yaml
vllm_settings:
  model_path: ./models/Qwen3-14B-unsloth-bnb-4bit
  port: 8001
  max_model_len: 8192

# configs/models/qwen-vision.yaml  
vllm_settings:
  model_path: ./models/Qwen2.5-VL-7B-Instruct-unsloth-bnb-4bit
  port: 8002
  max_model_len: 32768  # Vision model context
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

**Text Adapter:**
- **Before:** 😫 Hunt through 5 files to change context length
- **After:** 😎 Change `max_model_len: 8192` in one file → Done!
- **Status:** ✅ Perfect centralization achieved!

**Vision Adapter:**
- **Current:** 🤔 Basic settings in YAML, vLLM params in code
- **To change context:** Edit both `qwen_vision_adapter.py` and script
- **Status:** ⚠️ Partial centralization - needs refactoring

**Recommendation:** Refactor vision adapter to match text adapter's centralized approach.