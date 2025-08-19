#!/usr/bin/env python3
"""
Comprehensive test script for LLM Router
Run with: uv run python test_router.py
"""

import asyncio
import json
import sys
from typing import Dict, Any
import aiohttp
import time

BASE_URL = "http://localhost:8000"

class RouterTester:
    def __init__(self):
        self.session = None
        self.results = {}
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def test_health(self) -> bool:
        """Test health endpoint"""
        try:
            async with self.session.get(f"{BASE_URL}/v1/health") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"✅ Health check: {data}")
                    return True
                else:
                    print(f"❌ Health check failed: {resp.status}")
                    return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False

    async def test_model(self, model_name: str, test_message: str = "Hello! Respond briefly.") -> Dict[str, Any]:
        """Test a specific model with auto-startup awareness"""
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": test_message}],
            "max_tokens": 50,
            "temperature": 0.1
        }
        
        # Special handling for local models that might need auto-startup
        is_local = model_name in ["qwen3-30b", "qwen2.5-vl-7b", "qwen2.5-vl"]
        timeout = 300 if is_local else 60  # 5 min for local (startup time), 1 min for cloud
        
        if is_local:
            print(f"🚀 Testing {model_name} (local model - may auto-start vLLM server)...")
        
        try:
            start_time = time.time()
            async with self.session.post(
                f"{BASE_URL}/v1/chat/completions",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                elapsed = time.time() - start_time
                
                if resp.status == 200:
                    data = await resp.json()
                    response_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    if is_local and elapsed > 30:
                        print(f"✅ {model_name}: Server auto-started! Response: {response_text[:100]}... ({elapsed:.1f}s)")
                    else:
                        print(f"✅ {model_name}: {response_text[:100]}... ({elapsed:.1f}s)")
                    
                    return {"status": "success", "response": response_text, "time": elapsed}
                else:
                    error_text = await resp.text()
                    print(f"❌ {model_name} failed ({resp.status}): {error_text[:200]}")
                    return {"status": "error", "error": error_text, "code": resp.status}
                    
        except asyncio.TimeoutError:
            timeout_msg = f"Timeout (>{timeout}s)"
            if is_local:
                timeout_msg += " - vLLM server may be starting, try again"
            print(f"❌ {model_name}: {timeout_msg}")
            return {"status": "timeout"}
        except Exception as e:
            print(f"❌ {model_name}: {str(e)}")
            return {"status": "error", "error": str(e)}

    async def run_tests(self):
        """Run all tests"""
        print("🧪 Starting LLM Router Tests\n")
        
        # Test 1: Health check
        print("1️⃣ Testing health endpoint...")
        health_ok = await self.test_health()
        if not health_ok:
            print("❌ Server not responding. Make sure it's running on port 8000")
            return
            
        print("\n2️⃣ Testing models...")
        
        # Test models (adjust based on your config)
        test_models = [
            # Cloud models (require API keys)
            "gpt-3.5-turbo",
            "gpt-4", 
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            
            # Local models (require vLLM servers running)
            "qwen3-30b",
            "qwen2.5-vl-7b"
        ]
        
        results = {}
        for model in test_models:
            print(f"\n📝 Testing {model}...")
            results[model] = await self.test_model(model)
            
        # Summary
        print(f"\n📊 Test Summary:")
        print("=" * 50)
        
        successful = [k for k, v in results.items() if v.get("status") == "success"]
        failed = [k for k, v in results.items() if v.get("status") != "success"]
        
        print(f"✅ Working models ({len(successful)}): {', '.join(successful)}")
        print(f"❌ Failed models ({len(failed)}): {', '.join(failed)}")
        
        if failed:
            print("\n🔍 Failure details:")
            for model in failed:
                result = results[model]
                if result.get("status") == "error":
                    print(f"   {model}: {result.get('error', 'Unknown error')[:100]}")
                elif result.get("status") == "timeout":
                    print(f"   {model}: Request timeout")
                    
        print(f"\n💡 Tips:")
        if any("qwen" in model for model in failed):
            print("   - For local models: Run ./scripts/start_qwen_text.sh first")
        if any("gpt" in model or "claude" in model for model in failed):
            print("   - For cloud models: Set API keys in .env file")

async def main():
    """Main test runner"""
    try:
        async with RouterTester() as tester:
            await tester.run_tests()
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted")
    except Exception as e:
        print(f"❌ Test runner error: {e}")

if __name__ == "__main__":
    asyncio.run(main())