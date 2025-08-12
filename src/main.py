from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from src.core.router import LLMRouter
from src.models.requests import ChatRequest
from src.models.responses import ChatResponse
from src.utils.config_loader import ConfigLoader
from src.utils.logger import setup_logger
import uvicorn
import logging
from typing import AsyncGenerator

logger = setup_logger()

config_loader = ConfigLoader()
try:
    server_config = config_loader.load_config('configs/server.yaml')
except FileNotFoundError:
    server_config = {
        'api': {'title': 'LLM Router API', 'version': '1.0.0', 'prefix': '/v1'},
        'cors': {'enabled': True, 'origins': ['*'], 'methods': ['*'], 'headers': ['*']},
        'server': {'host': '0.0.0.0', 'port': 8000, 'workers': 1}
    }

app = FastAPI(
    title=server_config['api']['title'],
    version=server_config['api']['version']
)

if server_config['cors']['enabled']:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=server_config['cors']['origins'],
        allow_methods=server_config['cors']['methods'],
        allow_headers=server_config['cors']['headers']
    )

try:
    router = LLMRouter()
except Exception as e:
    logger.error(f"Failed to initialize router: {e}")
    router = None


@app.post(f"{server_config['api']['prefix']}/chat/completions")
async def chat_completions(request: ChatRequest):
    """OpenAI-compatible chat completions endpoint"""
    if not router:
        raise HTTPException(status_code=503, detail="Router not initialized")
    
    try:
        result = await router.route(request)
        
        if request.stream:
            return StreamingResponse(result, media_type="text/plain")
        else:
            return result
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(f"{server_config['api']['prefix']}/models")
async def list_models():
    """List available models"""
    if not router:
        raise HTTPException(status_code=503, detail="Router not initialized")
    
    models = []
    for adapter_name, adapter in router.adapters.items():
        models.append({
            "id": adapter.model_id or adapter.name,
            "object": "model",
            "owned_by": adapter_name
        })
    return {"data": models}


@app.get("/health")
async def health():
    """Health check endpoint"""
    if not router:
        return {"router": False, "error": "Router not initialized"}
    
    try:
        health_status = await router.health_check()
        return health_status or {}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"error": str(e)}


@app.get(f"{server_config['api']['prefix']}/health") 
async def health_v1():
    """Health check endpoint (v1 API)"""
    return await health()


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown"""
    if router:
        logger.info("🧹 Cleaning up adapters...")
        for adapter_name, adapter in router.adapters.items():
            if hasattr(adapter, 'cleanup'):
                try:
                    adapter.cleanup()
                    logger.info(f"✅ Cleaned up {adapter_name}")
                except Exception as e:
                    logger.error(f"❌ Error cleaning up {adapter_name}: {e}")


if __name__ == "__main__":
    import signal
    import atexit
    
    host = server_config['server']['host']
    port = server_config['server']['port'] 
    workers = server_config['server'].get('workers', 1)
    
    logger.info(f"🚀 Starting LLM Router on {host}:{port}")
    logger.info(f"📍 Health check: http://{host}:{port}/v1/health")
    logger.info(f"📖 API docs: http://{host}:{port}/docs")
    
    def cleanup_on_exit():
        """Clean up on exit"""
        if router:
            for adapter_name, adapter in router.adapters.items():
                if hasattr(adapter, 'cleanup'):
                    try:
                        adapter.cleanup()
                    except:
                        pass
    
    def signal_handler(signum, frame):
        """Handle signals"""
        logger.info(f"📡 Received signal {signum}, cleaning up...")
        cleanup_on_exit()
        exit(0)
    
    # Register cleanup handlers
    atexit.register(cleanup_on_exit)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        uvicorn.run(
            "src.main:app",
            host=host,
            port=port,
            workers=1,  # Force single worker for proper cleanup
            reload=False,
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info("👋 Server interrupted")
        cleanup_on_exit()
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        cleanup_on_exit()
        raise