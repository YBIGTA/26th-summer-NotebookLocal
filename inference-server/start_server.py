#!/usr/bin/env python3
"""
Startup script for the inference server with automatic database initialization.
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_environment():
    """Check if required environment variables are set."""
    required_vars = ["DATABASE_URL"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        logger.info("Set them like this:")
        for var in missing_vars:
            if var == "DATABASE_URL":
                logger.info(f'export {var}="postgresql://username:password@localhost:5432/inference_db"')
        return False
    
    return True


def main():
    """Main startup function."""
    logger.info("🚀 Starting inference server initialization...")
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Test database connection and initialize if needed
    try:
        from src.database.init_db import init_database_on_startup
        
        if not init_database_on_startup():
            logger.warning("⚠️ Database initialization had issues, but continuing...")
        
    except Exception as e:
        logger.error(f"❌ Database setup failed: {e}")
        logger.info("💡 Make sure PostgreSQL is running and DATABASE_URL is correct")
        sys.exit(1)
    
    # Start the FastAPI server
    try:
        import uvicorn
        logger.info("✅ Starting FastAPI server...")
        logger.info("💡 For local model development, use UV commands:")
        logger.info("   uv add vllm transformers torch")
        
        uvicorn.run(
            "api.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
        
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user")
    except Exception as e:
        logger.error(f"❌ Server startup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()