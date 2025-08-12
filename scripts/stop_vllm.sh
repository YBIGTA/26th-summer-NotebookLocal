#!/bin/bash

# Stop vLLM servers
# Usage: ./stop_vllm.sh [port] or ./stop_vllm.sh all

set -e

PORT=${1:-all}

stop_server() {
    local port=$1
    local pids=$(lsof -ti:$port 2>/dev/null || true)
    
    if [ -n "$pids" ]; then
        echo "🛑 Stopping server on port $port (PIDs: $pids)"
        kill -TERM $pids
        sleep 2
        
        # Force kill if still running
        local remaining=$(lsof -ti:$port 2>/dev/null || true)
        if [ -n "$remaining" ]; then
            echo "🔥 Force killing remaining processes on port $port"
            kill -KILL $remaining
        fi
        echo "✅ Server on port $port stopped"
    else
        echo "ℹ️  No server running on port $port"
    fi
}

case $PORT in
    "all")
        echo "🛑 Stopping all vLLM servers..."
        stop_server 8001
        stop_server 8002
        ;;
    [0-9]*)
        stop_server $PORT
        ;;
    *)
        echo "❌ Invalid port. Use a port number or 'all'"
        echo "Usage: $0 [port|all]"
        exit 1
        ;;
esac

echo "🏁 Done!"