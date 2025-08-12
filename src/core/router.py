from typing import Dict, Optional, Union
from src.core.base_adapter import BaseAdapter
from src.adapters.openai_adapter import OpenAIAdapter
from src.adapters.anthropic_adapter import AnthropicAdapter
from src.adapters.qwen_text_adapter import QwenTextAdapter
from src.adapters.qwen_vision_adapter import QwenVisionAdapter
from src.models.requests import ChatRequest
from src.models.responses import ChatResponse
from src.utils.config_loader import ConfigLoader
from src.core.exceptions import AdapterNotAvailableException
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class LLMRouter:
    """Main router for directing requests to appropriate adapters"""
    
    def __init__(self):
        self.config_loader = ConfigLoader()
        self.routing_config = self.config_loader.load_config('configs/routing.yaml')
        self.adapters_config = self.config_loader.load_config('configs/adapters.yaml')
        self.adapters: Dict[str, BaseAdapter] = {}
        self._initialize_adapters()
    
    def _initialize_adapters(self):
        """Initialize all configured adapters"""
        for adapter_name, adapter_config in self.adapters_config['adapters'].items():
            if not adapter_config.get('enabled', False):
                continue
            
            try:
                adapter_type = adapter_config['type']
                config_file = f"configs/models/{adapter_config['config_file']}"
                
                if adapter_type == 'openai':
                    self.adapters[adapter_name] = OpenAIAdapter(config_file)
                elif adapter_type == 'anthropic':
                    self.adapters[adapter_name] = AnthropicAdapter(config_file)
                elif adapter_type == 'qwen_text':
                    self.adapters[adapter_name] = QwenTextAdapter(config_file)
                elif adapter_type == 'qwen_vision':
                    self.adapters[adapter_name] = QwenVisionAdapter(config_file)
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
        
        try:
            if request.stream:
                return adapter.stream(request)
            else:
                return await adapter.complete(request)
        except Exception as e:
            logger.error(f"Error in adapter {adapter_name}: {e}")
            return await self._fallback(request, exclude=[adapter_name])
    
    def _select_adapter(self, request: ChatRequest) -> str:
        """Select adapter based on routing rules"""
        rules = self.routing_config['rules']
        
        if request.model:
            for rule in rules['explicit_models']:
                if request.model in rule['models']:
                    return rule['adapter']
        
        if self._has_vision_content(request):
            return rules['vision_default']
        
        total_length = sum(len(str(msg.content)) for msg in request.messages)
        
        if total_length > rules['complexity_threshold']:
            return rules['complex_default']
        
        return rules['default_adapter']
    
    def _has_vision_content(self, request: ChatRequest) -> bool:
        """Check if request contains vision content"""
        for msg in request.messages:
            if isinstance(msg.content, list):
                for item in msg.content:
                    if isinstance(item, dict) and item.get('type') == 'image_url':
                        return True
        return False
    
    async def _fallback(self, request: ChatRequest, exclude: list):
        """Fallback to alternative adapter"""
        fallback_chain = self.routing_config['fallback_chain']
        
        for adapter_name in fallback_chain:
            if adapter_name not in exclude and adapter_name in self.adapters:
                try:
                    adapter = self.adapters[adapter_name]
                    return await adapter.complete(request)
                except Exception as e:
                    logger.warning(f"Fallback adapter {adapter_name} failed: {e}")
                    continue
        
        raise Exception("All adapters failed")
    
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all adapters"""
        health_status = {}
        for name, adapter in self.adapters.items():
            health_status[name] = await adapter.health_check()
        return health_status