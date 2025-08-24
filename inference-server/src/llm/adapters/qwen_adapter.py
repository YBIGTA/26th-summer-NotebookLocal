from ..core.base_adapter import BaseAdapter
from ..models.requests import ChatRequest
from ..models.responses import ChatResponse, Choice, Message, Usage
import aiohttp
import asyncio
from typing import AsyncGenerator, List, Optional
import uuid
import time
import logging
import json
import subprocess
import os
import signal
from pathlib import Path
import base64
import io
from PIL import Image

logger = logging.getLogger(__name__)


class QwenAdapter(BaseAdapter):
    """Stateless adapter for all Qwen models (text and vision) via vLLM server"""
    
    def __init__(self, config_path: Optional[str] = None):
        super().__init__(config_path)
        self.vllm_process = None
        
    def initialize(self):
        """Initialize Qwen adapter"""        
        logger.info("Initialized QwenAdapter (stateless)")

    async def _check_server_running(self, port: int) -> bool:
        """Check if vLLM server is running on specified port"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://localhost:{port}/health", 
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
        except:
            return False

    async def _start_vllm_server(self, model_config: dict) -> bool:
        """Start vLLM server for specific model"""
        # Required fields - NO FALLBACKS
        if 'name' not in model_config:
            raise ValueError("Model name not configured")
        if 'server' not in model_config or 'port' not in model_config['server']:
            raise ValueError("Server port not configured for model")
        if 'model_path' not in model_config:
            raise ValueError("Model path not configured")
            
        model_name = model_config['name']
        port = model_config['server']['port']
        model_path = model_config['model_path']
        auto_start = model_config.get('auto_start', False)  # This can have fallback as it's optional
        
        logger.info(f"🚀 Starting vLLM server for {model_name}")
        
        if not auto_start:
            logger.warning("❌ Auto-start disabled for this model")
            return False
            
        # Check if model exists
        if not Path(model_path).exists():
            logger.error(f"❌ Model not found at {model_path}")
            return False
            
        try:
            # Build command from model config - NO FALLBACKS
            vllm_config = model_config.get('vllm_config', {})
            if not vllm_config:
                raise ValueError(f"vLLM configuration not found for model {model_name}")
                
            cmd = [
                "python", "-m", "vllm.entrypoints.openai.api_server",
                "--model", model_path,
                "--port", str(port),
                "--host", model_config.get('server', {}).get('host', '127.0.0.1'),  # Optional with fallback
                "--served-model-name", model_config['served_model_name'],
                "--max-model-len", str(vllm_config['max_model_len']),
                "--quantization", vllm_config['quantization'],
                "--load-format", vllm_config['load_format'],
                "--gpu-memory-utilization", str(vllm_config['gpu_memory_utilization']),
                "--dtype", vllm_config['dtype'],
                "--max-num-seqs", str(vllm_config['max_num_seqs']),
                "--tensor-parallel-size", str(vllm_config['tensor_parallel_size'])
            ]
            
            # Add boolean flags from config
            if vllm_config.get('trust_remote_code'):
                cmd.append("--trust-remote-code")
            if vllm_config.get('disable_log_requests'):
                cmd.append("--disable-log-requests")
            if vllm_config.get('disable_custom_all_reduce'):
                cmd.append("--disable-custom-all-reduce")
            if vllm_config.get('enforce_eager'):
                cmd.append("--enforce-eager")
            
            # Set environment variables
            env = os.environ.copy()
            env_vars = model_config.get('environment', {})
            for key, value in env_vars.items():
                env[key] = str(value)
            
            # Start process
            logger.info(f"📦 Starting vLLM process for {model_name}")
            self.vllm_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                preexec_fn=os.setsid
            )
            
            # Wait for server to start
            logger.info("⏳ Waiting for server to start...")
            for i in range(60):  # 2 minutes
                await asyncio.sleep(2)
                
                if await self._check_server_running(port):
                    logger.info(f"✅ vLLM server started for {model_name}")
                    return True
                
                if self.vllm_process.poll() is not None:
                    logger.error(f"❌ vLLM process exited for {model_name}")
                    return False
                    
            logger.error(f"❌ vLLM server failed to start for {model_name}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to start vLLM server for {model_name}: {e}")
            return False

    async def _ensure_server_running(self, model_config: dict) -> bool:
        """Ensure vLLM server is running for specific model"""
        if 'server' not in model_config or 'port' not in model_config['server']:
            raise ValueError("Server port not configured for model")
        port = model_config['server']['port']
        
        if await self._check_server_running(port):
            return True
            
        return await self._start_vllm_server(model_config)
    
    def _format_messages_for_vllm(self, messages):
        """Convert OpenAI messages to vLLM server format"""
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "role": msg.role,
                "content": msg.content
            })
        return formatted_messages
    
    async def complete(self, request: ChatRequest) -> ChatResponse:
        """Process completion request via vLLM server"""
        # Get model-specific config
        model_name = getattr(request, 'model', 'qwen-default')
        model_config = self._load_model_config(model_name)
        
        # Ensure server is running
        if not await self._ensure_server_running(model_config):
            raise Exception(f"vLLM server is not available for {model_name}")
            
        messages = self._format_messages_for_vllm(request.messages)
        
        if 'server' not in model_config or 'port' not in model_config['server']:
            raise ValueError(f"Server port not configured for model {model_name}")
        if 'served_model_name' not in model_config:
            raise ValueError(f"Served model name not configured for {model_name}")
        if 'temperature' not in model_config:
            raise ValueError(f"Temperature not configured for {model_name}")
        if 'max_tokens' not in model_config:
            raise ValueError(f"Max tokens not configured for {model_name}")
        if 'top_p' not in model_config:
            raise ValueError(f"Top p not configured for {model_name}")
            
        port = model_config['server']['port']
        served_name = model_config['served_model_name']
        
        payload = {
            "model": served_name,
            "messages": messages,
            "temperature": getattr(request, 'temperature', None) or model_config['temperature'],
            "max_tokens": getattr(request, 'max_tokens', None) or model_config['max_tokens'],
            "top_p": getattr(request, 'top_p', None) or model_config['top_p']
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://localhost:{port}/v1/chat/completions",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=model_config.get('timeout', 60))
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return ChatResponse(**result)
                    else:
                        error_text = await response.text()
                        logger.error(f"vLLM server error: {response.status} - {error_text}")
                        raise Exception(f"vLLM server error: {response.status}")
                        
        except Exception as e:
            logger.error(f"Failed to call vLLM server: {e}")
            raise
    
    async def stream(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """Process streaming request via vLLM server"""
        # Get model-specific config
        model_name = getattr(request, 'model', 'qwen-default')
        model_config = self._load_model_config(model_name)
        
        # Ensure server is running
        if not await self._ensure_server_running(model_config):
            raise Exception(f"vLLM server is not available for {model_name}")
            
        messages = self._format_messages_for_vllm(request.messages)
        port = model_config.get('port')
        served_name = model_config.get('served_model_name', model_name)
        
        # Get parameters from request or validate model config - NO FALLBACKS
        temperature = request.temperature
        max_tokens = request.max_tokens
        top_p = request.top_p
        
        # If not provided in request, must be in model config
        if temperature is None:
            if 'temperature' not in model_config:
                raise ValueError(f"temperature not configured for model {model_name}")
            temperature = model_config['temperature']
        
        if max_tokens is None:
            if 'max_tokens' not in model_config:
                raise ValueError(f"max_tokens not configured for model {model_name}")
            max_tokens = model_config['max_tokens']
            
        if top_p is None:
            if 'top_p' not in model_config:
                raise ValueError(f"top_p not configured for model {model_name}")
            top_p = model_config['top_p']
        
        payload = {
            "model": served_name,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://localhost:{port}/v1/chat/completions",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=model_config.get('timeout', 60))
                ) as response:
                    if response.status == 200:
                        async for line in response.content:
                            line = line.decode('utf-8').strip()
                            if line.startswith('data: '):
                                yield line + '\\n\\n'
                    else:
                        error_text = await response.text()
                        logger.error(f"vLLM server streaming error: {response.status} - {error_text}")
                        raise Exception(f"vLLM server streaming error: {response.status}")
                        
        except Exception as e:
            logger.error(f"Failed to stream from vLLM server: {e}")
            raise
    
    def _load_model_config(self, model_name: str) -> dict:
        """Load configuration for specific model"""
        from ..utils.config_loader import ConfigLoader
        config_loader = ConfigLoader()
        try:
            return config_loader.load_config(f'configs/models/qwen/{model_name}.yaml')
        except Exception as e:
            logger.error(f"Failed to load config for {model_name}: {e}")
            raise
    
    def embed(self, texts: List[str], model: str) -> List[List[float]]:
        """Generate embeddings using Qwen embedding model"""
        # Load embedding model config
        from ..utils.config_loader import ConfigLoader
        config_loader = ConfigLoader()
        model_config = config_loader.load_config(f'configs/models/qwen/{model}.yaml')
        
        if not model_config.get('capabilities', {}).get('embeddings', False):
            raise NotImplementedError(f"Model {model} does not support embeddings")
        
        port = model_config.get('server', {}).get('port', 8003)
        served_name = model_config.get('served_model_name', model)
        
        # For now, raise NotImplementedError as vLLM embedding support is complex
        # This would need specialized vLLM embedding server setup
        raise NotImplementedError(f"Qwen embedding via vLLM not yet implemented for {model}")
    
    async def describe_images(self, images: List[Image.Image], model: str, prompt: str = "Describe this image") -> List[str]:
        """Generate descriptions for images using Qwen vision model"""
        # Load vision model config
        from ..utils.config_loader import ConfigLoader
        config_loader = ConfigLoader()
        model_config = config_loader.load_config(f'configs/models/qwen/{model}.yaml')
        
        if not model_config.get('capabilities', {}).get('vision', False):
            raise NotImplementedError(f"Model {model} does not support vision")
        
        # Ensure vision server is running
        if not await self._ensure_server_running(model_config):
            raise Exception(f"vLLM server is not available for vision model {model}")
        
        port = model_config.get('server', {}).get('port', 8002)
        served_name = model_config.get('served_model_name', model)
        
        descriptions = []
        for img in images:
            try:
                # Convert PIL Image to base64
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_bytes = buffered.getvalue()
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                
                # Get vision parameters from model config - NO FALLBACKS
                if 'max_tokens' not in model_config:
                    raise ValueError(f"max_tokens not configured for vision model {model}")
                if 'temperature' not in model_config:
                    raise ValueError(f"temperature not configured for vision model {model}")
                
                # Create OpenAI-compatible vision request
                payload = {
                    "model": served_name,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                        ]
                    }],
                    "max_tokens": model_config['max_tokens'],
                    "temperature": model_config['temperature']
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"http://localhost:{port}/v1/chat/completions",
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=60)
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            description = result['choices'][0]['message']['content']
                            descriptions.append(description)
                        else:
                            error_text = await response.text()
                            logger.error(f"Qwen vision error: {response.status} - {error_text}")
                            descriptions.append(f"[Vision processing failed: {response.status}]")
                
            except Exception as e:
                logger.error(f"Qwen vision processing failed: {e}")
                descriptions.append(f"[Image processing failed: {str(e)}]")
        
        return descriptions
    
    async def health_check(self) -> bool:
        """Check if Qwen provider is healthy"""
        try:
            # Provider-level health check
            return True  # Provider is always available
        except Exception as e:
            logger.error(f"❌ Qwen provider health check failed: {e}")
            return False

    def cleanup(self):
        """Clean up vLLM server processes"""
        if self.vllm_process:
            try:
                logger.info("Stopping vLLM server...")
                os.killpg(os.getpgid(self.vllm_process.pid), signal.SIGTERM)
                self.vllm_process.wait(timeout=10)
                logger.info("vLLM server stopped")
            except Exception as e:
                logger.error(f"Error stopping vLLM server: {e}")
                try:
                    os.killpg(os.getpgid(self.vllm_process.pid), signal.SIGKILL)
                except:
                    pass
            finally:
                self.vllm_process = None