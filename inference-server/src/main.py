from .processors.embedder import Embedder
from .storage.vector_store import get_vector_store
from .storage.hybrid_store import HybridStore
from .workflows.document_workflow import DocumentWorkflow
from .database.init_db import init_database_on_startup
from .llm.core.router import LLMRouter
from .database.file_manager import file_manager
from .vault.file_queue_manager import FileQueueManager
from .workflows.prefect_document_flows import initialize_prefect_document_processor
import logging

logger = logging.getLogger(__name__)


class LectureProcessor:
    def __init__(self, use_hybrid: bool = True) -> None:
        # Initialize Universal Router first
        try:
            self.router = LLMRouter()
            logger.info("✅ Universal Router initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Universal Router: {e}")
            raise ValueError(f"Universal Router initialization failed: {e}")
        
        # Initialize embedder with router
        self.embedder = Embedder(router=self.router)
        
        if use_hybrid:
            # Initialize PostgreSQL database first
            if not init_database_on_startup():
                logger.warning("Database initialization failed, falling back to vector store only")
                self.store = get_vector_store(self.embedder.embed)
            else:
                # Use hybrid PostgreSQL + Weaviate storage
                vector_store = get_vector_store(self.embedder.embed)
                self.store = HybridStore(vector_store, self.embedder)
        else:
            # Use legacy vector store only
            self.store = get_vector_store(self.embedder.embed)
        
        self.document_workflow = DocumentWorkflow(self.store, self.embedder, router=self.router)
        
        # Initialize Prefect DocumentProcessor with all dependencies
        self.queue_manager = FileQueueManager(file_manager)
        self.prefect_processor = initialize_prefect_document_processor(
            document_workflow=self.document_workflow,
            file_manager=file_manager,
            queue_manager=self.queue_manager
        )
        
        # QA workflow removed - now handled by intelligence system

    @property
    def document_processing_service(self):
        """Backward compatibility property."""
        return self.prefect_processor

    async def process_document(self, pdf_path: str):
        return await self.document_workflow.run(pdf_path)

    # ask_question removed - now handled by intelligence system via /api/v1/intelligence/chat
