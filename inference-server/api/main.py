from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from .routes import router
from src.database.init_db import check_database_health

logger = logging.getLogger(__name__)

app = FastAPI(
    title="NotebookLocal Inference Server",
    description="A streamlined AI system for document processing with modular LLM routing and Obsidian integration",
    version="1.0.0"
)

# Add CORS middleware for Obsidian plugin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    """Run startup checks."""
    logger.info("🚀 Starting NotebookLocal Inference Server...")
    
    # Check database health
    if check_database_health():
        logger.info("✅ Database is ready")
    else:
        logger.warning("⚠️ Database issues detected")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    logger.info("🛑 Shutting down NotebookLocal Inference Server...")


@app.get("/api")
def api_info():
    """API information endpoint."""
    return {
        "status": "ok",
        "service": "notebook-local-inference-server",
        "version": "1.0.0",
        "features": ["Document Processing", "Modular LLM Routing", "Intelligence System"],
        "endpoints": {
            "health": "/api/v1/health",
            "process": "/api/v1/process",
            "ask": "/api/v1/ask",
            "chat_completions": "/api/v1/chat/completions",
            "models": "/api/v1/models",
            "intelligence_chat": "/api/v1/intelligence/chat",
            "intelligence_capabilities": "/api/v1/intelligence/capabilities",
            "obsidian_search": "/api/v1/obsidian/search",
            "obsidian_documents": "/api/v1/obsidian/documents",
            "documents_upload_process": "/api/v1/documents/upload-and-process",
            "documents_process_file": "/api/v1/documents/process-file",
            "documents_process_vault": "/api/v1/documents/process-vault",
            "documents_health": "/api/v1/documents/health",
            "documents_stats": "/api/v1/documents/stats"
        }
    }
