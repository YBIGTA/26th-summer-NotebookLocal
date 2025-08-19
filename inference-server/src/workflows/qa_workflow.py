"""Question answering workflow using LangChain and LangGraph with modular LLM routing."""

from typing import Dict, Union
import asyncio

from langgraph.graph import END, StateGraph

from ..processors.embedder import Embedder
from ..storage.vector_store import SimpleVectorStore, WeaviateVectorStore
from ..llm.core.router import LLMRouter
from ..llm.models.requests import ChatRequest, Message
from ..llm.models.responses import ChatResponse


class QAWorkflow:
    """Simple retrieval-augmented question answering workflow with modular LLM routing."""

    def __init__(
        self,
        store: Union[SimpleVectorStore, WeaviateVectorStore],
        embedder: Embedder | None = None,
        llm_router: LLMRouter | None = None,
    ) -> None:
        self.store = store
        self.embedder = embedder or Embedder()
        
        # Initialize LLM router or fallback to None
        try:
            self.llm_router = llm_router or LLMRouter()
        except Exception as e:
            print(f"Warning: Failed to initialize LLM router: {e}")
            self.llm_router = None

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
        if not self.llm_router:
            state["answer"] = "Error: LLM router not available"
            return state
        
        try:
            # Create OpenAI-compatible request
            messages = [
                Message(
                    role="system", 
                    content="Answer the question based on the provided context. If the question is in Korean, respond in Korean."
                ),
                Message(
                    role="user", 
                    content=f"Context:\n{state['context']}\n\nQuestion: {state['question']}"
                )
            ]
            
            request = ChatRequest(
                messages=messages,
                temperature=0.7,
                max_tokens=2048
            )
            
            # Use asyncio to run the async LLM router
            response = asyncio.run(self.llm_router.route(request))
            
            if response.choices and len(response.choices) > 0:
                state["answer"] = response.choices[0].message.content
            else:
                state["answer"] = "Error: No response from LLM"
                
        except Exception as e:
            print(f"Error in LLM generation: {e}")
            state["answer"] = f"Error: {str(e)}"
            
        return state

    # ------------------------------------------------------------------
    def ask(self, question: str) -> str:
        """Answer ``question`` using retrieved context."""

        final_state = self.graph.invoke({"question": question})
        return final_state["answer"]
