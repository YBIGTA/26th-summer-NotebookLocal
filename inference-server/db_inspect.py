#!/usr/bin/env python3
"""
Direct database inspection tools.
Connect directly to PostgreSQL to see exactly what's stored.
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.database.connection import get_session
from src.database.models import Document, Chunk
from sqlalchemy import func
import json
from datetime import datetime

def inspect_documents():
    """Show all documents in the database"""
    print("🔍 Inspecting documents table...")
    
    try:
        session = get_session()
        
        # Get document count
        total_docs = session.query(func.count(Document.doc_uid)).scalar()
        print(f"📊 Total documents: {total_docs}")
        
        if total_docs == 0:
            print("📭 No documents found in database")
            return
        
        # Get all documents
        documents = session.query(Document).order_by(Document.ingested_at.desc()).all()
        
        print("\n📄 Documents:")
        print("-" * 80)
        
        for doc in documents:
            print(f"ID: {doc.doc_uid}")
            print(f"Title: {doc.title}")
            print(f"Source: {doc.source_type}")
            print(f"Path: {doc.path}")
            print(f"Language: {doc.lang}")
            print(f"Tags: {doc.tags}")
            print(f"Pages: {doc.page_count}")
            print(f"Checksum: {doc.checksum}")
            print(f"Ingested: {doc.ingested_at}")
            print(f"Created: {doc.created_at}")
            
            # Count chunks for this document
            chunk_count = session.query(func.count(Chunk.chunk_uid)).filter(Chunk.document_id == doc.doc_uid).scalar()
            print(f"Chunks: {chunk_count}")
            print("-" * 80)
        
        session.close()
        
    except Exception as e:
        print(f"❌ Database inspection failed: {e}")
        import traceback
        traceback.print_exc()

def inspect_chunks(document_id=None, limit=10):
    """Show chunks, optionally for a specific document"""
    print(f"🔍 Inspecting chunks table (limit: {limit})...")
    
    try:
        session = get_session()
        
        # Get chunk count
        query = session.query(func.count(Chunk.chunk_uid))
        if document_id:
            query = query.filter(Chunk.document_id == document_id)
        
        total_chunks = query.scalar()
        print(f"📊 Total chunks: {total_chunks}")
        
        if total_chunks == 0:
            print("📭 No chunks found")
            return
        
        # Get chunks
        query = session.query(Chunk)
        if document_id:
            query = query.filter(Chunk.document_id == document_id)
        
        chunks = query.order_by(Chunk.created_at.desc()).limit(limit).all()
        
        print(f"\n📝 Chunks (showing first {len(chunks)}):")
        print("-" * 80)
        
        for chunk in chunks:
            print(f"Chunk ID: {chunk.chunk_uid}")
            print(f"Document ID: {chunk.document_id}")
            print(f"Sequence: {chunk.sequence_number}")
            print(f"Page: {chunk.page_number}")
            print(f"Text (first 100 chars): {chunk.text[:100]}...")
            print(f"Text length: {len(chunk.text)} characters")
            print(f"Vector ID: {chunk.vector_id}")
            print(f"Metadata: {chunk.metadata}")
            print(f"Created: {chunk.created_at}")
            print("-" * 80)
        
        session.close()
        
    except Exception as e:
        print(f"❌ Chunk inspection failed: {e}")
        import traceback
        traceback.print_exc()

def inspect_stats():
    """Show database statistics"""
    print("🔍 Database statistics...")
    
    try:
        session = get_session()
        
        # Document stats
        doc_count = session.query(func.count(Document.doc_uid)).scalar()
        chunk_count = session.query(func.count(Chunk.chunk_uid)).scalar()
        
        print(f"📊 OVERALL STATS:")
        print(f"   Documents: {doc_count:,}")
        print(f"   Chunks: {chunk_count:,}")
        print(f"   Avg chunks per doc: {chunk_count / doc_count if doc_count > 0 else 0:.1f}")
        
        # Document types
        doc_types = session.query(Document.source_type, func.count(Document.doc_uid)).group_by(Document.source_type).all()
        if doc_types:
            print(f"\n📄 DOCUMENT TYPES:")
            for doc_type, count in doc_types:
                print(f"   {doc_type}: {count}")
        
        # Languages
        languages = session.query(Document.lang, func.count(Document.doc_uid)).group_by(Document.lang).all()
        if languages:
            print(f"\n🌍 LANGUAGES:")
            for lang, count in languages:
                print(f"   {lang}: {count}")
        
        # Chunk size distribution
        chunk_sizes = session.query(func.length(Chunk.text)).all()
        if chunk_sizes:
            sizes = [size[0] for size in chunk_sizes if size[0] is not None]
            if sizes:
                print(f"\n📏 CHUNK SIZES:")
                print(f"   Min: {min(sizes):,} characters")
                print(f"   Max: {max(sizes):,} characters")
                print(f"   Average: {sum(sizes) / len(sizes):.0f} characters")
        
        # Recent activity
        recent_docs = session.query(Document).order_by(Document.ingested_at.desc()).limit(5).all()
        if recent_docs:
            print(f"\n⏰ RECENT DOCUMENTS:")
            for doc in recent_docs:
                print(f"   {doc.title} ({doc.ingested_at})")
        
        session.close()
        
    except Exception as e:
        print(f"❌ Stats failed: {e}")
        import traceback
        traceback.print_exc()

def search_documents(search_term):
    """Search documents by title or content"""
    print(f"🔍 Searching for: '{search_term}'...")
    
    try:
        session = get_session()
        
        # Search in document titles
        title_matches = session.query(Document).filter(
            Document.title.contains(search_term)
        ).all()
        
        # Search in chunk content
        content_matches = session.query(Chunk).filter(
            Chunk.text.contains(search_term)
        ).limit(10).all()
        
        if title_matches:
            print(f"\n📄 TITLE MATCHES ({len(title_matches)}):")
            for doc in title_matches:
                print(f"   {doc.title} (ID: {doc.doc_uid})")
        
        if content_matches:
            print(f"\n📝 CONTENT MATCHES (first 10):")
            for chunk in content_matches:
                # Get document title
                doc = session.query(Document).filter(Document.doc_uid == chunk.document_id).first()
                doc_title = doc.title if doc else "Unknown"
                
                # Show context around match
                text = chunk.text
                match_pos = text.lower().find(search_term.lower())
                if match_pos >= 0:
                    start = max(0, match_pos - 50)
                    end = min(len(text), match_pos + len(search_term) + 50)
                    context = text[start:end]
                    print(f"   {doc_title}: ...{context}...")
                else:
                    print(f"   {doc_title}: {text[:100]}...")
        
        if not title_matches and not content_matches:
            print("📭 No matches found")
        
        session.close()
        
    except Exception as e:
        print(f"❌ Search failed: {e}")
        import traceback
        traceback.print_exc()

def clear_database():
    """Clear all data (use with caution!)"""
    confirm = input("⚠️  This will delete ALL data. Type 'DELETE ALL' to confirm: ")
    if confirm != "DELETE ALL":
        print("❌ Operation cancelled")
        return
    
    print("🗑️  Clearing database...")
    
    try:
        session = get_session()
        
        # Delete in correct order due to foreign keys
        chunk_count = session.query(Chunk).count()
        session.query(Chunk).delete()
        
        doc_count = session.query(Document).count()
        session.query(Document).delete()
        
        session.commit()
        session.close()
        
        print(f"✅ Deleted {chunk_count} chunks and {doc_count} documents")
        
    except Exception as e:
        print(f"❌ Clear operation failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Database inspection tools:")
        print("  python db_inspect.py documents         - Show all documents")
        print("  python db_inspect.py chunks [limit]    - Show chunks (default limit: 10)")
        print("  python db_inspect.py chunks DOC_ID     - Show chunks for specific document")
        print("  python db_inspect.py stats             - Show database statistics")
        print("  python db_inspect.py search TERM       - Search documents and content")
        print("  python db_inspect.py clear             - Clear all data (DANGEROUS!)")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "documents":
        inspect_documents()
    elif command == "chunks":
        if len(sys.argv) > 2:
            try:
                # Try as limit first
                limit = int(sys.argv[2])
                inspect_chunks(limit=limit)
            except ValueError:
                # Must be document ID
                inspect_chunks(document_id=sys.argv[2])
        else:
            inspect_chunks()
    elif command == "stats":
        inspect_stats()
    elif command == "search" and len(sys.argv) > 2:
        search_documents(" ".join(sys.argv[2:]))
    elif command == "clear":
        clear_database()
    else:
        print(f"Unknown command: {command}")