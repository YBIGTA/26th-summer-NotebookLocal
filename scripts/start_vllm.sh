#!/bin/bash

# Start vLLM server for a specific model using unified YAML configuration
# Usage: ./start_vllm.sh [text|vision]

set -e

MODEL_TYPE=${1:-text}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Function to read YAML values using Python
get_yaml_value() {
    python -c "
import yaml
import sys
with open('$1', 'r') as f:
    config = yaml.safe_load(f)
    
# Navigate nested dictionary
keys = '$2'.split('.')
value = config
for key in keys:
    if isinstance(value, dict) and key in value:
        value = value[key]
    else:
        print('$3')  # default value
        sys.exit(0)
        
print(value)
"
}

# Select config file based on model type
case $MODEL_TYPE in
    "text")
        CONFIG_FILE="./configs/models/qwen_text.yaml"
        echo "🚀 Starting Qwen text model server"
        ;;
    "vision")
        CONFIG_FILE="./configs/models/qwen_vision.yaml"
        echo "🚀 Starting Qwen vision model server"
        ;;
    *)
        echo "❌ Invalid model type. Use: text or vision"
        echo "Usage: $0 [text|vision]"
        exit 1
        ;;
esac

echo "📋 Reading configuration from: $CONFIG_FILE"

# Read all settings from YAML config
MODEL_PATH=$(get_yaml_value "$CONFIG_FILE" "vllm_settings.model_path" "./models/default")
PORT=$(get_yaml_value "$CONFIG_FILE" "vllm_settings.port" "8001")
HOST=$(get_yaml_value "$CONFIG_FILE" "vllm_settings.host" "0.0.0.0")
MODEL_NAME=$(get_yaml_value "$CONFIG_FILE" "vllm_settings.served_model_name" "default")
MAX_LEN=$(get_yaml_value "$CONFIG_FILE" "vllm_settings.max_model_len" "8192")
GPU_MEM=$(get_yaml_value "$CONFIG_FILE" "vllm_settings.gpu_memory_utilization" "0.65")
MAX_SEQS=$(get_yaml_value "$CONFIG_FILE" "vllm_settings.max_num_seqs" "32")
TENSOR_PARALLEL=$(get_yaml_value "$CONFIG_FILE" "vllm_settings.tensor_parallel_size" "1")
QUANTIZATION=$(get_yaml_value "$CONFIG_FILE" "vllm_settings.quantization" "bitsandbytes")
LOAD_FORMAT=$(get_yaml_value "$CONFIG_FILE" "vllm_settings.load_format" "bitsandbytes")
DTYPE=$(get_yaml_value "$CONFIG_FILE" "vllm_settings.dtype" "auto")
TRUST_REMOTE_CODE=$(get_yaml_value "$CONFIG_FILE" "vllm_settings.trust_remote_code" "true")
DISABLE_LOG_REQUESTS=$(get_yaml_value "$CONFIG_FILE" "vllm_settings.disable_log_requests" "true")

# Vision-specific settings
if [ "$MODEL_TYPE" = "vision" ]; then
    EXTRA_ARGS="--limit-mm-per-prompt image=$(get_yaml_value "$CONFIG_FILE" "vllm_settings.max_images_per_prompt" "16")"
else
    EXTRA_ARGS=""
fi

# Set environment variables from config
export PYTORCH_CUDA_ALLOC_CONF=$(get_yaml_value "$CONFIG_FILE" "vllm_settings.environment.PYTORCH_CUDA_ALLOC_CONF" "expandable_segments:True")
export VLLM_SKIP_P2P_CHECK=$(get_yaml_value "$CONFIG_FILE" "vllm_settings.environment.VLLM_SKIP_P2P_CHECK" "1")
export TRANSFORMERS_OFFLINE=$(get_yaml_value "$CONFIG_FILE" "vllm_settings.environment.TRANSFORMERS_OFFLINE" "1")

echo "📍 Model path: $MODEL_PATH"
echo "🔌 Port: $PORT"
echo "📏 Context window: $MAX_LEN"
echo "💾 GPU memory utilization: $GPU_MEM"
echo "🔄 Max sequences: $MAX_SEQS"

# Check if model directory exists
if [ ! -d "$MODEL_PATH" ]; then
    echo "❌ Error: Model directory not found: $MODEL_PATH"
    echo "Please download or link your model to this path"
    exit 1
fi

# Check if port is already in use
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "❌ Error: Port $PORT is already in use"
    echo "Stop the existing server or use a different port"
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p logs

echo "⏳ Starting vLLM server... This may take 1-5 minutes to load the model."

# Build command arguments
CMD_ARGS=(
    --model "$MODEL_PATH"
    --port "$PORT"
    --host "$HOST"
    --served-model-name "$MODEL_NAME"
    --max-model-len "$MAX_LEN"
    --quantization "$QUANTIZATION"
    --load-format "$LOAD_FORMAT"
    --gpu-memory-utilization "$GPU_MEM"
    --dtype "$DTYPE"
    --max-num-seqs "$MAX_SEQS"
    --tensor-parallel-size "$TENSOR_PARALLEL"
)

# Add optional flags based on config
if [ "$TRUST_REMOTE_CODE" = "true" ]; then
    CMD_ARGS+=(--trust-remote-code)
fi

if [ "$DISABLE_LOG_REQUESTS" = "true" ]; then
    CMD_ARGS+=(--disable-log-requests)
fi

# Add vision-specific args
if [ -n "$EXTRA_ARGS" ]; then
    CMD_ARGS+=($EXTRA_ARGS)
fi

echo "🚀 Starting vLLM server with unified YAML configuration..."

# Start vLLM server
python -m vllm.entrypoints.openai.api_server "${CMD_ARGS[@]}"