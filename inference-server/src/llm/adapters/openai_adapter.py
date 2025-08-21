from ..core.base_adapter import BaseAdapter
from ..models.requests import ChatRequest
from ..models.responses import ChatResponse, Choice, Message, Usage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import AIMessage
from openai import OpenAI
from typing import List
import base64
import io
from PIL import Image
import os
import uuid
import time
import logging
import json

logger = logging.getLogger(__name__)


class OpenAIAdapter(BaseAdapter):
    """Stateless adapter for OpenAI models - loads configs dynamically"""
    
    def initialize(self):
        """Initialize OpenAI client"""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        
        # Initialize OpenAI client for all operations
        self.openai_client = OpenAI(api_key=api_key)
        
        logger.info("Initialized OpenAIAdapter (stateless)")
    
    def _convert_to_openai_response(self, langchain_response: AIMessage, request: ChatRequest) -> ChatResponse:
        """Convert LangChain response to OpenAI format"""
        return ChatResponse(
            id=str(uuid.uuid4()),
            model=request.model or self.config.get('default_model', 'gpt-3.5-turbo'),
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
            "model": request.model or self.config.get('default_model', 'gpt-3.5-turbo'),
            "choices": [{
                "index": 0,
                "delta": {"content": langchain_chunk.content},
                "finish_reason": None
            }]
        }
        return f"data: {json.dumps(chunk_data)}\n\n"
    
    def _load_model_config(self, model_name: str) -> dict:
        """Load specific model configuration"""
        from ..utils.config_loader import ConfigLoader
        config_loader = ConfigLoader()
        try:
            return config_loader.load_config(f'configs/models/openai/{model_name}.yaml')
        except Exception as e:
            logger.error(f"Failed to load config for {model_name}: {e}")
            raise

    def embed(self, texts: List[str], model: str) -> List[List[float]]:
        """Generate embeddings using OpenAI embedding model"""
        try:
            # Load model-specific config
            model_config = self._load_model_config(model)
            
            # Verify this model supports embeddings
            if not model_config.get('capabilities', {}).get('embeddings', False):
                raise ValueError(f"Model {model} does not support embeddings")
            
            api_key = os.getenv('OPENAI_API_KEY')
            embeddings_client = OpenAIEmbeddings(
                model=model,
                openai_api_key=api_key
            )
            return embeddings_client.embed_documents(texts)
        except Exception as e:
            logger.error(f"OpenAI embedding failed for {model}: {e}")
            raise
    
    async def describe_images(self, images: List[Image.Image], model: str, prompt: str = "Describe this image") -> List[str]:
        """Generate descriptions for images using OpenAI Vision API"""
        try:
            # Load model-specific config
            model_config = self._load_model_config(model)
            
            # Verify this model supports vision
            if not model_config.get('capabilities', {}).get('vision', False):
                raise ValueError(f"Model {model} does not support vision")
        except Exception as e:
            logger.error(f"Model config error for {model}: {e}")
            # Continue with default settings for now
            
        descriptions = []
        
        for img in images:
            try:
                # Convert PIL Image to base64
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_bytes = buffered.getvalue()
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                
                # Call OpenAI Vision API
                response = self.openai_client.chat.completions.create(
                    model=model,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                        ]
                    }],
                    max_tokens=500
                )
                
                description = response.choices[0].message.content
                descriptions.append(description)
                
            except Exception as e:
                logger.error(f"OpenAI vision processing failed for {model}: {e}")
                descriptions.append(f"[Image processing failed: {str(e)}]")
        
        return descriptions
    
    async def complete(self, request: ChatRequest) -> ChatResponse:
        """Process completion request using OpenAI API"""
        # Get model name from request - NO DEFAULTS
        if not request.model:
            raise ValueError("Model name is required in request")
        model_name = request.model
        
        try:
            # Load model-specific config
            model_config = self._load_model_config(model_name)
            
            # Verify model supports chat
            if not model_config.get('capabilities', {}).get('chat', False):
                raise ValueError(f"Model {model_name} does not support chat")
            
            # Convert messages to OpenAI format
            messages = []
            for msg in request.messages:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # Create completion
            response = self.openai_client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=getattr(request, 'temperature', 0.7),
                max_tokens=getattr(request, 'max_tokens', 2048),
                top_p=getattr(request, 'top_p', 1.0)
            )
            
            # Convert to our ChatResponse format
            return ChatResponse(
                id=response.id,
                model=model_name,
                created=response.created,
                choices=[
                    Choice(
                        index=choice.index,
                        message=Message(
                            role=choice.message.role,
                            content=choice.message.content
                        ),
                        finish_reason=choice.finish_reason
                    ) for choice in response.choices
                ],
                usage=Usage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens
                )
            )
            
        except Exception as e:
            logger.error(f"OpenAI completion failed for {model_name}: {e}")
            raise
    
    async def stream(self, request: ChatRequest):
        """Process streaming request using OpenAI API"""
        # Get model name from request - NO DEFAULTS
        if not request.model:
            raise ValueError("Model name is required in request")
        model_name = request.model
        
        try:
            # Load model-specific config
            model_config = self._load_model_config(model_name)
            
            # Verify model supports chat and streaming
            if not model_config.get('capabilities', {}).get('chat', False):
                raise ValueError(f"Model {model_name} does not support chat")
            if not model_config.get('capabilities', {}).get('streaming', False):
                raise ValueError(f"Model {model_name} does not support streaming")
            
            # Convert messages to OpenAI format
            messages = []
            for msg in request.messages:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # Create streaming completion
            stream = self.openai_client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=getattr(request, 'temperature', 0.7),
                max_tokens=getattr(request, 'max_tokens', 2048),
                top_p=getattr(request, 'top_p', 1.0),
                stream=True
            )
            
            # Yield chunks in OpenAI format
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    chunk_data = {
                        "id": chunk.id,
                        "object": "chat.completion.chunk",
                        "created": chunk.created,
                        "model": model_name,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": chunk.choices[0].delta.content},
                            "finish_reason": chunk.choices[0].finish_reason
                        }]
                    }
                    yield f"data: {json.dumps(chunk_data)}\n\n"
            
            # End stream
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"OpenAI streaming failed for {model_name}: {e}")
            raise
    
    async def _health_check_implementation(self) -> bool:
        """Check OpenAI API availability"""
        try:
            # Just check if we have API key - no actual API call
            if not os.getenv('OPENAI_API_KEY'):
                return False
            return True
        except Exception as e:
            logger.error(f"OpenAI health check failed: {e}")
            return False