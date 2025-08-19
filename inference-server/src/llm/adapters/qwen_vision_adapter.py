from ..core.base_adapter import BaseAdapter
from ..models.requests import ChatRequest
from ..models.responses import ChatResponse, Choice, Message, Usage
import aiohttp
import base64
from typing import AsyncGenerator, List, Dict, Any
import uuid
import time
import logging
import json
from PIL import Image
import io
import subprocess
import os
import signal
from pathlib import Path
import asyncio

logger = logging.getLogger(__name__)


class QwenVisionAdapter(BaseAdapter):
    """Adapter for Qwen2.5-VL vision model via vLLM server API"""
    
    def __init__(self, config_path: str):
        super().__init__(config_path)
        # Initialize ALL attributes needed before initialize() from config
        self.server_url = self.config.get('server_url', 'http://localhost:8002')
        self.model_name = self.config.get('model_name', 'Qwen2.5-VL-7B-Instruct-unsloth-bnb-4bit')
        self.model_path = self.config.get('model_path', './models/Qwen2.5-VL-7B-Instruct-unsloth-bnb-4bit')
        self.timeout = self.config.get('timeout', 120)  # Vision models need more time
        self.auto_start = self.config.get('auto_start', True)
        self.vllm_process = None
        
        # Extract port from server URL
        try:
            import urllib.parse
            parsed = urllib.parse.urlparse(self.server_url)
            self.port = parsed.port or 8002
        except:
            self.port = 8002
        
        # Vision-specific settings
        self.max_image_size = self.config.get('max_image_size', 1024)
        self.supported_formats = self.config.get('supported_formats', ['jpg', 'png', 'webp'])
    
    def initialize(self):
        """Initialize vLLM server connection for Qwen2.5-VL"""        
        # vLLM server parameters (only set these during initialization)
        self.default_params = {
            'temperature': self.config.get('temperature', 0.7),
            'max_tokens': self.config.get('max_tokens', 8192),
            'top_p': self.config.get('top_p', 0.9),
        }
        
        logger.info(f"Initialized QwenVisionAdapter with server: {self.server_url}")
        logger.info(f"Auto-start enabled: {self.auto_start}")

    async def _check_server_running(self) -> bool:
        """Check if vLLM vision server is already running"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.server_url}/health", 
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
        except:
            return False

    async def _start_vllm_server(self) -> bool:
        """Start vLLM vision server if not running"""
        if not self.auto_start:
            logger.warning("Auto-start disabled. Please start vLLM server manually.")
            return False
            
        # Check if model exists
        if not Path(self.model_path).exists():
            logger.error(f"Model not found at {self.model_path}")
            return False
            
        logger.info(f"Starting vLLM vision server for {self.model_name} on port {self.port}")
        
        try:
            # Start vLLM server process for vision model
            cmd = [
                "python", "-m", "vllm.entrypoints.openai.api_server",
                "--model", self.model_path,
                "--port", str(self.port),
                "--host", "0.0.0.0",
                "--trust-remote-code",
                "--served-model-name", self.model_name,
                "--max-model-len", "32768",  # Vision models typically have smaller context
                "--quantization", "bitsandbytes",
                "--load-format", "bitsandbytes",
                "--gpu-memory-utilization", "0.8",  # Leave more room for vision processing
                "--dtype", "auto",
                "--disable-log-requests",
                "--max-num-seqs", "128",  # Lower for vision
                "--tensor-parallel-size", "1"
            ]
            
            # Start process in background
            self.vllm_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid  # Create new process group
            )
            
            # Wait for server to start (up to 3 minutes for vision models)
            for i in range(90):  # 90 * 2 = 180 seconds
                await asyncio.sleep(2)
                if await self._check_server_running():
                    logger.info(f"vLLM vision server started successfully on {self.server_url}")
                    return True
                    
            # If we get here, server didn't start
            logger.error("vLLM vision server failed to start within 3 minutes")
            if self.vllm_process:
                os.killpg(os.getpgid(self.vllm_process.pid), signal.SIGTERM)
                self.vllm_process = None
            return False
            
        except Exception as e:
            logger.error(f"Failed to start vLLM vision server: {e}")
            return False

    async def _ensure_server_running(self) -> bool:
        """Ensure vLLM vision server is running, start if needed"""
        if await self._check_server_running():
            return True
            
        if self.auto_start:
            logger.info("vLLM vision server not running, attempting to start...")
            return await self._start_vllm_server()
        else:
            logger.error("vLLM vision server not running and auto-start disabled")
            return False

    def _format_messages_for_vllm(self, messages):
        """Convert OpenAI messages to vLLM server format (supports multimodal)"""
        # vLLM server expects OpenAI-compatible format for vision models
        formatted_messages = []
        
        for msg in messages:
            formatted_messages.append({
                "role": msg.role,
                "content": msg.content  # Keep original format - vLLM server handles multimodal
            })
        
        return formatted_messages
    
    async def complete(self, request: ChatRequest) -> ChatResponse:
        """Process completion request via vLLM vision server"""
        # Ensure server is running
        if not await self._ensure_server_running():
            raise Exception("vLLM vision server is not available")
            
        messages = self._format_messages_for_vllm(request.messages)
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            **self.default_params
        }
        
        # Override with request-specific parameters
        if hasattr(request, 'temperature') and request.temperature is not None:
            payload['temperature'] = request.temperature
        if hasattr(request, 'max_tokens') and request.max_tokens is not None:
            payload['max_tokens'] = request.max_tokens
        if hasattr(request, 'top_p') and request.top_p is not None:
            payload['top_p'] = request.top_p
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.server_url}/v1/chat/completions",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return ChatResponse(**result)
                    else:
                        error_text = await response.text()
                        logger.error(f"vLLM vision server error: {response.status} - {error_text}")
                        raise Exception(f"vLLM vision server error: {response.status}")
                        
        except Exception as e:
            logger.error(f"Failed to call vLLM vision server: {e}")
            raise
    
    async def stream(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """Process streaming request via vLLM vision server"""
        # Ensure server is running
        if not await self._ensure_server_running():
            raise Exception("vLLM vision server is not available")
            
        messages = self._format_messages_for_vllm(request.messages)
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            **self.default_params
        }
        
        # Override with request-specific parameters
        if hasattr(request, 'temperature') and request.temperature is not None:
            payload['temperature'] = request.temperature
        if hasattr(request, 'max_tokens') and request.max_tokens is not None:
            payload['max_tokens'] = request.max_tokens
        if hasattr(request, 'top_p') and request.top_p is not None:
            payload['top_p'] = request.top_p
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.server_url}/v1/chat/completions",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        async for line in response.content:
                            line = line.decode('utf-8').strip()
                            if line.startswith('data: '):
                                yield line + '\n\n'
                    else:
                        error_text = await response.text()
                        logger.error(f"vLLM vision server streaming error: {response.status} - {error_text}")
                        raise Exception(f"vLLM vision server streaming error: {response.status}")
                        
        except Exception as e:
            logger.error(f"Failed to stream from vLLM vision server: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if adapter is healthy without triggering initialization"""
        try:
            return await self._health_check_implementation()
        except Exception as e:
            logger.error(f"❌ Health check failed for {self.name}: {e}")
            return False

    async def _health_check_implementation(self) -> bool:
        """Check if Qwen vision model can be used (server running or can auto-start)"""
        try:
            # Get model path from config (don't rely on initialized attribute)
            model_path = self.config.get('model_path', './models/Qwen2.5-VL-7B-Instruct-unsloth-bnb-4bit')
            
            # First check if server is already running
            server_url = self.config.get('server_url', 'http://localhost:8002')
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{server_url}/health", 
                        timeout=aiohttp.ClientTimeout(total=2)
                    ) as response:
                        if response.status == 200:
                            return True
            except:
                pass  # Server not running, check model files
                
            # For auto-start capability, just check if model files exist
            model_exists = Path(model_path).exists()
            if not model_exists:
                logger.warning(f"Model path does not exist: {model_path}")
                
            return model_exists
                
        except Exception as e:
            logger.error(f"Qwen vision health check failed: {e}")
            return False

    def _convert_to_openai_response(self, langchain_response, request):
        """Not used for vLLM server adapter - responses are already in OpenAI format"""
        pass
    
    def _format_stream_chunk(self, langchain_chunk, request):
        """Not used for vLLM server adapter - chunks are already in OpenAI format"""  
        pass

    def cleanup(self):
        """Clean up vLLM vision server process"""
        if self.vllm_process:
            try:
                logger.info("Stopping vLLM vision server...")
                os.killpg(os.getpgid(self.vllm_process.pid), signal.SIGTERM)
                self.vllm_process.wait(timeout=10)
                logger.info("vLLM vision server stopped")
            except Exception as e:
                logger.error(f"Error stopping vLLM vision server: {e}")
                try:
                    os.killpg(os.getpgid(self.vllm_process.pid), signal.SIGKILL)
                except:
                    pass
            finally:
                self.vllm_process = None
