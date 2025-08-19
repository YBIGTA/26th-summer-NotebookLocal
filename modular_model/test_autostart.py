#!/usr/bin/env python3
"""
Quick auto-startup validation script
Tests that vLLM servers auto-start when needed
"""

import requests
import time
import subprocess
import signal
import os

def check_process_running(port):
    """Check if anything is listening on port"""
    result = subprocess.run(['netstat', '-tulpn'], capture_output=True, text=True)
    return f':{port}' in result.stdout

def kill_vllm_processes():
    """Kill any existing vLLM processes"""
    try:
        subprocess.run(['pkill', '-f', 'vllm.entrypoints'], check=False)
        time.sleep(2)
        print("🧹 Cleaned up existing vLLM processes")
    except:
        pass

def test_auto_startup():
    """Test the auto-startup feature"""
    
    print("🧪 Auto-Startup Test")
    print("=" * 40)
    
    # Step 1: Clean slate
    print("\n1️⃣ Cleaning up any existing vLLM processes...")
    kill_vllm_processes()
    
    # Step 2: Verify clean state
    print("\n2️⃣ Checking ports are free...")
    for port, name in [(8001, "Qwen text"), (8002, "Qwen vision")]:
        if check_process_running(port):
            print(f"⚠️  Port {port} ({name}) still occupied")
        else:
            print(f"✅ Port {port} ({name}) is free")
    
    # Step 3: Test router is running
    print("\n3️⃣ Checking router is running...")
    try:
        response = requests.get("http://localhost:8000/v1/health", timeout=5)
        if response.status_code == 200:
            print("✅ Router is running")
        else:
            print(f"❌ Router health check failed: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Router not running: {e}")
        print("💡 Start router first: uv run python src/main.py")
        return
    
    # Step 4: Test auto-startup
    print("\n4️⃣ Testing Qwen text model auto-startup...")
    print("   This may take 2-3 minutes for first request...")
    
    payload = {
        "model": "qwen3-14b",
        "messages": [{"role": "user", "content": "Say hi briefly"}],
        "max_tokens": 20
    }
    
    try:
        start_time = time.time()
        response = requests.post(
            "http://localhost:8000/v1/chat/completions",
            json=payload,
            timeout=300  # 5 minute timeout for startup
        )
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            message = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"✅ Auto-startup successful! ({elapsed:.1f}s)")
            print(f"   Response: {message}")
            
            # Verify vLLM process is now running
            if check_process_running(8001):
                print("✅ vLLM server confirmed running on port 8001")
            else:
                print("⚠️  vLLM process not detected, but request succeeded")
                
        else:
            print(f"❌ Request failed: {response.status_code}")
            print(f"   Error: {response.text}")
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out (>5min)")
        print("   Check model files exist and GPU memory is available")
    except Exception as e:
        print(f"❌ Request error: {e}")
    
    print("\n5️⃣ Testing subsequent request (should be fast)...")
    try:
        start_time = time.time()
        response = requests.post(
            "http://localhost:8000/v1/chat/completions",
            json=payload,
            timeout=30
        )
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            print(f"✅ Second request fast! ({elapsed:.1f}s)")
        else:
            print(f"❌ Second request failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Second request error: {e}")
    
    print(f"\n📊 Final Status:")
    print(f"   Router (8000): {'✅' if check_process_running(8000) else '❌'}")
    print(f"   Qwen Text (8001): {'✅' if check_process_running(8001) else '❌'}")
    print(f"   Qwen Vision (8002): {'✅' if check_process_running(8002) else '❌'}")

if __name__ == "__main__":
    test_auto_startup()