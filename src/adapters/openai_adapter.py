from src.core.base_adapter import BaseAdapter
from src.models.requests import ChatRequest
from src.models.responses import ChatResponse, Choice, Message, Usage
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
import os
import uuid
import time
import logging
import json

logger = logging.getLogger(__name__)


class OpenAIAdapter(BaseAdapter):
    """Adapter for OpenAI GPT models using LangChain"""
    
    def initialize(self):
        """Initialize OpenAI client via LangChain"""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        
        self.llm = ChatOpenAI(
            openai_api_key=api_key,
            model=self.config.get('default_model', 'gpt-3.5-turbo'),
            temperature=self.config.get('temperature', 0.7),
            max_tokens=self.config.get('max_tokens', 2048),
            timeout=self.config.get('timeout', 60),
            max_retries=self.config.get('max_retries', 2)
        )
        
        logger.info(f"Initialized OpenAIAdapter with default model: {self.config.get('default_model')}")
    
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
    
    async def _health_check_implementation(self) -> bool:
        """Check OpenAI API availability via LangChain"""
        try:
            from langchain_core.messages import HumanMessage
            test_message = [HumanMessage(content="test")]
            await self.llm.ainvoke(test_message)
            return True
        except Exception as e:
            logger.error(f"OpenAI health check failed: {e}")
            return False