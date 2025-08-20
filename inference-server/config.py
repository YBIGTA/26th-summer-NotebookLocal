import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

LLM_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-large"
VISION_MODEL = "gpt-4o-mini"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
MAX_TOKENS = 4000

COLLECTION_NAME = "lecture_documents"

# Vector store settings
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY")

# PostgreSQL settings
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://username:password@localhost:5432/inference_db")
DATABASE_ECHO = os.getenv("DATABASE_ECHO", "False").lower() == "true"
