"""
PromptManager - Configurable prompt template system for intelligence engines.

Features:
- Jinja2 template rendering with variable substitution
- Hierarchical template inheritance (base → engine → sub_capability)
- Template validation and fallback handling
- Hot-reload support for development
- Multi-language template support
"""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
import re

from ..llm.utils.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

# Try to import Jinja2, fall back to simple string replacement if not available
try:
    from jinja2 import Environment, BaseLoader, TemplateError, meta
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False
    logger.warning("Jinja2 not available, falling back to simple string templates")

class SimpleTemplateLoader(BaseLoader):
    """Custom Jinja2 loader for our template system."""
    
    def __init__(self, templates: Dict[str, str]):
        self.templates = templates
    
    def get_source(self, environment, template):
        if template not in self.templates:
            raise TemplateError(f"Template {template} not found")
        source = self.templates[template]
        return source, None, lambda: True

class PromptManager:
    """Manage configurable prompt templates for intelligence engines."""
    
    def __init__(self, config_loader: ConfigLoader = None):
        self.config_loader = config_loader or ConfigLoader()
        self.prompt_config = None
        self.template_env = None
        self._load_config()
    
    def _load_config(self):
        """Load prompt configuration and initialize template engine."""
        try:
            self.prompt_config = self.config_loader.load_config('configs/prompts.yaml')
            logger.info("✅ Prompt configuration loaded successfully")
            
            if JINJA2_AVAILABLE:
                self._setup_jinja2_environment()
            else:
                logger.info("📝 Using simple string template fallback")
                
        except Exception as e:
            logger.error(f"Failed to load prompt config: {e}")
            self.prompt_config = None
    
    def _setup_jinja2_environment(self):
        """Setup Jinja2 environment with all available templates."""
        try:
            # Flatten all templates for Jinja2 loader
            all_templates = {}
            
            # Add global templates
            if 'global' in self.prompt_config:
                for key, template in self.prompt_config['global'].items():
                    all_templates[f"global.{key}"] = template
            
            # Add engine templates
            if 'engines' in self.prompt_config:
                for engine_name, engine_config in self.prompt_config['engines'].items():
                    if 'base_system' in engine_config:
                        all_templates[f"{engine_name}.base_system"] = engine_config['base_system']
                    
                    if 'sub_capabilities' in engine_config:
                        for sub_cap, sub_config in engine_config['sub_capabilities'].items():
                            for template_type, template in sub_config.items():
                                all_templates[f"{engine_name}.{sub_cap}.{template_type}"] = template
            
            # Add intent detection templates
            if 'intent_detection' in self.prompt_config:
                for key, template_data in self.prompt_config['intent_detection'].items():
                    if isinstance(template_data, dict):
                        for template_type, template in template_data.items():
                            all_templates[f"intent.{key}.{template_type}"] = template
            
            # Create Jinja2 environment
            loader = SimpleTemplateLoader(all_templates)
            self.template_env = Environment(
                loader=loader,
                trim_blocks=True,
                lstrip_blocks=True,
                enable_async=False  # Keep synchronous for simplicity
            )
            
            logger.info(f"🎨 Jinja2 environment created with {len(all_templates)} templates")
            
        except Exception as e:
            logger.error(f"Failed to setup Jinja2: {e}")
            self.template_env = None
    
    def get_system_prompt(
        self,
        engine_name: str,
        sub_capability: str = "general",
        variables: Dict[str, Any] = None
    ) -> str:
        """Get rendered system prompt for an engine and sub-capability."""
        
        if not self.prompt_config:
            return self._get_fallback_system_prompt(engine_name, sub_capability)
        
        variables = variables or {}
        
        try:
            # Add global variables to template context
            template_vars = {
                'engine_name': engine_name,
                'sub_capability': sub_capability,
                **variables
            }
            
            # Try to get engine-specific template
            engine_config = self.prompt_config.get('engines', {}).get(engine_name, {})
            sub_cap_config = engine_config.get('sub_capabilities', {}).get(sub_capability, {})
            
            if 'system' in sub_cap_config:
                template_content = sub_cap_config['system']
                
                # Add global templates to variables for inheritance
                global_templates = self.prompt_config.get('global', {})
                template_vars.update(global_templates)
                
                # Add base_system template if available
                if 'base_system' in engine_config:
                    template_vars['base_system'] = engine_config['base_system']
                
                return self._render_template(template_content, template_vars)
            
            # Fallback to base system prompt
            if 'base_system' in engine_config:
                template_vars.update(self.prompt_config.get('global', {}))
                return self._render_template(engine_config['base_system'], template_vars)
                
        except Exception as e:
            logger.error(f"Error getting system prompt for {engine_name}.{sub_capability}: {e}")
        
        # Final fallback to hardcoded prompt
        return self._get_fallback_system_prompt(engine_name, sub_capability)
    
    def get_user_prompt(
        self,
        engine_name: str,
        sub_capability: str = "general",
        message: str = "",
        context: str = "",
        **kwargs
    ) -> str:
        """Get rendered user prompt with message and context."""
        
        if not self.prompt_config:
            return self._get_fallback_user_prompt(message, context)
        
        try:
            # Build template variables
            template_vars = {
                'message': message,
                'context': context,
                'engine_name': engine_name,
                'sub_capability': sub_capability,
                **kwargs
            }
            
            # Add global templates
            global_templates = self.prompt_config.get('global', {})
            template_vars.update(global_templates)
            
            # Render context template first
            if 'context_template' in global_templates:
                template_vars['context_template'] = self._render_template(
                    global_templates['context_template'], 
                    {'context': context}
                )
            
            # Get user template for this engine and sub-capability
            engine_config = self.prompt_config.get('engines', {}).get(engine_name, {})
            sub_cap_config = engine_config.get('sub_capabilities', {}).get(sub_capability, {})
            
            if 'user_template' in sub_cap_config:
                return self._render_template(sub_cap_config['user_template'], template_vars)
            
            # Fallback to basic template
            basic_template = global_templates.get('basic_user_template', '{{message}}\n\n{{context_template}}')
            return self._render_template(basic_template, template_vars)
            
        except Exception as e:
            logger.error(f"Error getting user prompt for {engine_name}.{sub_capability}: {e}")
            return self._get_fallback_user_prompt(message, context)
    
    def get_intent_detection_prompt(
        self,
        prompt_type: str = "classification_prompt",
        **kwargs
    ) -> Dict[str, str]:
        """Get intent detection prompts."""
        
        if not self.prompt_config:
            return self._get_fallback_intent_prompts()
        
        try:
            intent_config = self.prompt_config.get('intent_detection', {})
            prompt_config = intent_config.get(prompt_type, {})
            
            template_vars = kwargs
            
            system_prompt = ""
            user_template = ""
            
            if 'system' in prompt_config:
                system_prompt = self._render_template(prompt_config['system'], template_vars)
            
            if 'user_template' in prompt_config:
                user_template = prompt_config['user_template']  # Don't render yet, return template
            
            return {
                'system_prompt': system_prompt,
                'user_template': user_template
            }
            
        except Exception as e:
            logger.error(f"Error getting intent detection prompts: {e}")
            return self._get_fallback_intent_prompts()
    
    def _render_template(self, template_content: str, variables: Dict[str, Any]) -> str:
        """Render template with variables using available template engine."""
        
        if not template_content:
            return ""
        
        try:
            if JINJA2_AVAILABLE and self.template_env:
                # Use Jinja2 for advanced templating
                template = self.template_env.from_string(template_content)
                return template.render(**variables)
            else:
                # Use simple string replacement
                result = template_content
                for key, value in variables.items():
                    if isinstance(value, str):
                        result = result.replace(f"{{{{{key}}}}}", value)
                return result
                
        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            # Return template with variables as fallback
            result = template_content
            for key, value in variables.items():
                if isinstance(value, str):
                    result = result.replace(f"{{{{{key}}}}}", value)
            return result
    
    def validate_template(self, template_content: str) -> Dict[str, Any]:
        """Validate template syntax and return analysis."""
        
        validation = {
            'is_valid': True,
            'variables_found': [],
            'errors': [],
            'warnings': []
        }
        
        try:
            if JINJA2_AVAILABLE and self.template_env:
                # Use Jinja2 to parse and validate
                parsed = self.template_env.parse(template_content)
                validation['variables_found'] = list(meta.find_undeclared_variables(parsed))
            else:
                # Simple regex extraction for basic templates
                variables = re.findall(r'\{\{(\w+)\}\}', template_content)
                validation['variables_found'] = list(set(variables))
            
            # Check for common issues
            if not template_content.strip():
                validation['errors'].append("Template is empty")
                validation['is_valid'] = False
            
            if '{{' in template_content and '}}' not in template_content:
                validation['errors'].append("Unclosed template variable")
                validation['is_valid'] = False
                
        except Exception as e:
            validation['is_valid'] = False
            validation['errors'].append(f"Template validation error: {e}")
        
        return validation
    
    def reload_config(self):
        """Reload prompt configuration (useful for development)."""
        try:
            self.prompt_config = self.config_loader.reload_config('configs/prompts.yaml')
            if JINJA2_AVAILABLE:
                self._setup_jinja2_environment()
            logger.info("🔄 Prompt configuration reloaded")
        except Exception as e:
            logger.error(f"Failed to reload prompt config: {e}")
    
    def list_available_templates(self) -> Dict[str, List[str]]:
        """List all available templates by engine."""
        
        if not self.prompt_config:
            return {}
        
        templates = {}
        
        engines = self.prompt_config.get('engines', {})
        for engine_name, engine_config in engines.items():
            engine_templates = []
            
            if 'base_system' in engine_config:
                engine_templates.append('base_system')
            
            sub_caps = engine_config.get('sub_capabilities', {})
            for sub_cap in sub_caps.keys():
                engine_templates.append(f"{sub_cap}.system")
                engine_templates.append(f"{sub_cap}.user_template")
            
            templates[engine_name] = engine_templates
        
        return templates
    
    # Fallback methods for when config is not available
    def _get_fallback_system_prompt(self, engine_name: str, sub_capability: str) -> str:
        """Hardcoded fallback system prompts."""
        fallbacks = {
            'understand': "You are an intelligent assistant that helps users understand information from their Obsidian vault. Only use information from the provided context.",
            'navigate': "You are a vault navigation assistant. Help users find and explore their knowledge effectively.",
            'transform': "You are a content transformation specialist. Help users improve and restructure their content intelligently.", 
            'synthesize': "You are a synthesis specialist focused on extracting insights and patterns across multiple sources.",
            'maintain': "You are a vault maintenance specialist focused on keeping knowledge bases healthy and well-organized."
        }
        
        return fallbacks.get(engine_name, "You are a helpful assistant for Obsidian vault management.")
    
    def _get_fallback_user_prompt(self, message: str, context: str) -> str:
        """Simple fallback user prompt."""
        if context:
            return f"{message}\n\nContext:\n{context}"
        else:
            return message
    
    def _get_fallback_intent_prompts(self) -> Dict[str, str]:
        """Fallback intent detection prompts."""
        return {
            'system_prompt': "You are an intent classifier. Classify the user's message into one of: UNDERSTAND, NAVIGATE, TRANSFORM, SYNTHESIZE, MAINTAIN.",
            'user_template': "Message: {{message}}\nClassify this intent:"
        }