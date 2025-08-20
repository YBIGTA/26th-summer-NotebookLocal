#!/bin/bash

# Development setup script with UV for local models

echo "🚀 Setting up inference server development environment with UV..."

# Check if UV is installed
if ! command -v uv &> /dev/null; then
    echo "❌ UV is not installed. Installing UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
fi

echo "✅ UV is available"

# Check if Docker is available for databases
if ! command -v docker &> /dev/null; then
    echo "⚠️ Docker not found. You'll need to set up PostgreSQL and Weaviate manually."
else
    echo "🐳 Starting databases with Docker..."
    ./setup_docker.sh
fi

# Create virtual environment and install dependencies
echo "📦 Creating virtual environment and installing dependencies..."
uv sync

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo "✅ Please edit .env file with your API keys"
fi

echo ""
echo "🎉 Development environment ready!"
echo ""
echo "🔧 Next steps:"
echo "  1. Edit .env file with your API keys"
echo "  2. For local models: uv add <model-package>"
echo "  3. Start server: python start_server.py"
echo ""
echo "🚀 UV commands:"
echo "  uv add <package>     # Add new dependency"
echo "  uv remove <package>  # Remove dependency"
echo "  uv sync              # Sync dependencies"
echo "  uv run <command>     # Run in virtual env"
echo ""
echo "🧪 Local model development:"
echo "  uv add torch torchvision  # For PyTorch models"
echo "  uv add vllm              # For VLLM inference"
echo "  uv add transformers      # For HuggingFace models"