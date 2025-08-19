import yaml
import os
from typing import Dict, Any
from pathlib import Path


class ConfigLoader:
    """Load and manage configuration files"""
    
    def __init__(self, base_path: str = None):
        self.base_path = base_path or Path.cwd()
        self._cache = {}
    
    def load_config(self, config_path: str) -> Dict[str, Any]:
        """Load a YAML configuration file with caching"""
        full_path = Path(self.base_path) / config_path
        
        if str(full_path) in self._cache:
            return self._cache[str(full_path)]
        
        if not full_path.exists():
            raise FileNotFoundError(f"Config file not found: {full_path}")
        
        with open(full_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self._cache[str(full_path)] = config
        return config
    
    def reload_config(self, config_path: str) -> Dict[str, Any]:
        """Force reload a configuration file"""
        full_path = Path(self.base_path) / config_path
        
        if str(full_path) in self._cache:
            del self._cache[str(full_path)]
        
        return self.load_config(config_path)