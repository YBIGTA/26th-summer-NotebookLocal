from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, AsyncGenerator, List
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langchain_core.language_models import BaseChatModel
from ..models.requests import ChatRequest
from ..models.responses import ChatResponse
import yaml


class BaseAdapter(ABC):
    """Base adapter that all model adapters must inherit from"""
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            self.config = self._load_config(config_path)
            self.name = self.config.get('name', 'unknown')
            self.model_id = self.config.get('model_id')
        else:
            # Stateless adapter - no default config
            self.config = {}
            self.name = self.__class__.__name__
            self.model_id = None
        self.llm: Optional[BaseChatModel] = None
        self._initialized = False
    
    def _load_config(self, config_path: str) -> Dict:
        """Load adapter-specific configuration"""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    @abstractmethod
    def initialize(self):
        """Initialize the adapter with LangChain ChatModel"""
        pass
    
    async def _ensure_initialized(self):
        """Ensure the model is loaded (lazy loading)"""
        if not self._initialized:
            print(f"🔄 Loading model for adapter: {self.name}...")
            self.initialize()
            self._initialized = True
            print(f"✅ Model loaded for adapter: {self.name}")
    
    @abstractmethod
    async def complete(self, request: ChatRequest) -> ChatResponse:
        """Process a completion request - MUST be implemented by all adapters"""
        pass
    
    @abstractmethod  
    async def stream(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """Process a streaming request - MUST be implemented by all adapters"""
        pass
    
    @abstractmethod
    def embed(self, texts: List[str], model: str) -> List[List[float]]:
        """Generate embeddings - MUST be implemented by all adapters"""
        pass
    
    @abstractmethod
    async def describe_images(self, images: List, model: str, prompt: str = "Describe this image") -> List[str]:
        """Generate image descriptions - MUST be implemented by all adapters"""
        pass
    
    async def health_check(self) -> bool:
        """Check if the adapter is healthy (loads model if needed)"""
        try:
            await self._ensure_initialized()
            return await self._health_check_implementation()
        except Exception as e:
            print(f"❌ Health check failed for {self.name}: {e}")
            return False
    
    @abstractmethod
    async def _health_check_implementation(self) -> bool:
        """Actual health check implementation (overridden by subclasses)"""
        pass
    
    def _convert_to_langchain_messages(self, messages) -> List[BaseMessage]:
        """Convert OpenAI format messages to LangChain messages"""
        langchain_messages = []
        
        for msg in messages:
            content = msg.content
            if msg.role == 'system':
                langchain_messages.append(SystemMessage(content=content))
            elif msg.role == 'user':
                langchain_messages.append(HumanMessage(content=content))
            elif msg.role == 'assistant':
                langchain_messages.append(AIMessage(content=content))
        
        return langchain_messages
    
    @abstractmethod
    def _convert_to_openai_response(self, langchain_response, request: ChatRequest) -> ChatResponse:
        """Convert LangChain response to OpenAI format"""
        pass
    
    @abstractmethod
    def _format_stream_chunk(self, langchain_chunk, request: ChatRequest) -> str:
        """Format LangChain stream chunk to OpenAI format"""
        pass
    
    def supports_vision(self) -> bool:
        """Check if this adapter supports vision"""
        return self.config.get('capabilities', {}).get('vision', False)
    
    def get_context_window(self) -> int:
        """Get the context window size"""
        return self.config.get('context_window', 4096)
    
    def get_max_tokens(self) -> int:
        """Get max output tokens"""
        return self.config.get('max_tokens', 2048)