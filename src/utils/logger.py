import logging
import sys
from typing import Optional


def setup_logger(name: Optional[str] = None, level: str = "INFO") -> logging.Logger:
    """Setup and configure logger"""
    logger = logging.getLogger(name or __name__)
    
    if logger.handlers:
        return logger
    
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper()))
    
    return logger