#!/bin/bash

# Start vLLM server for Qwen3-14B text model using centralized configuration
# This script reads ALL settings from configs/models/qwen_text.yaml

set -e

CONFIG_FILE="./configs/models/qwen_text.yaml"

echo "🚀 Starting vLLM server for Qwen3-14B text model"
echo "📋 Reading configuration from: $CONFIG_FILE"

# Function to read YAML values using Python
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
        print('$2')  # default value
        sys.exit(0)
        
print(value)
"
}

# Read all vLLM settings from centralized config
MODEL_PATH=$(get_yaml_value "vllm_settings.model_path" "./models/Qwen3-14B-unsloth-bnb-4bit")
PORT=$(get_yaml_value "vllm_settings.port" "8001")
HOST=$(get_yaml_value "vllm_settings.host" "0.0.0.0")
SERVED_MODEL_NAME=$(get_yaml_value "vllm_settings.served_model_name" "Qwen3-14B-unsloth-bnb-4bit")
MAX_MODEL_LEN=$(get_yaml_value "vllm_settings.max_model_len" "8192")
GPU_MEMORY_UTIL=$(get_yaml_value "vllm_settings.gpu_memory_utilization" "0.6")
MAX_NUM_SEQS=$(get_yaml_value "vllm_settings.max_num_seqs" "64")
TENSOR_PARALLEL_SIZE=$(get_yaml_value "vllm_settings.tensor_parallel_size" "1")
QUANTIZATION=$(get_yaml_value "vllm_settings.quantization" "bitsandbytes")
LOAD_FORMAT=$(get_yaml_value "vllm_settings.load_format" "bitsandbytes")
DTYPE=$(get_yaml_value "vllm_settings.dtype" "auto")
TRUST_REMOTE_CODE=$(get_yaml_value "vllm_settings.trust_remote_code" "true")
DISABLE_LOG_REQUESTS=$(get_yaml_value "vllm_settings.disable_log_requests" "true")

# Set environment variables from config
export PYTORCH_CUDA_ALLOC_CONF=$(get_yaml_value "vllm_settings.environment.PYTORCH_CUDA_ALLOC_CONF" "expandable_segments:True")
export VLLM_SKIP_P2P_CHECK=$(get_yaml_value "vllm_settings.environment.VLLM_SKIP_P2P_CHECK" "1")
export TRANSFORMERS_OFFLINE=$(get_yaml_value "vllm_settings.environment.TRANSFORMERS_OFFLINE" "1")

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

# Add optional flags based on config
if [ "$TRUST_REMOTE_CODE" = "true" ]; then
    CMD_ARGS+=(--trust-remote-code)
fi

if [ "$DISABLE_LOG_REQUESTS" = "true" ]; then
    CMD_ARGS+=(--disable-log-requests)
fi

echo "🚀 Starting vLLM server with centralized configuration..."

# Start vLLM server
python -m vllm.entrypoints.openai.api_server "${CMD_ARGS[@]}"