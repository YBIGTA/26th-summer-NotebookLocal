"""Question answering workflow using LangChain and LangGraph."""

from typing import Dict, Union

from langgraph.graph import END, StateGraph

from config import OPENAI_API_KEY, LLM_MODEL
from ..processors.embedder import Embedder
from ..storage.vector_store import SimpleVectorStore, WeaviateVectorStore

# As with the embeddings, try to import the ChatOpenAI wrapper from the modern
# package name but fall back to the legacy location for compatibility.
try:  # pragma: no cover - exercised in tests via patching
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover
    from langchain.chat_models import ChatOpenAI  # type: ignore


class QAWorkflow:
    """Simple retrieval-augmented question answering workflow."""

    def __init__(
        self,
        store: Union[SimpleVectorStore, WeaviateVectorStore],
        embedder: Embedder | None = None,
    ) -> None:
        self.store = store
        self.embedder = embedder or Embedder()
        self.llm = ChatOpenAI(model=LLM_MODEL, openai_api_key=OPENAI_API_KEY)

        workflow = StateGraph(dict)
        workflow.add_node("retrieve", self._retrieve)
        workflow.add_node("generate", self._generate)
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", END)
        workflow.set_entry_point("retrieve")
        self.graph = workflow.compile()

    # ------------------------------------------------------------------
    def _retrieve(self, state: Dict) -> Dict:
        if isinstance(self.store, SimpleVectorStore):
            q_emb = self.embedder.embed([state["question"]])[0]
            results = self.store.similarity_search(q_emb, k=4)
            state["context"] = "\n".join(text for text, _ in results)
        else:
            results = self.store.similarity_search(state["question"], k=4)
            state["context"] = "\n".join(r.get("text", "") for r in results)
        return state

    # ------------------------------------------------------------------
    def _generate(self, state: Dict) -> Dict:
        prompt = (
            "Answer the question based on the context below.\nContext:\n"
            f"{state['context']}\n\nQuestion: {state['question']}"
        )
        response = self.llm.invoke(prompt)
        state["answer"] = getattr(response, "content", str(response))
        return state

    # ------------------------------------------------------------------
    def ask(self, question: str) -> str:
        """Answer ``question`` using retrieved context."""

        final_state = self.graph.invoke({"question": question})
        return final_state["answer"]
