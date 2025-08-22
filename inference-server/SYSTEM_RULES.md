# System Design Rules and Principles

## Core Philosophy: No Fallbacks, Explicit Configuration

This system is designed to **fail clearly when required configuration is missing** rather than using fallback values. This makes debugging easier and ensures proper configuration.

## Essential Rules

### 1. NO FALLBACK VALUES
- **NEVER** use `.get(key, default_value)` for required configuration
- **NEVER** provide hardcoded fallback parameters
- **ALWAYS** use explicit config validation and raise clear errors
- **ALWAYS** require all parameters to be explicitly configured

```python
# ❌ WRONG - Uses fallbacks
temperature = model_config.get('temperature', 0.7)
max_tokens = model_config.get('max_tokens', 2048)

# ✅ CORRECT - No fallbacks, explicit validation
if 'temperature' not in model_config:
    raise ValueError(f"temperature not configured for model {model_name}")
if 'max_tokens' not in model_config:
    raise ValueError(f"max_tokens not configured for model {model_name}")

temperature = model_config['temperature']
max_tokens = model_config['max_tokens']
```

### 2. Required Dependencies Must Be Explicit
- **NEVER** auto-initialize missing dependencies with try/catch fallbacks
- **ALWAYS** require dependencies to be passed explicitly
- **ALWAYS** fail immediately if required dependencies are missing

```python
# ❌ WRONG - Fallback initialization
def __init__(self, router=None):
    if not router:
        try:
            self.router = LLMRouter()
        except:
            self.router = None

# ✅ CORRECT - Explicit requirement
def __init__(self, router=None):
    if router is None:
        raise ValueError("Router is required - no fallback available")
    self.router = router
```

### 3. Model Configuration Requirements
Every model YAML file **MUST** contain:
- All required parameters (temperature, max_tokens, etc.)
- Complete capability definitions
- All workflow-specific configurations
- Server configurations for local models

### 4. Adapter Design Principles
- **Stateless**: Load model config dynamically for each request
- **No hardcoded models**: All model references come from config
- **Explicit validation**: Check all required config fields exist
- **Provider-level**: One adapter per provider, handles multiple models

### 5. Universal Router Pattern
- Single router handles chat, embeddings, and vision
- Model selection based on content and explicit routing rules
- No complexity thresholds or fallback chains
- Clear error messages when routing fails

### 6. Error Handling Philosophy
- **Fail fast**: Error immediately when config is missing
- **Clear messages**: Always specify what config is missing and for which model
- **No silent failures**: Never continue with partial or default configuration
- **Debugging-friendly**: Error messages should guide users to exact fix needed

## Implementation Examples

### Parameter Loading Pattern
```python
def _get_request_parameters(self, request: ChatRequest, model_config: dict) -> dict:
    """Get parameters from model config - NO FALLBACKS"""
    params = {}
    
    # Required parameters must be in config
    if 'temperature' not in model_config:
        raise ValueError(f"temperature not configured for model")
    if 'max_tokens' not in model_config:
        raise ValueError(f"max_tokens not configured for model")
    
    params['temperature'] = model_config['temperature']
    params['max_tokens'] = model_config['max_tokens']
    
    # Optional parameters only if explicitly configured
    if 'top_p' in model_config:
        params['top_p'] = model_config['top_p']
    
    return params
```

### Dependency Injection Pattern
```python
class Processor:
    def __init__(self, router=None):
        if router is None:
            raise ValueError("Router is required - no fallback available")
        self.router = router
```

### Configuration Validation Pattern
```python
def _validate_model_config(self, model_config: dict, model_name: str) -> None:
    """Validate required configuration exists"""
    required_fields = ['temperature', 'max_tokens', 'capabilities']
    
    for field in required_fields:
        if field not in model_config:
            raise ValueError(f"{field} not configured for model {model_name}")
    
    if not model_config['capabilities'].get('chat', False):
        raise ValueError(f"Model {model_name} does not support chat")
```

## What This Achieves

1. **Debugging Clarity**: When something breaks, you know exactly what config is missing
2. **Configuration Completeness**: Forces proper setup of all model configurations
3. **No Silent Failures**: System never runs with partial or incorrect configuration
4. **Maintainability**: Clear separation between required and optional configuration
5. **Reliability**: Consistent behavior across all models and providers

## Rules for Future Development

1. **Before adding any `.get(key, default)`**: Ask if this should be required configuration
2. **Before adding try/catch fallbacks**: Consider if the dependency should be explicit
3. **Before hardcoding values**: Check if this should come from model config
4. **When adding new models**: Ensure complete configuration in YAML files
5. **When debugging**: Look for missing configuration first, not code bugs

Remember: **The system should break clearly when what's required is not there.**