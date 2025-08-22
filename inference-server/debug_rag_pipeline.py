#!/usr/bin/env python3
"""
RAG Pipeline Debug Script - comprehensive system diagnosis
"""

import logging
import sys
from pathlib import Path
import time

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

import config
from src.database.connection import get_db, engine
from src.database.models import Document, Chunk
from sqlalchemy import text
import weaviate

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def check_configuration():
    """Check all configuration values."""
    logger.info("🔧 Configuration Check:")
    logger.info(f"   COLLECTION_NAME: {config.COLLECTION_NAME}")
    logger.info(f"   WEAVIATE_URL: {config.WEAVIATE_URL}")
    logger.info(f"   WEAVIATE_API_KEY: {'***' if config.WEAVIATE_API_KEY else 'None'}")
    logger.info(f"   DATABASE_URL: {config.DATABASE_URL}")
    logger.info(f"   OPENAI_API_KEY: {'***' if config.OPENAI_API_KEY else 'None'}")


def check_postgresql():
    """Check PostgreSQL connection and data."""
    logger.info("🐘 PostgreSQL Check:")
    
    try:
        # Test basic connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            logger.info(f"   ✅ Connected: {version[:50]}...")
        
        # Check tables exist
        db = next(get_db())
        try:
            # Count documents
            doc_count = db.query(Document).count()
            logger.info(f"   📄 Documents: {doc_count}")
            
            # Count chunks
            chunk_count = db.query(Chunk).count()
            logger.info(f"   📝 Chunks: {chunk_count}")
            
            # Show recent documents
            if doc_count > 0:
                recent_docs = db.query(Document).order_by(Document.created_at.desc()).limit(3).all()
                logger.info("   📋 Recent documents:")
                for doc in recent_docs:
                    logger.info(f"      - {doc.title} ({doc.doc_uid})")
                    
                    # Check chunks for this document
                    doc_chunks = db.query(Chunk).filter(Chunk.doc_uid == doc.doc_uid).count()
                    logger.info(f"        Chunks: {doc_chunks}")
            else:
                logger.warning("   ⚠️ No documents found in PostgreSQL")
                
        finally:
            db.close()
            
        return True
        
    except Exception as e:
        logger.error(f"   ❌ PostgreSQL error: {e}")
        return False


def check_weaviate():
    """Check Weaviate connection and data."""
    logger.info("🔍 Weaviate Check:")
    
    try:
        # Connect to Weaviate
        auth = (
            weaviate.AuthApiKey(api_key=config.WEAVIATE_API_KEY)
            if config.WEAVIATE_API_KEY
            else None
        )
        client = weaviate.Client(
            url=config.WEAVIATE_URL, 
            auth_client_secret=auth, 
            timeout_config=(5, 30)
        )
        
        # Test connection
        if not client.is_ready():
            logger.error("   ❌ Weaviate is not ready")
            return False
            
        logger.info("   ✅ Connected to Weaviate")
        
        # Check schema
        schema = client.schema.get()
        classes = [cls['class'] for cls in schema.get('classes', [])]
        logger.info(f"   📋 Available classes: {classes}")
        
        # Check if our collection exists
        target_class = config.COLLECTION_NAME
        if target_class in classes:
            logger.info(f"   ✅ Collection '{target_class}' exists")
            
            # Get schema details
            class_schema = client.schema.get(target_class)
            properties = [prop['name'] for prop in class_schema.get('properties', [])]
            logger.info(f"   📋 Properties: {properties}")
            
            # Count objects
            try:
                result = client.query.aggregate(target_class).with_meta_count().do()
                count = result.get('data', {}).get('Aggregate', {}).get(target_class, [{}])[0].get('meta', {}).get('count', 0)
                logger.info(f"   📊 Object count: {count}")
                
                # Sample a few objects
                if count > 0:
                    sample_result = client.query.get(target_class, ["text", "chunk_id", "doc_uid"]).with_limit(2).do()
                    objects = sample_result.get('data', {}).get('Get', {}).get(target_class, [])
                    logger.info("   📋 Sample objects:")
                    for i, obj in enumerate(objects, 1):
                        text_preview = obj.get('text', '')[:50] + '...' if len(obj.get('text', '')) > 50 else obj.get('text', '')
                        logger.info(f"      {i}. Text: {text_preview}")
                        logger.info(f"         chunk_id: {obj.get('chunk_id', 'N/A')}")
                        logger.info(f"         doc_uid: {obj.get('doc_uid', 'N/A')}")
                else:
                    logger.warning("   ⚠️ No objects found in Weaviate")
                    
            except Exception as e:
                logger.error(f"   ❌ Error querying objects: {e}")
                
        else:
            logger.error(f"   ❌ Collection '{target_class}' does not exist")
            logger.info("   💡 Run: python reset_weaviate.py")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"   ❌ Weaviate error: {e}")
        return False


def test_vector_store_creation():
    """Test vector store creation process."""
    logger.info("🏪 Vector Store Creation Test:")
    
    try:
        from src.storage.vector_store import get_vector_store
        from src.processors.embedder import Embedder
        from src.llm.core.router import LLMRouter
        
        # Create router and embedder
        router = LLMRouter()
        embedder = Embedder(router=router)
        
        # Create vector store
        vector_store = get_vector_store(embedder.embed)
        logger.info(f"   ✅ Vector store created: {type(vector_store).__name__}")
        
        # Test if it's Weaviate or fallback
        from src.storage.vector_store import WeaviateVectorStore
        if isinstance(vector_store, WeaviateVectorStore):
            logger.info("   ✅ Using WeaviateVectorStore")
            logger.info(f"   📋 Index name: {vector_store.index_name}")
        else:
            logger.warning("   ⚠️ Using SimpleVectorStore (fallback)")
            
        return vector_store
        
    except Exception as e:
        logger.error(f"   ❌ Vector store creation error: {e}")
        return None


def test_hybrid_store():
    """Test hybrid store functionality."""
    logger.info("🔗 Hybrid Store Test:")
    
    try:
        from src.storage.hybrid_store import HybridStore
        from src.processors.embedder import Embedder
        from src.llm.core.router import LLMRouter
        
        # Create components
        router = LLMRouter()
        embedder = Embedder(router=router)
        vector_store = test_vector_store_creation()
        
        if not vector_store:
            logger.error("   ❌ Cannot test hybrid store without vector store")
            return False
            
        # Create hybrid store
        hybrid_store = HybridStore(vector_store, embedder)
        logger.info("   ✅ HybridStore created successfully")
        
        # Test search (should return empty results but not error)
        test_query = "test query"
        logger.info(f"   🔍 Testing search with: '{test_query}'")
        
        start_time = time.time()
        results = hybrid_store.search(test_query, k=3)
        search_time = time.time() - start_time
        
        logger.info(f"   📊 Search completed in {search_time:.2f}s")
        logger.info(f"   📋 Results found: {len(results)}")
        
        if results:
            logger.info("   📋 Sample result:")
            sample = results[0]
            for key, value in sample.items():
                if key == 'text':
                    preview = value[:50] + '...' if len(value) > 50 else value
                    logger.info(f"      {key}: {preview}")
                else:
                    logger.info(f"      {key}: {value}")
        
        return True
        
    except Exception as e:
        logger.error(f"   ❌ Hybrid store error: {e}")
        import traceback
        logger.error(f"   📋 Traceback: {traceback.format_exc()}")
        return False


def test_full_rag_pipeline():
    """Test the complete RAG pipeline."""
    logger.info("🔄 Full RAG Pipeline Test:")
    
    try:
        from src.main import LectureProcessor
        
        # Create processor
        logger.info("   🏗️ Creating LectureProcessor...")
        processor = LectureProcessor(use_hybrid=True)
        logger.info("   ✅ LectureProcessor created")
        
        # Test QA workflow
        test_question = "What is this document about?"
        logger.info(f"   ❓ Testing question: '{test_question}'")
        
        start_time = time.time()
        import asyncio
        answer = asyncio.run(processor.qa_workflow.ask(test_question))
        qa_time = time.time() - start_time
        
        logger.info(f"   ⏱️ QA completed in {qa_time:.2f}s")
        logger.info(f"   💬 Answer: {answer}")
        
        return True
        
    except Exception as e:
        logger.error(f"   ❌ RAG pipeline error: {e}")
        import traceback
        logger.error(f"   📋 Traceback: {traceback.format_exc()}")
        return False


def main():
    """Run comprehensive RAG pipeline diagnosis."""
    print("🔍 RAG Pipeline Diagnostic Tool")
    print("=" * 50)
    
    all_passed = True
    
    # 1. Configuration
    check_configuration()
    print()
    
    # 2. PostgreSQL
    if not check_postgresql():
        all_passed = False
    print()
    
    # 3. Weaviate
    if not check_weaviate():
        all_passed = False
    print()
    
    # 4. Vector Store
    if not test_vector_store_creation():
        all_passed = False
    print()
    
    # 5. Hybrid Store
    if not test_hybrid_store():
        all_passed = False
    print()
    
    # 6. Full Pipeline
    if not test_full_rag_pipeline():
        all_passed = False
    print()
    
    # Summary
    if all_passed:
        logger.info("🎉 All tests passed! RAG pipeline is working correctly.")
    else:
        logger.error("❌ Some tests failed. Check the errors above.")
        logger.info("💡 Common fixes:")
        logger.info("   - Run: python reset_weaviate.py")
        logger.info("   - Re-process documents after fixing issues")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)