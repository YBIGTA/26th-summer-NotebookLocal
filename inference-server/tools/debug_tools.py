#!/usr/bin/env python3
"""
Quick debugging and testing tools for the inference server.
Run these commands to see exactly what's happening in your system.
"""

import requests
import json
import time
import os
from pathlib import Path

BASE_URL = "http://localhost:8000/api/v1"

def test_health():
    """Test basic server health"""
    print("🔍 Testing server health...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"✅ Health check: {response.status_code}")
        print(f"   Response: {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_detailed_health():
    """Test detailed system health"""
    print("🔍 Testing detailed system health...")
    try:
        response = requests.get(f"{BASE_URL}/debug/health-detailed")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ System Status: {data.get('system_status', 'unknown')}")
            
            components = data.get('components', {})
            for component, status in components.items():
                print(f"   {component}: {status.get('status', 'unknown')}")
                if status.get('error'):
                    print(f"      Error: {status['error']}")
        else:
            print(f"❌ Detailed health check failed: {response.status_code}")
            print(f"   Response: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Detailed health check failed: {e}")
        return False

def test_db_stats():
    """Check database statistics"""
    print("🔍 Checking database statistics...")
    try:
        response = requests.get(f"{BASE_URL}/debug/db-stats")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Database Stats:")
            print(f"   Documents: {data.get('total_documents', 0)}")
            print(f"   Chunks: {data.get('total_chunks', 0)}")
            print(f"   Types: {data.get('documents_by_type', {})}")
            
            recent = data.get('recent_documents', [])
            if recent:
                print(f"   Recent documents:")
                for doc in recent[:3]:
                    print(f"     - {doc.get('title', 'Untitled')} ({doc.get('chunks', 0)} chunks)")
        else:
            print(f"❌ DB stats failed: {response.status_code}")
            print(f"   Response: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ DB stats failed: {e}")
        return False

def test_pdf_upload(pdf_path):
    """Test PDF upload and processing"""
    # If relative path, try from project root
    if not os.path.isabs(pdf_path):
        project_root = Path(__file__).parent.parent
        full_path = project_root / pdf_path
        if full_path.exists():
            pdf_path = str(full_path)
    
    if not os.path.exists(pdf_path):
        print(f"❌ PDF file not found: {pdf_path}")
        return False
    
    print(f"🔍 Testing PDF upload: {pdf_path}")
    print(f"   File size: {os.path.getsize(pdf_path) / 1024 / 1024:.2f} MB")
    
    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': (os.path.basename(pdf_path), f, 'application/pdf')}
            
            print("📤 Uploading PDF...")
            start_time = time.time()
            response = requests.post(f"{BASE_URL}/process", files=files)
            upload_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Upload successful in {upload_time:.2f}s:")
                print(f"   Filename: {data.get('filename')}")
                print(f"   Chunks: {data.get('chunks', 0)}")
                print(f"   Images: {data.get('images', 0)}")
                print(f"   Status: {data.get('status')}")
                return True
            else:
                print(f"❌ Upload failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return False

def test_question(question):
    """Test question answering"""
    print(f"🔍 Testing question: '{question}'")
    
    try:
        payload = {"question": question}
        
        print("🤔 Processing question...")
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/ask", json=payload)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Answer received in {response_time:.2f}s:")
            print(f"   Answer: {data.get('answer', 'No answer provided')[:200]}...")
            return True
        else:
            print(f"❌ Question failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Question failed: {e}")
        return False

def run_full_test():
    """Run complete system test"""
    print("🚀 Running full system test...")
    print("=" * 50)
    
    # Test 1: Basic health
    health_ok = test_health()
    print()
    
    # Test 2: Detailed health
    detailed_health_ok = test_detailed_health()
    print()
    
    # Test 3: Database stats
    db_ok = test_db_stats()
    print()
    
    # Test 4: PDF upload (if test.pdf exists)
    pdf_path = "test.pdf"
    upload_ok = False
    # Check in project root
    project_root = Path(__file__).parent.parent
    full_pdf_path = project_root / pdf_path
    if full_pdf_path.exists():
        upload_ok = test_pdf_upload(str(full_pdf_path))
        print()
    else:
        print(f"⚠️  Skipping PDF test - {pdf_path} not found")
        print()
    
    # Test 5: Question answering (only if upload worked or we have existing documents)
    question_ok = False
    if upload_ok or (db_ok and test_db_stats()):  # Check if we have documents
        question_ok = test_question("What is this document about?")
        print()
    else:
        print("⚠️  Skipping question test - no documents available")
        print()
    
    # Summary
    print("=" * 50)
    print("🎯 TEST SUMMARY:")
    print(f"   Basic Health: {'✅' if health_ok else '❌'}")
    print(f"   Detailed Health: {'✅' if detailed_health_ok else '❌'}")
    print(f"   Database: {'✅' if db_ok else '❌'}")
    print(f"   PDF Upload: {'✅' if upload_ok else '⚠️  Skipped'}")
    print(f"   Q&A: {'✅' if question_ok else '⚠️  Skipped'}")
    
    all_critical_tests_passed = health_ok and detailed_health_ok
    if all_critical_tests_passed:
        print("🎉 Core system is working!")
    else:
        print("⚠️  Some issues found - check logs above")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "health":
            test_health()
        elif command == "detailed-health":
            test_detailed_health()
        elif command == "db-stats":
            test_db_stats()
        elif command == "upload" and len(sys.argv) > 2:
            test_pdf_upload(sys.argv[2])
        elif command == "question" and len(sys.argv) > 2:
            test_question(" ".join(sys.argv[2:]))
        elif command == "full":
            run_full_test()
        else:
            print("Usage:")
            print("  python debug_tools.py health")
            print("  python debug_tools.py detailed-health")
            print("  python debug_tools.py db-stats")
            print("  python debug_tools.py upload path/to/file.pdf")
            print("  python debug_tools.py question 'What is this about?'")
            print("  python debug_tools.py full")
    else:
        run_full_test()