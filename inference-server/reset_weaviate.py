#!/usr/bin/env python3
"""
Weaviate schema reset script - drops and recreates schema with new fields.
Use this after making schema changes to the WeaviateVectorStore.
"""

import logging
import sys
from pathlib import Path
import weaviate

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def connect_to_weaviate():
    """Connect to Weaviate instance."""
    try:
        auth = (
            weaviate.AuthApiKey(api_key=config.WEAVIATE_API_KEY)
            if config.WEAVIATE_API_KEY
            else None
        )
        client = weaviate.Client(
            url=config.WEAVIATE_URL, 
            auth_client_secret=auth, 
            timeout_config=(10, 60)  # Longer timeout for schema operations
        )
        
        # Test connection
        if client.is_ready():
            logger.info(f"✅ Connected to Weaviate at {config.WEAVIATE_URL}")
            return client
        else:
            logger.error("❌ Weaviate is not ready")
            return None
            
    except Exception as e:
        logger.error(f"❌ Failed to connect to Weaviate: {e}")
        return None


def show_current_schema(client):
    """Show current Weaviate schema."""
    try:
        logger.info("📋 Current Weaviate schema:")
        
        schema = client.schema.get()
        classes = schema.get('classes', [])
        
        if not classes:
            logger.info("  No classes found")
            return
            
        for cls in classes:
            class_name = cls['class']
            logger.info(f"  📌 Class: {class_name}")
            
            properties = cls.get('properties', [])
            for prop in properties:
                prop_name = prop['name']
                prop_type = prop['dataType']
                logger.info(f"     Property: {prop_name} ({prop_type})")
                
        # Check if our target class exists
        target_class = config.COLLECTION_NAME
        if any(cls['class'] == target_class for cls in classes):
            logger.info(f"  ✅ Target class '{target_class}' exists")
        else:
            logger.info(f"  ⚠️ Target class '{target_class}' does not exist")
            
    except Exception as e:
        logger.error(f"❌ Failed to show schema: {e}")


def delete_class(client, class_name):
    """Delete a specific class from Weaviate."""
    try:
        if client.schema.exists(class_name):
            logger.info(f"🗑️ Deleting class: {class_name}")
            client.schema.delete_class(class_name)
            logger.info(f"✅ Class '{class_name}' deleted successfully")
            return True
        else:
            logger.info(f"⚠️ Class '{class_name}' does not exist, skipping deletion")
            return True
            
    except Exception as e:
        logger.error(f"❌ Failed to delete class '{class_name}': {e}")
        return False


def create_new_schema(client, class_name):
    """Create new schema with updated fields."""
    try:
        logger.info(f"🏗️ Creating new schema for class: {class_name}")
        
        schema = {
            "class": class_name,
            "vectorizer": "none",
            "properties": [
                {"name": "text", "dataType": ["text"]},
                {"name": "chunk_id", "dataType": ["text"]},
                {"name": "doc_uid", "dataType": ["text"]},
                {"name": "order_index", "dataType": ["int"]},
                {"name": "type", "dataType": ["text"]},
            ],
        }
        
        client.schema.create_class(schema)
        logger.info(f"✅ Schema created successfully for '{class_name}'")
        
        # Verify creation
        if client.schema.exists(class_name):
            logger.info(f"✅ Schema verification passed for '{class_name}'")
            return True
        else:
            logger.error(f"❌ Schema verification failed for '{class_name}'")
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to create schema for '{class_name}': {e}")
        return False


def reset_weaviate_schema():
    """Reset Weaviate schema with new structure."""
    logger.info("🔄 Starting Weaviate schema reset...")
    
    # Connect to Weaviate
    client = connect_to_weaviate()
    if not client:
        return False
    
    target_class = config.COLLECTION_NAME
    logger.info(f"🎯 Target class: {target_class}")
    
    # Show current schema
    show_current_schema(client)
    
    # Delete existing class
    if not delete_class(client, target_class):
        return False
    
    # Create new schema
    if not create_new_schema(client, target_class):
        return False
    
    logger.info("✅ Weaviate schema reset completed successfully!")
    logger.info("🎉 New schema with metadata fields is now active")
    
    # Show updated schema
    show_current_schema(client)
    
    return True


def get_stats(client):
    """Get current Weaviate statistics."""
    try:
        target_class = config.COLLECTION_NAME
        
        if not client.schema.exists(target_class):
            logger.info(f"📊 Class '{target_class}' does not exist")
            return
            
        # Count objects in the class
        result = client.query.aggregate(target_class).with_meta_count().do()
        count = result.get('data', {}).get('Aggregate', {}).get(target_class, [{}])[0].get('meta', {}).get('count', 0)
        
        logger.info(f"📊 Current statistics for '{target_class}':")
        logger.info(f"   Total objects: {count}")
        
    except Exception as e:
        logger.error(f"❌ Failed to get stats: {e}")


if __name__ == "__main__":
    print("🔄 Weaviate Schema Reset Tool")
    print("=" * 50)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--show-schema":
        client = connect_to_weaviate()
        if client:
            show_current_schema(client)
            get_stats(client)
        sys.exit(0)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        client = connect_to_weaviate()
        if client:
            get_stats(client)
        sys.exit(0)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage:")
        print("  python reset_weaviate.py                # Reset schema")
        print("  python reset_weaviate.py --show-schema  # Show current schema")
        print("  python reset_weaviate.py --stats        # Show statistics")
        print("  python reset_weaviate.py --help         # Show this help")
        sys.exit(0)
    
    print("⚠️  This will DELETE ALL DATA in Weaviate and recreate the schema!")
    print("This is needed to apply the new metadata fields (chunk_id, doc_uid, etc.).")
    print()
    
    response = input("Are you sure you want to continue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("❌ Operation cancelled")
        sys.exit(1)
    
    print()
    if reset_weaviate_schema():
        print()
        print("🎉 Weaviate schema reset completed successfully!")
        print("You can now re-process your documents with the new schema.")
    else:
        print("❌ Weaviate schema reset failed!")
        sys.exit(1)