#!/bin/bash

# Start vLLM server for Qwen3-14B text model using centralized configuration
# This script reads ALL settings from configs/models/qwen_text.yaml

set -e

CONFIG_FILE="./configs/models/qwen_text.yaml"

echo "🚀 Starting vLLM server for Qwen3-14B text model"
echo "📋 Reading configuration from: $CONFIG_FILE"

# Function to read YAML values using Python - NO DEFAULTS ALLOWED
get_yaml_value() {
    python -c "
import yaml
import sys
with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
    
# Navigate nested dictionary
keys = '$1'.split('.')
value = config
for key in keys:
    if isinstance(value, dict) and key in value:
        value = value[key]
    else:
        print(f'ERROR: Missing required configuration key: $1', file=sys.stderr)
        sys.exit(1)
        
print(value)
"
}

# Read all vLLM settings from centralized config - ALL REQUIRED, NO DEFAULTS
echo "📋 Validating required configuration parameters..."

MODEL_PATH=$(get_yaml_value "vllm_settings.model_path")
PORT=$(get_yaml_value "vllm_settings.port")
HOST=$(get_yaml_value "vllm_settings.host")
SERVED_MODEL_NAME=$(get_yaml_value "vllm_settings.served_model_name")
MAX_MODEL_LEN=$(get_yaml_value "vllm_settings.max_model_len")
GPU_MEMORY_UTIL=$(get_yaml_value "vllm_settings.gpu_memory_utilization")
MAX_NUM_SEQS=$(get_yaml_value "vllm_settings.max_num_seqs")
TENSOR_PARALLEL_SIZE=$(get_yaml_value "vllm_settings.tensor_parallel_size")
QUANTIZATION=$(get_yaml_value "vllm_settings.quantization")
LOAD_FORMAT=$(get_yaml_value "vllm_settings.load_format")
DTYPE=$(get_yaml_value "vllm_settings.dtype")
TRUST_REMOTE_CODE=$(get_yaml_value "vllm_settings.trust_remote_code")
DISABLE_LOG_REQUESTS=$(get_yaml_value "vllm_settings.disable_log_requests")
DISABLE_CUSTOM_ALL_REDUCE=$(get_yaml_value "vllm_settings.disable_custom_all_reduce")
ENFORCE_EAGER=$(get_yaml_value "vllm_settings.enforce_eager")

echo "✅ All required vLLM settings validated"

# Set environment variables from config - ALL REQUIRED
echo "🔧 Setting required environment variables..."

export PYTORCH_CUDA_ALLOC_CONF=$(get_yaml_value "vllm_settings.environment.PYTORCH_CUDA_ALLOC_CONF")
export VLLM_SKIP_P2P_CHECK=$(get_yaml_value "vllm_settings.environment.VLLM_SKIP_P2P_CHECK")
export TRANSFORMERS_OFFLINE=$(get_yaml_value "vllm_settings.environment.TRANSFORMERS_OFFLINE")
export CUDA_LAUNCH_BLOCKING=$(get_yaml_value "vllm_settings.environment.CUDA_LAUNCH_BLOCKING")
export PYTORCH_NO_CUDA_MEMORY_CACHING=$(get_yaml_value "vllm_settings.environment.PYTORCH_NO_CUDA_MEMORY_CACHING")
export VLLM_DISABLE_CUDA_GRAPHS=$(get_yaml_value "vllm_settings.environment.VLLM_DISABLE_CUDA_GRAPHS")
export VLLM_USE_V1=$(get_yaml_value "vllm_settings.environment.VLLM_USE_V1")
export VLLM_DISABLE_COMPILATION=$(get_yaml_value "vllm_settings.environment.VLLM_DISABLE_COMPILATION")
export TORCH_COMPILE_DISABLE=$(get_yaml_value "vllm_settings.environment.TORCH_COMPILE_DISABLE")
export VLLM_WORKER_MULTIPROC_METHOD=$(get_yaml_value "vllm_settings.environment.VLLM_WORKER_MULTIPROC_METHOD")

echo "✅ All required environment variables set"

echo "📍 Model path: $MODEL_PATH"
echo "🔌 Port: $PORT" 
echo "📏 Context window: $MAX_MODEL_LEN"
echo "💾 GPU memory utilization: $GPU_MEMORY_UTIL"
echo "🔄 Max sequences: $MAX_NUM_SEQS"

# Check if model directory exists
if [ ! -d "$MODEL_PATH" ]; then
    echo "❌ Error: Model directory not found: $MODEL_PATH"
    echo "Please download or link your model to this path"
    exit 1
fi

# Build command arguments
CMD_ARGS=(
    --model "$MODEL_PATH"
    --port "$PORT"
    --host "$HOST"
    --served-model-name "$SERVED_MODEL_NAME"
    --max-model-len "$MAX_MODEL_LEN"
    --quantization "$QUANTIZATION"
    --load-format "$LOAD_FORMAT"
    --gpu-memory-utilization "$GPU_MEMORY_UTIL"
    --dtype "$DTYPE"
    --max-num-seqs "$MAX_NUM_SEQS"
    --tensor-parallel-size "$TENSOR_PARALLEL_SIZE"
)

# Add required flags based on config
if [ "$TRUST_REMOTE_CODE" = "true" ]; then
    CMD_ARGS+=(--trust-remote-code)
fi

if [ "$DISABLE_LOG_REQUESTS" = "true" ]; then
    CMD_ARGS+=(--disable-log-requests)
fi

if [ "$DISABLE_CUSTOM_ALL_REDUCE" = "true" ]; then
    CMD_ARGS+=(--disable-custom-all-reduce)
fi

if [ "$ENFORCE_EAGER" = "true" ]; then
    CMD_ARGS+=(--enforce-eager)
fi

echo "🚀 Starting vLLM server with centralized configuration..."

# Start vLLM server
python -m vllm.entrypoints.openai.api_server "${CMD_ARGS[@]}"