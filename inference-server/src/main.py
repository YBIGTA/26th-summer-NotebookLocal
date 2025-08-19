from .processors.embedder import Embedder
from .storage.vector_store import get_vector_store
from .workflows.document_workflow import DocumentWorkflow
from .workflows.qa_workflow import QAWorkflow


class LectureProcessor:
    def __init__(self) -> None:
        self.embedder = Embedder()
        self.store = get_vector_store(self.embedder.embed)
        self.document_workflow = DocumentWorkflow(self.store, self.embedder)
        self.qa_workflow = QAWorkflow(self.store, self.embedder)

    def process_document(self, pdf_path: str):
        return self.document_workflow.run(pdf_path)

    def ask_question(self, question: str) -> str:
        return self.qa_workflow.ask(question)
