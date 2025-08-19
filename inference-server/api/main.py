from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import router

app = FastAPI(
    title="NotebookLocal Inference Server",
    description="A streamlined AI system for processing Korean PDFs with modular LLM routing and Obsidian integration",
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


@app.get("/api")
def api_info():
    """API information endpoint."""
    return {
        "status": "ok",
        "service": "notebook-local-inference-server",
        "version": "1.0.0",
        "features": ["Korean PDF Processing", "Modular LLM Routing", "RAG Chat"],
        "endpoints": {
            "health": "/api/v1/health",
            "process": "/api/v1/process",
            "ask": "/api/v1/ask",
            "chat_completions": "/api/v1/chat/completions",
            "models": "/api/v1/models",
            "obsidian_chat": "/api/v1/obsidian/chat",
            "obsidian_chat_stream": "/api/v1/obsidian/chat/stream",
            "obsidian_search": "/api/v1/obsidian/search",
            "obsidian_documents": "/api/v1/obsidian/documents"
        }
    }
