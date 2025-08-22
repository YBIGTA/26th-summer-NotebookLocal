"""Question answering workflow using LangChain and LangGraph with modular LLM routing."""

from typing import Dict, Union, Any
import logging

from langgraph.graph import END, StateGraph

from ..processors.embedder import Embedder
from ..storage.vector_store import SimpleVectorStore, WeaviateVectorStore
from ..storage.hybrid_store import HybridStore
from ..llm.core.router import LLMRouter
from ..llm.models.requests import ChatRequest, Message
from ..llm.models.responses import ChatResponse


class QAWorkflow:
    """Retrieval-augmented question answering workflow with hybrid search support."""

    def __init__(
        self,
        store: Union[SimpleVectorStore, WeaviateVectorStore, HybridStore],
        embedder: Embedder | None = None,
        llm_router: LLMRouter | None = None,
    ) -> None:
        self.store = store
        self.embedder = embedder or Embedder()
        
        # Initialize LLM router - NO FALLBACKS
        if llm_router is None:
            raise ValueError("LLM router is required - no fallback available")
        self.llm_router = llm_router

        workflow = StateGraph(dict)
        workflow.add_node("retrieve", self._retrieve)
        workflow.add_node("generate", self._generate)
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", END)
        workflow.set_entry_point("retrieve")
        self.graph = workflow.compile()

    # ------------------------------------------------------------------
    def _retrieve(self, state: Dict) -> Dict:
        logger = logging.getLogger(__name__)
        logger.info(f"🔍 Starting retrieval for question: '{state['question'][:50]}...'")
        
        if isinstance(self.store, HybridStore):
            # Use hybrid search with metadata filtering
            filters = state.get("filters", None)  # Optional filters from API
            logger.info(f"📊 Using HybridStore with filters: {filters}")
            
            results = self.store.search(
                query=state["question"],
                k=4,
                filters=filters,
                alpha=0.7  # Favor semantic search over keyword
            )
            
            logger.info(f"📋 Found {len(results)} results from hybrid search")
            
            # Build context with source information
            context_parts = []
            sources = []
            
            for result in results:
                doc_info = result.get("document", {})
                source_info = f"[{doc_info.get('title', 'Unknown')}]"
                if result.get("page"):
                    source_info += f" (Page {result['page']})"
                
                context_parts.append(f"{source_info}: {result['text']}")
                sources.append(source_info)
            
            state["context"] = "\n\n".join(context_parts)
            state["sources"] = sources
            
            logger.info(f"📝 Built context: {len(state['context'])} chars from {len(context_parts)} chunks")
            
        elif isinstance(self.store, SimpleVectorStore):
            logger.info("📊 Using SimpleVectorStore")
            q_emb = self.embedder.embed([state["question"]])[0]
            results = self.store.similarity_search(q_emb, k=4)
            state["context"] = "\n".join(text for text, _ in results)
            state["sources"] = []
            
            logger.info(f"📝 Built context: {len(state['context'])} chars from {len(results)} chunks")
        else:
            logger.info("📊 Using fallback vector store")
            results = self.store.similarity_search(state["question"], k=4)
            state["context"] = "\n".join(r.get("text", "") for r in results)
            state["sources"] = []
            
            logger.info(f"📝 Built context: {len(state['context'])} chars from {len(results)} chunks")
            
        return state

    # ------------------------------------------------------------------
    async def _generate(self, state: Dict) -> Dict:
        if not self.llm_router:
            state["answer"] = "Error: LLM router not available"
            return state
        
        logger = logging.getLogger(__name__)
        
        try:
            logger.info("🤖 Starting LLM generation...")
            
            # Get the default chat model from router config
            if not hasattr(self.llm_router, 'routing_config') or 'rules' not in self.llm_router.routing_config:
                raise ValueError("LLM router not properly configured")
                
            selected_model = self.llm_router.routing_config['rules']['chat_default']
            if not selected_model:
                raise ValueError("No default chat model configured in router")
            
            logger.info(f"📥 Selected model: {selected_model}")
            
            # Load model-specific configuration  
            model_config = self._load_model_config(selected_model)
            workflow_config = model_config.get('workflows', {}).get('qa_workflow', {})
            
            # Get model-specific system prompt - NO FALLBACK
            system_prompt = workflow_config.get('system_prompt')
            if not system_prompt:
                raise ValueError(f"No system_prompt configured for model {selected_model} in qa_workflow")
            
            # Get model-specific parameters - NO FALLBACKS
            model_params = workflow_config.get('parameters')
            if not model_params:
                raise ValueError(f"No parameters configured for model {selected_model} in qa_workflow")
            
            logger.info(f"🔧 Using model config: temp={model_params.get('temperature')}, max_tokens={model_params.get('max_tokens')}")
            
            # Build messages with model-specific prompt
            messages = [
                Message(role="system", content=system_prompt),
                Message(
                    role="user", 
                    content=f"Context:\n{state['context']}\n\nQuestion: {state['question']}"
                )
            ]
            
            # Create new request with model-specific configuration
            configured_request = ChatRequest(
                messages=messages,
                model=selected_model,
                **model_params
            )
            
            logger.info(f"📤 Sending configured request: {len(messages)} messages, model={selected_model}")
            
            # Route the properly configured request
            response = await self.llm_router.route(configured_request)
            
            logger.info(f"📥 Router response received from {selected_model}")
            
            if response.choices and len(response.choices) > 0:
                answer = response.choices[0].message.content
                state["answer"] = answer
                logger.info(f"✅ LLM generation successful: {len(answer)} chars")
            else:
                state["answer"] = "Error: No response from LLM"
                logger.error("❌ LLM response had no choices")
                
        except Exception as e:
            error_msg = f"Error in LLM generation: {e}"
            logger.error(f"❌ {error_msg}")
            state["answer"] = f"Error: {str(e)}"
            
        return state

    def _load_model_config(self, model_name: str) -> dict:
        """Load model configuration to get workflow-specific settings"""
        from ..llm.utils.config_loader import ConfigLoader
        config_loader = ConfigLoader()
        
        # Determine provider from model name
        if 'gpt' in model_name.lower() or 'text-embedding' in model_name.lower():
            provider = 'openai'
        elif 'claude' in model_name.lower():
            provider = 'anthropic'
        elif 'qwen' in model_name.lower():
            provider = 'qwen'
        else:
            raise ValueError(f"Unknown provider for model {model_name} - cannot determine config path")
        
        try:
            config_path = f'configs/models/{provider}/{model_name}.yaml'
            return config_loader.load_config(config_path)
        except Exception as e:
            logger.error(f"Failed to load config for {model_name}: {e}")
            raise

    # ------------------------------------------------------------------
    async def ask(self, question: str, filters: Dict[str, Any] = None) -> str:
        """Answer ``question`` using retrieved context with optional filters."""

        final_state = await self.graph.ainvoke({
            "question": question,
            "filters": filters
        })
        return final_state["answer"]
    
    async def ask_with_sources(self, question: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Answer question and return sources for citation."""
        
        final_state = await self.graph.ainvoke({
            "question": question,
            "filters": filters
        })
        
        return {
            "answer": final_state["answer"],
            "sources": final_state.get("sources", []),
            "context": final_state.get("context", "")
        }
