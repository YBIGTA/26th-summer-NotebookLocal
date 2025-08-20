#!/bin/bash

# Comprehensive setup script for NotebookLocal Inference Server
# Handles both Docker databases and local development environment
#
# Usage:
#   ./setup_local_dev.sh              # Normal setup (requires Docker)
#   ./setup_local_dev.sh --no-docker  # Skip Docker setup (manual databases)

echo "🚀 Setting up NotebookLocal Inference Server..."

# Check for --no-docker flag
FORCE_NO_DOCKER=false
if [[ "$1" == "--no-docker" ]]; then
    FORCE_NO_DOCKER=true
    echo "⚠️ Skipping Docker setup (--no-docker flag detected)"
fi

# Check if UV is installed, install if needed
if ! command -v uv &> /dev/null; then
    echo "📦 UV not found. Installing UV for fast dependency management..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
fi
echo "✅ UV is available"

# Check Docker for databases
if [[ "$FORCE_NO_DOCKER" == "true" ]]; then
    echo "⚠️ Skipping Docker setup. You'll need to set up PostgreSQL and Weaviate manually."
    echo "💡 See DATABASE_SETUP.md for manual setup instructions"
    SKIP_DOCKER=true
elif ! command -v docker &> /dev/null; then
    echo "⚠️ Docker not found. You'll need to set up PostgreSQL and Weaviate manually."
    echo "💡 See DATABASE_SETUP.md for manual setup instructions"
    SKIP_DOCKER=true
else
    if ! command -v docker-compose &> /dev/null; then
        echo "❌ Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        echo "❌ Docker daemon is not running or permission denied!"
        echo ""
        echo "🚨 The hybrid PostgreSQL + Weaviate system requires Docker."
        echo ""
        echo "Common solutions:"
        echo "  1. Start Docker daemon:"
        echo "     sudo systemctl start docker"
        echo ""
        echo "  2. Fix Docker permissions (if 'permission denied'):"
        echo "     sudo usermod -aG docker \$USER"
        echo "     newgrp docker"
        echo "     # Then logout/login or restart terminal"
        echo ""
        echo "  3. Retry setup:"
        echo "     ./setup_local_dev.sh"
        echo ""
        echo "Alternative options:"
        echo "  ./setup_local_dev.sh --no-docker  # Skip Docker (manual setup)"
        echo "  See DATABASE_SETUP.md for manual database instructions"
        echo ""
        exit 1
    else
        echo "✅ Docker and Docker Compose are available and running"
    fi
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✅ Please edit .env file with your API keys before starting the server"
fi

# Install Python dependencies with UV
echo "📦 Installing dependencies with UV (this is fast!)..."
uv sync

if [ "$SKIP_DOCKER" != "true" ]; then
    # Start Docker services
    echo "🐳 Starting PostgreSQL and Weaviate with Docker..."
    if ! docker-compose up -d; then
        echo "❌ Failed to start Docker services"
        echo ""
        echo "🚨 Docker setup failed!"
        echo ""
        echo "Please check and retry:"
        echo "  docker-compose logs"
        echo "  docker-compose down"
        echo "  ./setup_local_dev.sh"
        echo ""
        exit 1
    fi

    # Wait for services to be healthy
    echo "⏳ Waiting for services to start..."
    sleep 10

    # Check PostgreSQL with timeout
    echo "🔍 Checking PostgreSQL connection..."
    timeout=0
    until docker-compose exec postgres pg_isready -U inference_user -d inference_db; do
        echo "Waiting for PostgreSQL..."
        sleep 2
        ((timeout++))
        if [ $timeout -gt 30 ]; then
            echo "❌ PostgreSQL failed to start within 60 seconds"
            echo ""
            echo "🚨 Database setup failed!"
            echo ""
            echo "Please check and retry:"
            echo "  docker-compose logs postgres"
            echo "  docker-compose down"
            echo "  ./setup_local_dev.sh"
            echo ""
            exit 1
        fi
    done
    echo "✅ PostgreSQL is ready"

    # Check Weaviate with timeout
    echo "🔍 Checking Weaviate connection..."
    timeout=0
    until curl -s http://localhost:8080/v1/.well-known/live > /dev/null; do
        echo "Waiting for Weaviate..."
        sleep 2
        ((timeout++))
        if [ $timeout -gt 30 ]; then
            echo "❌ Weaviate failed to start within 60 seconds"
            echo ""
            echo "🚨 Database setup failed!"
            echo ""
            echo "Please check and retry:"
            echo "  docker-compose logs weaviate"
            echo "  docker-compose down"
            echo "  ./setup_local_dev.sh"
            echo ""
            exit 1
        fi
    done
    echo "✅ Weaviate is ready"
fi

echo ""
echo "🎉 Complete setup successful!"
echo ""
echo "📊 Service URLs:"
echo "  PostgreSQL: localhost:5432"
echo "  Weaviate:   http://localhost:8080"
echo ""
echo "🚀 Next steps:"
echo "  1. Edit .env file with your API keys"
echo "  2. Start server: python start_server.py"
echo "  3. Visit: http://localhost:8000/docs"
echo ""
echo "🛠️ Local model development:"
echo "  uv add vllm              # Add VLLM for local inference"
echo "  uv add transformers      # Add HuggingFace models"
echo "  uv add torch torchvision # Add PyTorch"
echo ""
echo "📚 UV commands:"
echo "  uv add <package>         # Add new dependency"
echo "  uv remove <package>      # Remove dependency"
echo "  uv sync                  # Sync dependencies"
echo "  uv run <command>         # Run in virtual env"
echo ""
echo "🛑 To stop services:"
echo "  docker-compose down"
echo ""
echo "📚 Documentation:"
echo "  README.md - Overview and quick start"
echo "  QUICKSTART.md - 3-step setup guide"
echo "  DATABASE_SETUP.md - Detailed database setup"