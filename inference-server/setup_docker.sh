#!/bin/bash

# Setup script for Docker-based inference server

echo "🚀 Setting up NotebookLocal Inference Server with Docker..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✅ Please edit .env file with your API keys before starting the server"
fi

# Start Docker services
echo "🐳 Starting PostgreSQL and Weaviate with Docker..."
docker-compose up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to start..."
sleep 10

# Check PostgreSQL
echo "🔍 Checking PostgreSQL connection..."
until docker-compose exec postgres pg_isready -U inference_user -d inference_db; do
    echo "Waiting for PostgreSQL..."
    sleep 2
done
echo "✅ PostgreSQL is ready"

# Check Weaviate
echo "🔍 Checking Weaviate connection..."
until curl -s http://localhost:8080/v1/.well-known/live > /dev/null; do
    echo "Waiting for Weaviate..."
    sleep 2
done
echo "✅ Weaviate is ready"

echo ""
echo "🎉 Docker services are running!"
echo ""
echo "📊 Service URLs:"
echo "  PostgreSQL: localhost:5432"
echo "  Weaviate:   http://localhost:8080"
echo ""
echo "🚀 To start the inference server:"
echo "  python start_server.py"
echo ""
echo "🛑 To stop services:"
echo "  docker-compose down"
echo ""
echo "📝 Don't forget to set your OpenAI API key in .env file!"