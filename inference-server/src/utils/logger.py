import logging
import time
import json
from typing import Any, Dict, Optional
from contextlib import contextmanager
import config

# Simple unified logging setup
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("inference_server")

class UnifiedLogger:
    """Simple unified logging for all inference server operations"""
    
    @staticmethod
    def log(operation: str, details: Optional[Dict[str, Any]] = None, level: str = "INFO"):
        """Log any operation with optional details"""
        if not (config.DEBUG_MODE or config.LOG_API_REQUESTS or config.LOG_DATABASE_OPS or config.LOG_PROCESSING_DETAILS):
            return
        
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(f"🔍 {operation}")
        
        if details and config.DEBUG_MODE:
            for key, value in details.items():
                # Truncate long values
                str_value = str(value)
                if len(str_value) > 200:
                    str_value = str_value[:200] + "..."
                log_func(f"   📋 {key}: {str_value}")
    
    @staticmethod
    @contextmanager
    def time_operation(operation_name: str, details: Optional[Dict[str, Any]] = None):
        """Time any operation and log results"""
        start_time = time.time()
        UnifiedLogger.log(f"⏱️  START: {operation_name}", details)
        
        try:
            yield
            duration = time.time() - start_time
            UnifiedLogger.log(f"✅ SUCCESS: {operation_name} ({duration:.2f}s)")
        except Exception as e:
            duration = time.time() - start_time
            UnifiedLogger.log(f"❌ FAILED: {operation_name} ({duration:.2f}s) - {str(e)}", level="ERROR")
            raise
    
    @staticmethod
    def api_request(service: str, method: str, details: Optional[Dict[str, Any]] = None):
        """Log API requests"""
        if config.LOG_API_REQUESTS or config.DEBUG_MODE:
            UnifiedLogger.log(f"🚀 API REQUEST: {service}.{method}", details)
    
    @staticmethod
    def api_response(service: str, method: str, duration: float, details: Optional[Dict[str, Any]] = None):
        """Log API responses"""
        if config.LOG_API_REQUESTS or config.DEBUG_MODE:
            UnifiedLogger.log(f"📥 API RESPONSE: {service}.{method} ({duration:.2f}s)", details)
    
    @staticmethod
    def db_operation(operation: str, table: str = "", details: Optional[Dict[str, Any]] = None):
        """Log database operations"""
        if config.LOG_DATABASE_OPS or config.DEBUG_MODE:
            table_part = f" {table}" if table else ""
            UnifiedLogger.log(f"🗄️  DB: {operation}{table_part}", details)
    
    @staticmethod
    def processing_step(step: str, details: Optional[Dict[str, Any]] = None):
        """Log processing steps"""
        if config.LOG_PROCESSING_DETAILS or config.DEBUG_MODE:
            UnifiedLogger.log(f"🔄 PROCESS: {step}", details)

# Simple shortcuts for easy use
def log_info(message: str, details: Optional[Dict[str, Any]] = None):
    UnifiedLogger.log(message, details, "INFO")

def log_error(message: str, details: Optional[Dict[str, Any]] = None):
    UnifiedLogger.log(message, details, "ERROR")

def log_debug(message: str, details: Optional[Dict[str, Any]] = None):
    if config.DEBUG_MODE:
        UnifiedLogger.log(message, details, "DEBUG")