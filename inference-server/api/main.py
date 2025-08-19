from fastapi import FastAPI
from .routes import router

app = FastAPI(
    title="Lecture Processor API",
    description="A streamlined AI system for processing lecture PDFs through OCR, multimodal understanding, embedding generation, and intelligent Q&A",
    version="1.0.0"
)

app.include_router(router, prefix="/api/v1")


@app.get("/api")
def api_info():
    """API information endpoint."""
    return {
        "status": "ok",
        "service": "lecture-processor",
        "version": "1.0.0",
        "endpoints": {
            "process": "/api/v1/process",
            "ask": "/api/v1/ask",
            "health": "/api/v1/health"
        }
    }
