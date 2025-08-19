"""LangGraph-powered document processing workflow."""

from typing import Dict, Union

from langgraph.graph import END, StateGraph

from langgraph.graph import END, StateGraph

from ..processors.pdf_processor import PDFProcessor
from ..processors.image_processor import ImageProcessor
from ..processors.text_processor import TextProcessor
from ..processors.embedder import Embedder
from ..storage.vector_store import SimpleVectorStore, WeaviateVectorStore


class DocumentWorkflow:
    """Process a PDF and populate the vector store."""

    def __init__(
        self,
        store: Union[SimpleVectorStore, WeaviateVectorStore],
        embedder: Embedder | None = None,
    ) -> None:

        self.pdf_processor = PDFProcessor()
        self.image_processor = ImageProcessor()
        self.text_processor = TextProcessor()
        self.embedder = embedder or Embedder()
        self.store = store

        workflow = StateGraph(dict)
        workflow.add_node("extract", self._extract)
        workflow.add_node("prepare", self._prepare)
        workflow.add_node("embed_store", self._embed_store)
        workflow.add_edge("extract", "prepare")
        workflow.add_edge("prepare", "embed_store")
        workflow.add_edge("embed_store", END)
        workflow.set_entry_point("extract")
        self.graph = workflow.compile()

    # ------------------------------------------------------------------
    def _extract(self, state: Dict) -> Dict:
        text, images = self.pdf_processor.extract(state["pdf_path"])
        state.update({"text": text, "images": images})
        return state

    # ------------------------------------------------------------------
    def _prepare(self, state: Dict) -> Dict:
        chunks = self.text_processor.process(state["text"])
        descriptions = self.image_processor.describe(state["images"]) if state["images"] else []
        state.update({"chunks": chunks, "descriptions": descriptions})
        return state

    # ------------------------------------------------------------------
    def _embed_store(self, state: Dict) -> Dict:
        combined = state["chunks"] + state["descriptions"]
        if combined:
            embeddings = self.embedder.embed(combined)
            self.store.add_texts(combined, embeddings)
        state["result"] = {"chunks": len(state["chunks"]), "images": len(state["images"])}
        return state

    # ------------------------------------------------------------------
    def run(self, pdf_path: str) -> Dict[str, int]:
        """Execute the workflow for ``pdf_path``."""

        final_state = self.graph.invoke({"pdf_path": pdf_path})
        return final_state["result"]
