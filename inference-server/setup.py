#!/usr/bin/env python3
"""Setup script for the lecture processor."""

import subprocess
import sys
import os


def install_requirements():
    """Install requirements from requirements.txt."""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✓ Dependencies installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install dependencies: {e}")
        return False
    return True


def check_env():
    """Check if environment is properly configured."""
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠ Warning: OPENAI_API_KEY not set. Please create a .env file or set this environment variable.")
        return False
    print("✓ Environment configured")
    return True


def run_basic_test():
    """Run a basic functionality test."""
    try:
        # Test text chunking
        from src.utils.helpers import chunk_text
        result = chunk_text("a" * 1500, 1000, 200)
        assert len(result) == 2
        print("✓ Text chunking works")
        
        # Test vector store
        from src.storage.vector_store import SimpleVectorStore
        store = SimpleVectorStore()
        store.add_texts(["hello world"], [[0.1, 0.2]])
        results = store.similarity_search([0.1, 0.2], k=1)
        assert len(results) == 1
        print("✓ Vector store works")
        
        print("✓ All basic tests passed")
        return True
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False


def main():
    """Main setup function."""
    print("Setting up Lecture Processor...")
    
    # Check if we're in a virtual environment
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("⚠ Warning: Not running in a virtual environment. Consider creating one:")
        print("  python3 -m venv venv")
        print("  source venv/bin/activate")
        print("  python setup.py")
        print()
    
    # Install dependencies
    if not install_requirements():
        return 1
    
    # Check environment
    env_ok = check_env()
    
    # Run basic tests
    if not run_basic_test():
        return 1
    
    print("\n🎉 Setup complete!")
    print("\nNext steps:")
    if not env_ok:
        print("1. Copy .env.example to .env and add your OpenAI API key")
    print("2. Run the example: python examples/basic_usage.py")
    print("3. Start the API server: uvicorn api.main:app --reload")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())