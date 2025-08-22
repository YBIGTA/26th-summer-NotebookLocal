from ..core.base_adapter import BaseAdapter
from ..models.requests import ChatRequest
from ..models.responses import ChatResponse, Choice, Message, Usage
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage
from typing import List
from PIL import Image
import os
import uuid
import time
import logging
import json

logger = logging.getLogger(__name__)


class AnthropicAdapter(BaseAdapter):
    """Stateless adapter for Anthropic Claude models"""
    
    def initialize(self):
        """Initialize Anthropic client"""
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")
        
        # Store API key for dynamic model creation
        self.api_key = api_key
        
        logger.info("Initialized AnthropicAdapter (stateless)")
    
    def _load_model_config(self, model_name: str) -> dict:
        """Load specific model configuration"""
        from ..utils.config_loader import ConfigLoader
        config_loader = ConfigLoader()
        try:
            return config_loader.load_config(f'configs/models/anthropic/{model_name}.yaml')
        except Exception as e:
            logger.error(f"Failed to load config for {model_name}: {e}")
            raise
    
    def _get_request_parameters(self, request: ChatRequest, model_config: dict, workflow: str = "qa_workflow") -> dict:
        """Get parameters for request from model config - NO FALLBACKS"""
        # Start with base model parameters - NO DEFAULTS
        params = {}
        
        # Required parameters must be in config
        if 'temperature' not in model_config:
            raise ValueError(f"temperature not configured for model")
        if 'max_tokens' not in model_config:
            raise ValueError(f"max_tokens not configured for model")
        
        params['temperature'] = model_config['temperature']
        params['max_tokens'] = model_config['max_tokens']
        
        # Override with workflow-specific parameters if available
        workflow_config = model_config.get('workflows', {}).get(workflow, {})
        workflow_params = workflow_config.get('parameters', {})
        params.update(workflow_params)
        
        # Finally, override with any request-specific parameters
        if hasattr(request, 'temperature') and request.temperature is not None:
            params['temperature'] = request.temperature
        if hasattr(request, 'max_tokens') and request.max_tokens is not None:
            params['max_tokens'] = request.max_tokens
            
        return params
    
    def _convert_to_openai_response(self, langchain_response: AIMessage, request: ChatRequest) -> ChatResponse:
        """Convert LangChain response to OpenAI format"""
        return ChatResponse(
            id=str(uuid.uuid4()),
            model=request.model or self.config.get('default_model', 'claude-3-5-sonnet-20241022'),
            created=int(time.time()),
            choices=[
                Choice(
                    index=0,
                    message=Message(
                        role="assistant",
                        content=langchain_response.content
                    ),
                    finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=0,  # LangChain doesn't provide token counts by default
                completion_tokens=0,
                total_tokens=0
            )
        )
    
    def _format_stream_chunk(self, langchain_chunk: AIMessage, request: ChatRequest) -> str:
        """Format LangChain stream chunk to OpenAI format"""
        chunk_data = {
            "id": str(uuid.uuid4()),
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": request.model or self.config.get('default_model', 'claude-3-5-sonnet-20241022'),
            "choices": [{
                "index": 0,
                "delta": {"content": langchain_chunk.content},
                "finish_reason": None
            }]
        }
        return f"data: {json.dumps(chunk_data)}\n\n"
    
    def embed(self, texts: List[str], model: str) -> List[List[float]]:
        """Generate embeddings - not supported by Anthropic adapter"""
        model_config = self._load_model_config(model)
        if not model_config.get('capabilities', {}).get('embeddings', False):
            raise NotImplementedError(f"Anthropic model {model} does not support embeddings")
        raise NotImplementedError("Anthropic embeddings not yet implemented")
    
    async def describe_images(self, images: List[Image.Image], model: str, prompt: str = "Describe this image") -> List[str]:
        """Generate descriptions for images using Anthropic Vision API"""
        model_config = self._load_model_config(model)
        if not model_config.get('capabilities', {}).get('vision', False):
            raise NotImplementedError(f"Anthropic model {model} does not support vision")
            
        descriptions = []
        for img in images:
            try:
                raise NotImplementedError("Anthropic vision API not yet implemented")
            except Exception as e:
                logger.error(f"Anthropic vision processing failed: {e}")
                descriptions.append(f"[Image processing failed: {str(e)}]")
        return descriptions
    
    async def complete(self, request: ChatRequest) -> ChatResponse:
        """Process completion request using Anthropic API"""
        try:
            # Get model name from request - NO DEFAULTS
            if not request.model:
                raise ValueError("Model name is required in request")
            model_name = request.model
            
            # Load model-specific config
            model_config = self._load_model_config(model_name)
            
            # Verify model supports chat
            if not model_config.get('capabilities', {}).get('chat', False):
                raise ValueError(f"Model {model_name} does not support chat")
            
            # Get parameters from model config with request overrides
            params = self._get_request_parameters(request, model_config)
            
            # Create LangChain client dynamically for this request
            llm = ChatAnthropic(
                anthropic_api_key=self.api_key,
                model=model_name,
                **params
            )
            
            # Convert messages to LangChain format
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
            messages = []
            for msg in request.messages:
                if msg.role == "user":
                    messages.append(HumanMessage(content=msg.content))
                elif msg.role == "system":
                    messages.append(SystemMessage(content=msg.content))
                elif msg.role == "assistant":
                    messages.append(AIMessage(content=msg.content))
            
            # Get response
            response = await llm.ainvoke(messages)
            
            # Convert to our ChatResponse format
            return ChatResponse(
                id=str(uuid.uuid4()),
                model=model_name,
                created=int(time.time()),
                choices=[
                    Choice(
                        index=0,
                        message=Message(
                            role="assistant",
                            content=response.content
                        ),
                        finish_reason="stop"
                    )
                ],
                usage=Usage(
                    prompt_tokens=0,  # LangChain doesn't provide token counts by default
                    completion_tokens=0,
                    total_tokens=0
                )
            )
            
        except Exception as e:
            logger.error(f"Anthropic completion failed for {model_name}: {e}")
            raise
    
    async def stream(self, request: ChatRequest):
        """Process streaming request using Anthropic API"""
        try:
            # Get model name from request - NO DEFAULTS  
            if not request.model:
                raise ValueError("Model name is required in request")
            model_name = request.model
            
            # Load model-specific config
            model_config = self._load_model_config(model_name)
            
            # Verify model supports chat and streaming
            if not model_config.get('capabilities', {}).get('chat', False):
                raise ValueError(f"Model {model_name} does not support chat")
            if not model_config.get('capabilities', {}).get('streaming', False):
                raise ValueError(f"Model {model_name} does not support streaming")
            
            # Get parameters from model config with request overrides
            params = self._get_request_parameters(request, model_config)
            
            # Create LangChain client dynamically for this request
            llm = ChatAnthropic(
                anthropic_api_key=self.api_key,
                model=model_name,
                **params
            )
            
            # Convert messages to LangChain format
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
            messages = []
            for msg in request.messages:
                if msg.role == "user":
                    messages.append(HumanMessage(content=msg.content))
                elif msg.role == "system":
                    messages.append(SystemMessage(content=msg.content))
                elif msg.role == "assistant":
                    messages.append(AIMessage(content=msg.content))
            
            # Stream response
            async for chunk in llm.astream(messages):
                if chunk.content:
                    chunk_data = {
                        "id": str(uuid.uuid4()),
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model_name,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": chunk.content},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(chunk_data)}\n\n"
            
            # End stream
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"Anthropic streaming failed for {model_name}: {e}")
            raise
    
    async def _health_check_implementation(self) -> bool:
        """Check Anthropic API availability via LangChain"""
        try:
            from langchain_core.messages import HumanMessage
            test_message = [HumanMessage(content="test")]
            await self.llm.ainvoke(test_message)
            return True
        except Exception as e:
            logger.error(f"Anthropic health check failed: {e}")
            return False