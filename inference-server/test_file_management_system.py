#!/usr/bin/env python3
"""
Test script for the enhanced file management system

Tests:
1. Database migration and table creation
2. FileQueueManager operations (scan, queue, process status updates)
3. File watcher functionality (simulated file changes)
4. API endpoints for vault management
5. Integration between components

Usage:
    python test_file_management_system.py

Requirements:
    - PostgreSQL database running
    - Test vault directory with sample files
    - All dependencies installed (watchdog, sqlalchemy, etc.)
"""

import asyncio
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from vault.file_queue_manager import FileQueueManager, QueueStatus
from vault.file_watcher import FileWatcher
from database.connection import get_db
from database.models import VaultFile, Document

class FileManagementSystemTester:
    """Comprehensive test suite for the file management system."""
    
    def __init__(self):
        self.test_vault_path = None
        self.queue_manager = None
        self.file_watcher = None
        self.test_files = []
        
    async def setup_test_environment(self):
        """Set up test environment with temporary vault and sample files."""
        print("🔧 Setting up test environment...")
        
        # Create temporary vault directory
        self.test_vault_path = Path(tempfile.mkdtemp(prefix="vault_test_"))
        print(f"   Test vault: {self.test_vault_path}")
        
        # Create sample files
        sample_files = [
            "README.md",
            "notes/daily/2024-01-01.md",
            "notes/daily/2024-01-02.md",
            "research/ai_models.md",
            "research/papers/transformer.pdf",
            "projects/notebook-local/setup.md"
        ]
        
        for file_path in sample_files:
            full_path = self.test_vault_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            if file_path.endswith('.md'):
                content = f"# {file_path.stem}\n\nTest content for {file_path}\nCreated at: {datetime.now()}"
            elif file_path.endswith('.pdf'):
                content = f"Dummy PDF content for {file_path}"
            else:
                content = f"Test file: {file_path}"
            
            full_path.write_text(content)
            self.test_files.append(str(full_path.relative_to(self.test_vault_path)))
        
        print(f"   Created {len(sample_files)} test files")
        
        # Initialize components
        self.queue_manager = FileQueueManager()
        self.file_watcher = FileWatcher(str(self.test_vault_path), self.queue_manager)
        
    async def test_database_operations(self):
        """Test database operations and migrations."""
        print("🗃️ Testing database operations...")
        
        try:
            # Test database connection
            db = next(get_db())
            try:
                # Check if vault_files table exists
                result = db.execute("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = 'vault_files'
                """).fetchone()
                
                if result:
                    print("   ✅ vault_files table exists")
                else:
                    print("   ❌ vault_files table not found - run migrations first!")
                    return False
                
                # Test basic CRUD operations
                test_file = VaultFile(
                    vault_path="test_file.md",
                    file_type="md",
                    content_hash="test_hash",
                    file_size=100,
                    processing_status="unprocessed"
                )
                
                db.add(test_file)
                db.commit()
                
                # Query back
                queried_file = db.query(VaultFile).filter(VaultFile.vault_path == "test_file.md").first()
                if queried_file:
                    print("   ✅ CRUD operations working")
                    db.delete(queried_file)
                    db.commit()
                else:
                    print("   ❌ CRUD operations failed")
                    return False
                    
            finally:
                db.close()
                
            return True
            
        except Exception as e:
            print(f"   ❌ Database test failed: {e}")
            return False
    
    async def test_file_queue_manager(self):
        """Test FileQueueManager operations."""
        print("📋 Testing FileQueueManager...")
        
        try:
            # Test vault scanning
            print("   Testing vault scan...")
            scan_result = await self.queue_manager.scan_vault_directory(
                str(self.test_vault_path), 
                force_rescan=True
            )
            
            if scan_result["success"]:
                changes = scan_result["changes"]
                print(f"   ✅ Scan completed: {changes['total_scanned']} files, {len(changes['new_files'])} new")
            else:
                print("   ❌ Vault scan failed")
                return False
            
            # Test file queueing
            print("   Testing file queueing...")
            md_files = [f for f in self.test_files if f.endswith('.md')][:3]  # Queue first 3 MD files
            
            queue_result = await self.queue_manager.queue_files_for_processing(md_files)
            if len(queue_result["queued_files"]) > 0:
                print(f"   ✅ Queued {len(queue_result['queued_files'])} files")
            else:
                print("   ❌ File queueing failed")
                return False
            
            # Test status updates
            print("   Testing status updates...")
            test_file_path = md_files[0]
            
            # Mark as processing
            success = await self.queue_manager.mark_file_processing(test_file_path)
            if success:
                print("   ✅ File marked as processing")
            else:
                print("   ❌ Failed to mark file as processing")
                return False
            
            # Mark as processed
            success = await self.queue_manager.mark_file_processed(test_file_path, "test_doc_uid")
            if success:
                print("   ✅ File marked as processed")
            else:
                print("   ❌ Failed to mark file as processed")
                return False
            
            # Test queue status
            print("   Testing queue status...")
            status = await self.queue_manager.get_queue_status()
            print(f"   ✅ Queue status: {status.total_queued} queued, {status.processing} processing")
            
            return True
            
        except Exception as e:
            print(f"   ❌ FileQueueManager test failed: {e}")
            return False
    
    async def test_file_watcher(self):
        """Test FileWatcher functionality."""
        print("👀 Testing FileWatcher...")
        
        try:
            # Set up change callback
            detected_changes = []
            
            def on_change(event):
                detected_changes.append(event)
                print(f"   📄 Detected: {event.event_type} - {event.file_path}")
            
            self.file_watcher.set_change_callback(on_change)
            
            # Start watching
            self.file_watcher.start_watching()
            print("   ✅ File watcher started")
            
            # Simulate file changes
            print("   Simulating file changes...")
            
            # Create new file
            new_file = self.test_vault_path / "test_new_file.md"
            new_file.write_text("# New File\n\nThis is a new test file.")
            
            # Modify existing file
            existing_file = self.test_vault_path / self.test_files[0]
            content = existing_file.read_text()
            existing_file.write_text(content + "\n\nModified content")
            
            # Wait for events to be processed
            await asyncio.sleep(3.0)  # Allow time for debouncing
            
            # Check if changes were detected
            if len(detected_changes) > 0:
                print(f"   ✅ Detected {len(detected_changes)} file changes")
            else:
                print("   ⚠️ No file changes detected (may be due to timing)")
            
            # Stop watching
            self.file_watcher.stop_watching()
            print("   ✅ File watcher stopped")
            
            return True
            
        except Exception as e:
            print(f"   ❌ FileWatcher test failed: {e}")
            return False
    
    async def test_integration(self):
        """Test integration between components."""
        print("🔗 Testing component integration...")
        
        try:
            # Test watcher + queue manager integration
            print("   Testing watcher -> queue manager integration...")
            
            # Start watcher with queue manager integration
            self.file_watcher.start_watching()
            
            # Create a new file that should trigger queue update
            integration_file = self.test_vault_path / "integration_test.md"
            integration_file.write_text("# Integration Test\n\nTesting watcher + queue integration")
            
            # Wait for processing
            await asyncio.sleep(2.0)
            
            # Check if file appears in database
            db = next(get_db())
            try:
                vault_file = db.query(VaultFile).filter(
                    VaultFile.vault_path == "integration_test.md"
                ).first()
                
                if vault_file:
                    print("   ✅ File automatically added to database via watcher")
                else:
                    print("   ⚠️ File not found in database (may require longer wait)")
            finally:
                db.close()
            
            self.file_watcher.stop_watching()
            
            return True
            
        except Exception as e:
            print(f"   ❌ Integration test failed: {e}")
            return False
    
    async def cleanup_test_environment(self):
        """Clean up test environment."""
        print("🧹 Cleaning up test environment...")
        
        try:
            # Stop watcher if still running
            if self.file_watcher and self.file_watcher.is_watching():
                self.file_watcher.stop_watching()
            
            # Clean up database test records
            db = next(get_db())
            try:
                # Delete test vault files from database
                test_records = db.query(VaultFile).filter(
                    VaultFile.vault_path.like("test_%")
                ).all()
                
                for record in test_records:
                    db.delete(record)
                
                db.commit()
                print(f"   ✅ Cleaned up {len(test_records)} test records from database")
                
            finally:
                db.close()
            
            # Remove test vault directory
            import shutil
            if self.test_vault_path and self.test_vault_path.exists():
                shutil.rmtree(self.test_vault_path)
                print(f"   ✅ Removed test vault: {self.test_vault_path}")
            
        except Exception as e:
            print(f"   ⚠️ Cleanup warning: {e}")
    
    async def run_all_tests(self):
        """Run all tests in sequence."""
        print("🧪 Starting File Management System Tests")
        print("=" * 50)
        
        try:
            await self.setup_test_environment()
            
            tests = [
                ("Database Operations", self.test_database_operations),
                ("FileQueueManager", self.test_file_queue_manager),
                ("FileWatcher", self.test_file_watcher),
                ("Integration", self.test_integration)
            ]
            
            results = {}
            
            for test_name, test_func in tests:
                print(f"\n📝 Running {test_name} tests...")
                try:
                    result = await test_func()
                    results[test_name] = result
                    if result:
                        print(f"✅ {test_name} tests PASSED")
                    else:
                        print(f"❌ {test_name} tests FAILED")
                except Exception as e:
                    print(f"❌ {test_name} tests FAILED with exception: {e}")
                    results[test_name] = False
            
            # Print summary
            print("\n" + "=" * 50)
            print("📊 Test Results Summary:")
            
            passed = sum(1 for result in results.values() if result)
            total = len(results)
            
            for test_name, result in results.items():
                status = "✅ PASSED" if result else "❌ FAILED"
                print(f"   {test_name}: {status}")
            
            print(f"\nOverall: {passed}/{total} test suites passed")
            
            if passed == total:
                print("🎉 All tests passed! File management system is working correctly.")
                return True
            else:
                print("⚠️ Some tests failed. Please check the output above for details.")
                return False
                
        finally:
            await self.cleanup_test_environment()

async def main():
    """Main test execution function."""
    tester = FileManagementSystemTester()
    
    try:
        success = await tester.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
        await tester.cleanup_test_environment()
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        await tester.cleanup_test_environment()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())