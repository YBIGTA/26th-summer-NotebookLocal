from src.core.base_adapter import BaseAdapter
from src.models.requests import ChatRequest
from src.models.responses import ChatResponse, Choice, Message, Usage
import aiohttp
import asyncio
from typing import AsyncGenerator
import uuid
import time
import logging
import json
import subprocess
import os
import signal
from pathlib import Path

logger = logging.getLogger(__name__)


class QwenTextAdapter(BaseAdapter):
    """Adapter for Qwen3-30B text model via vLLM server API"""
    
    def __init__(self, config_path: str):
        super().__init__(config_path)
        
        # Get vLLM settings from centralized config
        self.vllm_settings = self.config.get('vllm_settings', {})
        
        # Initialize attributes from centralized vllm_settings
        self.port = self.vllm_settings.get('port', 8001)
        self.server_url = f"http://localhost:{self.port}"  # Auto-construct from port
        self.model_name = self.vllm_settings.get('served_model_name', 'Qwen3-14B-unsloth-bnb-4bit')
        self.model_path = self.vllm_settings.get('model_path', './models/Qwen3-14B-unsloth-bnb-4bit')
        self.timeout = self.config.get('timeout', 60)
        self.auto_start = self.config.get('auto_start', True)
        self.vllm_process = None
        
        # Initialize model parameters from centralized config (needed early)
        model_params = self.config.get('model_params', {})
        self.default_params = {
            'temperature': model_params.get('temperature', 0.6),
            'max_tokens': model_params.get('max_tokens', 8192),
            'top_p': model_params.get('top_p', 0.95),
            'top_k': model_params.get('top_k', 20),
            'repetition_penalty': model_params.get('repetition_penalty', 1.1),
            'frequency_penalty': model_params.get('frequency_penalty', 0.0),
            'presence_penalty': model_params.get('presence_penalty', 0.0),
        }
    
    def initialize(self):
        """Initialize vLLM server connection for Qwen3-14B"""        
        logger.info(f"Initialized QwenTextAdapter with server: {self.server_url}")
        logger.info(f"Auto-start enabled: {self.auto_start}")
        logger.info(f"Using centralized vLLM settings: {len(self.vllm_settings)} parameters")

    async def _check_server_running(self) -> bool:
        """Check if vLLM server is already running"""
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
        """Start vLLM server if not running"""
        logger.info(f"🚀 _start_vllm_server called - auto_start: {self.auto_start}")
        
        if not self.auto_start:
            logger.warning("❌ Auto-start disabled. Please start vLLM server manually.")
            return False
            
        # Check if model exists
        logger.info(f"📁 Checking model path: {self.model_path}")
        if not Path(self.model_path).exists():
            logger.error(f"❌ Model not found at {self.model_path}")
            return False
        else:
            logger.info(f"✅ Model found at {self.model_path}")
            
        logger.info(f"🔧 Starting vLLM server for {self.model_name} on port {self.port}")
        
        try:
            # Build vLLM command from centralized settings
            cmd = [
                "python", "-m", "vllm.entrypoints.openai.api_server",
                "--model", self.vllm_settings.get('model_path', self.model_path),
                "--port", str(self.vllm_settings.get('port', self.port)),
                "--host", self.vllm_settings.get('host', '0.0.0.0'),
                "--served-model-name", self.vllm_settings.get('served_model_name', self.model_name),
                "--max-model-len", str(self.vllm_settings.get('max_model_len', 8192)),
                "--quantization", self.vllm_settings.get('quantization', 'bitsandbytes'),
                "--load-format", self.vllm_settings.get('load_format', 'bitsandbytes'),
                "--gpu-memory-utilization", str(self.vllm_settings.get('gpu_memory_utilization', 0.6)),
                "--dtype", self.vllm_settings.get('dtype', 'auto'),
                "--max-num-seqs", str(self.vllm_settings.get('max_num_seqs', 64)),
                "--tensor-parallel-size", str(self.vllm_settings.get('tensor_parallel_size', 1))
            ]
            
            # Add optional flags
            if self.vllm_settings.get('trust_remote_code', True):
                cmd.append("--trust-remote-code")
            if self.vllm_settings.get('disable_log_requests', True):
                cmd.append("--disable-log-requests")
            
            logger.info(f"💻 Command: {' '.join(cmd)}")
            
            # Set environment variables from centralized config
            env = os.environ.copy()
            env_vars = self.vllm_settings.get('environment', {})
            for key, value in env_vars.items():
                env[key] = str(value)
            
            # Start process in background
            logger.info("📦 Starting subprocess...")
            self.vllm_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                preexec_fn=os.setsid  # Create new process group
            )
            logger.info(f"🔄 Process started with PID: {self.vllm_process.pid}")
            
            # Wait for server to start (up to 2 minutes)
            logger.info("⏳ Waiting for server to start (up to 2 minutes)...")
            for i in range(60):  # 60 * 2 = 120 seconds
                await asyncio.sleep(2)
                logger.info(f"🔍 Check {i+1}/60 - Testing server connection...")
                
                if await self._check_server_running():
                    logger.info(f"✅ vLLM server started successfully on {self.server_url}")
                    return True
                
                # Check if process is still running
                if self.vllm_process.poll() is not None:
                    stdout, stderr = self.vllm_process.communicate()
                    logger.error(f"❌ vLLM process exited early!")
                    logger.error(f"📤 STDOUT: {stdout.decode()[-1000:]}")  # Last 1000 chars
                    logger.error(f"📤 STDERR: {stderr.decode()[-1000:]}")  # Last 1000 chars
                    return False
                    
            # If we get here, server didn't start
            logger.error("❌ vLLM server failed to start within 2 minutes")
            if self.vllm_process:
                stdout, stderr = self.vllm_process.communicate()
                logger.error(f"📤 Final STDOUT: {stdout.decode()[-1000:]}")
                logger.error(f"📤 Final STDERR: {stderr.decode()[-1000:]}")
                os.killpg(os.getpgid(self.vllm_process.pid), signal.SIGTERM)
                self.vllm_process = None
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to start vLLM server: {e}")
            import traceback
            logger.error(f"📋 Traceback: {traceback.format_exc()}")
            return False

    async def _ensure_server_running(self) -> bool:
        """Ensure vLLM server is running, start if needed"""
        logger.info(f"🔍 _ensure_server_running called - checking {self.server_url}")
        
        if await self._check_server_running():
            logger.info("✅ vLLM server already running")
            return True
            
        logger.info("❌ vLLM server not running")
        if self.auto_start:
            logger.info("🚀 Auto-start enabled - attempting to start...")
            return await self._start_vllm_server()
        else:
            logger.error("❌ vLLM server not running and auto-start disabled")
            return False
    
    def _format_messages_for_vllm(self, messages):
        """Convert OpenAI messages to vLLM server format"""
        # vLLM server expects OpenAI-compatible format
        formatted_messages = []
        
        for msg in messages:
            formatted_messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        return formatted_messages
    
    async def complete(self, request: ChatRequest) -> ChatResponse:
        """Process completion request via vLLM server"""
        # Ensure server is running
        if not await self._ensure_server_running():
            raise Exception("vLLM server is not available")
            
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
                        logger.error(f"vLLM server error: {response.status} - {error_text}")
                        raise Exception(f"vLLM server error: {response.status}")
                        
        except Exception as e:
            logger.error(f"Failed to call vLLM server: {e}")
            raise
    
    async def stream(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """Process streaming request via vLLM server"""
        # Ensure server is running
        if not await self._ensure_server_running():
            raise Exception("vLLM server is not available")
            
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
                        logger.error(f"vLLM server streaming error: {response.status} - {error_text}")
                        raise Exception(f"vLLM server streaming error: {response.status}")
                        
        except Exception as e:
            logger.error(f"Failed to stream from vLLM server: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Check if adapter is healthy without triggering initialization"""
        try:
            return await self._health_check_implementation()
        except Exception as e:
            logger.error(f"❌ Health check failed for {self.name}: {e}")
            return False

    async def _health_check_implementation(self) -> bool:
        """Check if Qwen text model can be used (server running or can auto-start)"""
        try:
            # Get model path from config (don't rely on initialized attribute)
            model_path = self.config.get('model_path', './models/Qwen3-30B-A3B-bnb-4bit')
            
            # First check if server is already running
            server_url = self.config.get('server_url', 'http://localhost:8001')
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
            logger.error(f"Qwen text health check failed: {e}")
            return False

    def _convert_to_openai_response(self, langchain_response, request):
        """Not used for vLLM server adapter - responses are already in OpenAI format"""
        pass
    
    def _format_stream_chunk(self, langchain_chunk, request):
        """Not used for vLLM server adapter - chunks are already in OpenAI format"""  
        pass

    def cleanup(self):
        """Clean up vLLM server process"""
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