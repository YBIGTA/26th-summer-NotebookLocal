#!/bin/bash

# Start vLLM server for Qwen2.5-VL vision model
# Port: 8002

set -e

MODEL_PATH="./models/Qwen2.5-VL-7B-Instruct-unsloth-bnb-4bit"
PORT=8002

echo "🚀 Starting vLLM server for Qwen2.5-VL vision model"
echo "📍 Model path: $MODEL_PATH"
echo "🔌 Port: $PORT"

# Check if model directory exists
if [ ! -d "$MODEL_PATH" ]; then
    echo "❌ Error: Model directory not found: $MODEL_PATH"
    echo "Please download or link your model to this path"
    exit 1
fi

# Start vLLM server for vision model
python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" \
    --port $PORT \
    --host 0.0.0.0 \
    --trust-remote-code \
    --served-model-name "Qwen2.5-VL-7B-Instruct-unsloth-bnb-4bit" \
    --max-model-len 32768 \
    --quantization bitsandbytes \
    --load-format bitsandbytes \
    --gpu-memory-utilization 0.8 \
    --dtype auto \
    --disable-log-requests \
    --max-num-seqs 64 \
    --tensor-parallel-size 1 \
    --limit-mm-per-prompt "image=16"