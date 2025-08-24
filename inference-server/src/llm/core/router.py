from typing import Dict, Optional, Union, List
from .base_adapter import BaseAdapter
from ..adapters.openai_adapter import OpenAIAdapter
from ..adapters.anthropic_adapter import AnthropicAdapter
from ..adapters.qwen_adapter import QwenAdapter
from ..models.requests import ChatRequest
from ..models.responses import ChatResponse
from ..utils.config_loader import ConfigLoader
from .exceptions import AdapterNotAvailableException
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class LLMRouter:
    """Universal router for directing chat, embedding, and vision requests to appropriate adapters"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self.config_loader = ConfigLoader()
        self.routing_config = self.config_loader.load_config('configs/routing.yaml')
        self.adapters_config = self.config_loader.load_config('configs/adapters.yaml')
        self.adapters: Dict[str, BaseAdapter] = {}
        self._initialize_adapters()
        self._initialized = True
    
    @classmethod
    def get_instance(cls):
        """Get singleton instance."""
        return cls()
    
    def _initialize_adapters(self):
        """Initialize all configured adapters"""
        for adapter_name, adapter_config in self.adapters_config['adapters'].items():
            if not adapter_config.get('enabled', False):
                continue
            
            try:
                adapter_type = adapter_config['type']
                
                if adapter_type == 'openai':
                    adapter = OpenAIAdapter(None)
                    adapter.initialize()
                    self.adapters[adapter_name] = adapter
                elif adapter_type == 'anthropic':
                    adapter = AnthropicAdapter(None)
                    adapter.initialize()
                    self.adapters[adapter_name] = adapter
                elif adapter_type == 'qwen':
                    adapter = QwenAdapter(None)
                    adapter.initialize()
                    self.adapters[adapter_name] = adapter
                else:
                    logger.error(f"Unknown adapter type: {adapter_type}")
                    continue
                
                logger.info(f"Initialized adapter: {adapter_name}")
            except Exception as e:
                logger.error(f"Failed to initialize adapter {adapter_name}: {e}")
    
    async def route(self, request: ChatRequest) -> Union[ChatResponse, AsyncGenerator[str, None]]:
        """Route request to appropriate adapter"""
        adapter_name = self._select_adapter(request)
        
        if adapter_name not in self.adapters:
            raise AdapterNotAvailableException(f"Adapter {adapter_name} not available")
        
        adapter = self.adapters[adapter_name]
        
        # If no model specified in request, use the default from routing config
        if not request.model:
            if self._has_vision_content(request):
                request.model = self.routing_config['rules']['vision_default']
            else:
                request.model = self.routing_config['rules']['chat_default']
        
        try:
            if request.stream:
                return adapter.stream(request)
            else:
                return await adapter.complete(request)
        except Exception as e:
            logger.error(f"Error in adapter {adapter_name}: {e}")
            raise AdapterNotAvailableException(f"Adapter {adapter_name} failed: {e}")
    
    def _select_adapter(self, request: ChatRequest) -> str:
        """Select adapter based on routing rules"""
        rules = self.routing_config['rules']
        
        if request.model:
            for rule in rules['explicit_models']:
                if request.model in rule['models']:
                    return rule['adapter']
        
        if self._has_vision_content(request):
            vision_model = rules['vision_default']
            return self._get_adapter_for_model(vision_model)
        
        # Default to chat model for all other requests
        chat_model = rules['chat_default']
        return self._get_adapter_for_model(chat_model)
    
    def _has_vision_content(self, request: ChatRequest) -> bool:
        """Check if request contains vision content"""
        for msg in request.messages:
            if isinstance(msg.content, list):
                for item in msg.content:
                    if isinstance(item, dict) and item.get('type') == 'image_url':
                        return True
        return False
    
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using configured embedding model"""
        from typing import List
        
        # Get default embedding model from routing config
        embedding_model = self.routing_config['rules']['embedding_default']
        
        # Find the adapter for this model
        adapter_name = self._get_adapter_for_model(embedding_model)
        
        if adapter_name not in self.adapters:
            raise AdapterNotAvailableException(f"Embedding adapter {adapter_name} not available")
        
        adapter = self.adapters[adapter_name]
        
        # For now, use the adapter's embedding capability
        # This will need to be implemented in each adapter
        if hasattr(adapter, 'embed'):
            return adapter.embed(texts, embedding_model)
        else:
            raise AdapterNotAvailableException(f"Adapter {adapter_name} does not support embeddings")
    
    async def vision(self, images: List, prompt: str = "Describe this image") -> List[str]:
        """Generate descriptions for images using configured vision model"""
        from typing import List
        
        # Get default vision model from routing config
        vision_model = self.routing_config['rules']['vision_default']
        
        # Find the adapter for this model
        adapter_name = self._get_adapter_for_model(vision_model)
        
        if adapter_name not in self.adapters:
            raise AdapterNotAvailableException(f"Vision adapter {adapter_name} not available")
        
        adapter = self.adapters[adapter_name]
        
        # For now, use the adapter's vision capability
        # This will need to be implemented in each adapter
        if hasattr(adapter, 'describe_images'):
            return await adapter.describe_images(images, vision_model, prompt)
        else:
            raise AdapterNotAvailableException(f"Adapter {adapter_name} does not support vision")
    
    def _get_adapter_for_model(self, model_name: str) -> str:
        """Get adapter name for a specific model"""
        rules = self.routing_config['rules']
        
        for rule in rules['explicit_models']:
            if model_name in rule['models']:
                return rule['adapter']
        
        raise AdapterNotAvailableException(f"No adapter found for model {model_name}")
    
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all adapters"""
        health_status = {}
        for name, adapter in self.adapters.items():
            health_status[name] = await adapter.health_check()
        return health_status