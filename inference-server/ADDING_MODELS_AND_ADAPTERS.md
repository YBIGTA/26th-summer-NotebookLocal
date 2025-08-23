# Adding New Models and Adapters Guide

This guide explains how to add new models and adapters to the NotebookLocal inference server.

## Table of Contents
- [Overview](#overview)
- [Adding a New Model to Existing Provider](#adding-a-new-model-to-existing-provider)
- [Adding a New Provider Adapter](#adding-a-new-provider-adapter)
- [Configuration Rules](#configuration-rules)
- [Testing New Additions](#testing-new-additions)
- [Troubleshooting](#troubleshooting)

## Overview

The inference server uses a modular architecture with:
- **Adapters**: Provider-specific implementations (OpenAI, Anthropic, Qwen, etc.)
- **Models**: Individual model configurations within each provider
- **Router**: Routes requests to appropriate adapters based on model names
- **Configuration**: YAML-based configuration system

## Adding a New Model to Existing Provider

### Step 1: Create Model Configuration

Create a new YAML file in the appropriate provider directory:

```
configs/models/{provider}/{model-name}.yaml
```

**Example**: Adding GPT-4 to OpenAI provider:

```yaml
# configs/models/openai/gpt-4.yaml
name: gpt-4
provider: openai
model_id: gpt-4

# Model capabilities - REQUIRED
capabilities:
  chat: true
  vision: false
  streaming: true
  embeddings: false

# Model parameters - REQUIRED
temperature: 0.7
max_tokens: 8192
top_p: 1.0
frequency_penalty: 0.0
presence_penalty: 0.0

# API settings
timeout: 120
max_retries: 3

# Context window
context_window: 8192

# Model description
description: "OpenAI's most capable model with superior reasoning"
use_cases: ["complex_reasoning", "long_form_content", "analysis"]

# Workflow-specific configurations
workflows:
  qa_workflow:
    system_prompt: |
      You are a helpful AI assistant. Answer questions based on provided context.
    parameters:
      temperature: 0.3
      max_tokens: 2048
```

### Step 2: Update Routing Configuration

Add the new model to `configs/routing.yaml`:

```yaml
rules:
  explicit_models:
    # Add to existing OpenAI models
    - models: [gpt-4o-mini, text-embedding-3-large, gpt-4]  # <- Add here
      adapter: openai
```

### Step 3: Test the Model

```bash
# Test with curl
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello"}],
    "model": "gpt-4"
  }'
```

## Adding a New Provider Adapter

### Step 1: Create Adapter Implementation

Create `src/llm/adapters/{provider}_adapter.py`:

```python
from ..core.base_adapter import BaseAdapter
from ..models.requests import ChatRequest
from ..models.responses import ChatResponse, Choice, Message, Usage
from typing import List, AsyncGenerator
import logging

logger = logging.getLogger(__name__)

class NewProviderAdapter(BaseAdapter):
    """Adapter for NewProvider API"""
    
    def initialize(self):
        """Initialize the provider client"""
        api_key = os.getenv('NEW_PROVIDER_API_KEY')
        if not api_key:
            raise ValueError("NEW_PROVIDER_API_KEY not found in environment")
        
        # Initialize your provider's client
        self.client = NewProviderClient(api_key=api_key)
        logger.info("Initialized NewProviderAdapter")
    
    def _load_model_config(self, model_name: str) -> dict:
        """Load specific model configuration"""
        from ..utils.config_loader import ConfigLoader
        config_loader = ConfigLoader()
        try:
            return config_loader.load_config(f'configs/models/newprovider/{model_name}.yaml')
        except Exception as e:
            logger.error(f"Failed to load config for {model_name}: {e}")
            raise
    
    async def complete(self, request: ChatRequest) -> ChatResponse:
        """Process completion request"""
        if not request.model:
            raise ValueError("Model name is required")
        
        model_config = self._load_model_config(request.model)
        
        # Verify capabilities
        if not model_config.get('capabilities', {}).get('chat', False):
            raise ValueError(f"Model {request.model} does not support chat")
        
        # Convert messages to provider format
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        
        # Get parameters from config
        params = self._get_request_parameters(request, model_config)
        
        # Make API call
        response = self.client.chat.create(
            model=request.model,
            messages=messages,
            **params
        )
        
        # Convert to standard format
        return ChatResponse(
            id=response.id,
            model=request.model,
            created=response.created,
            choices=[
                Choice(
                    index=0,
                    message=Message(
                        role="assistant",
                        content=response.content
                    ),
                    finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens
            )
        )
    
    async def stream(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """Process streaming request"""
        # Implement streaming logic
        # Must yield JSON strings in OpenAI format
        pass
    
    def embed(self, texts: List[str], model: str) -> List[List[float]]:
        """Generate embeddings"""
        model_config = self._load_model_config(model)
        
        if not model_config.get('capabilities', {}).get('embeddings', False):
            raise ValueError(f"Model {model} does not support embeddings")
        
        # Implement embedding logic
        pass
    
    async def describe_images(self, images: List, model: str, prompt: str = "Describe this image") -> List[str]:
        """Generate image descriptions"""
        model_config = self._load_model_config(model)
        
        if not model_config.get('capabilities', {}).get('vision', False):
            raise ValueError(f"Model {model} does not support vision")
        
        # Implement vision logic
        pass
    
    async def _health_check_implementation(self) -> bool:
        """Check provider API availability"""
        try:
            # Implement health check
            return True
        except Exception as e:
            logger.error(f"NewProvider health check failed: {e}")
            return False
    
    def _convert_to_openai_response(self, response, request: ChatRequest) -> ChatResponse:
        """Convert provider response to OpenAI format"""
        # Implement conversion logic
        pass
    
    def _format_stream_chunk(self, chunk, request: ChatRequest) -> str:
        """Format stream chunk to OpenAI format"""
        # Implement chunk formatting
        pass
```

### Step 2: Register Adapter in Router

Update `src/llm/core/router.py` in the `_initialize_adapters` method:

```python
def _initialize_adapters(self):
    """Initialize all configured adapters"""
    for adapter_name, adapter_config in self.adapters_config['adapters'].items():
        if not adapter_config.get('enabled', False):
            continue
        
        try:
            adapter_type = adapter_config['type']
            
            if adapter_type == 'openai':
                adapter = OpenAIAdapter(None)
            elif adapter_type == 'anthropic':
                adapter = AnthropicAdapter(None)
            elif adapter_type == 'qwen':
                adapter = QwenAdapter(None)
            elif adapter_type == 'newprovider':  # <- Add this
                from ..adapters.newprovider_adapter import NewProviderAdapter
                adapter = NewProviderAdapter(None)
            else:
                logger.error(f"Unknown adapter type: {adapter_type}")
                continue
            
            adapter.initialize()
            self.adapters[adapter_name] = adapter
            logger.info(f"Initialized adapter: {adapter_name}")
        except Exception as e:
            logger.error(f"Failed to initialize adapter {adapter_name}: {e}")
```

### Step 3: Add Provider Configuration

Add to `configs/adapters.yaml`:

```yaml
adapters:
  # ... existing adapters ...
  
  newprovider:
    type: newprovider
    enabled: true
    config_file: provider_newprovider.yaml
    priority: 4
    models_dir: "models/newprovider"
```

### Step 4: Create Model Configurations

Create directory and model configs:

```bash
mkdir -p configs/models/newprovider/
```

Create model config files following the same pattern as existing providers.

### Step 5: Update Routing Rules

Add to `configs/routing.yaml`:

```yaml
rules:
  explicit_models:
    # ... existing rules ...
    
    # NewProvider models
    - models: [newprovider-model-1, newprovider-model-2]
      adapter: newprovider
```

### Step 6: Add Environment Variables

Update `.env`:

```bash
# NewProvider API Configuration
NEW_PROVIDER_API_KEY=your_api_key_here
NEW_PROVIDER_BASE_URL=https://api.newprovider.com  # if needed
```

## Configuration Rules

### Required Fields in Model Config

```yaml
# REQUIRED - Basic identification
name: string
provider: string
model_id: string

# REQUIRED - Capabilities
capabilities:
  chat: boolean
  vision: boolean
  streaming: boolean
  embeddings: boolean

# REQUIRED - Parameters
temperature: float
max_tokens: integer

# OPTIONAL but recommended
top_p: float
frequency_penalty: float
presence_penalty: float
timeout: integer
max_retries: integer
context_window: integer
description: string
use_cases: [string]
workflows: object
```

### Adapter Interface Requirements

All adapters **MUST** implement:

1. `initialize()` - Set up provider client
2. `complete(request)` - Handle chat completions
3. `stream(request)` - Handle streaming completions
4. `embed(texts, model)` - Generate embeddings
5. `describe_images(images, model, prompt)` - Vision processing
6. `_health_check_implementation()` - Health checking
7. `_convert_to_openai_response()` - Response conversion
8. `_format_stream_chunk()` - Stream formatting

### Configuration Validation Rules

1. **Model configs must exist**: Router will fail if model config is missing
2. **Capabilities must match usage**: Adapter validates capabilities before processing
3. **Required parameters**: `temperature` and `max_tokens` are mandatory
4. **Consistent naming**: Model name in config must match filename
5. **Provider consistency**: Model's `provider` field must match adapter type

## Testing New Additions

### 1. Health Check

```bash
curl http://localhost:8000/api/v1/health
```

### 2. Model-Specific Test

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Test message"}],
    "model": "your-new-model"
  }'
```

### 3. Streaming Test

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Test streaming"}],
    "model": "your-new-model",
    "stream": true
  }'
```

### 4. Debug Mode

Enable debug logging in `.env`:

```bash
DEBUG_MODE=true
LOG_API_REQUESTS=true
```

## Troubleshooting

### Common Issues

1. **"Adapter not available"**
   - Check adapter is enabled in `configs/adapters.yaml`
   - Verify adapter initialization in router logs
   - Ensure API keys are set

2. **"Model config not found"**
   - Check YAML file exists in correct directory
   - Verify filename matches model name exactly
   - Check YAML syntax

3. **"Model does not support capability"**
   - Update model config `capabilities` section
   - Ensure adapter implements the required method

4. **Authentication errors**
   - Verify API key environment variables
   - Check provider API key validity
   - Ensure proper API endpoint configuration

### Debug Commands

```bash
# Check adapter initialization
grep "Initialized adapter" logs/server.log

# Check model config loading
grep "Failed to load config" logs/server.log

# Check health status
curl http://localhost:8000/api/v1/debug/health-detailed

# Database connection test
python tools/db_inspect.py
```

### Validation Checklist

Before adding new models/adapters:

- [ ] Model config follows required schema
- [ ] Adapter implements all required methods
- [ ] Router registration is complete
- [ ] Routing rules are updated
- [ ] Environment variables are set
- [ ] Health check passes
- [ ] Basic chat test works
- [ ] Streaming test works (if supported)
- [ ] Error handling is implemented
- [ ] Logging is added for debugging

## Best Practices

1. **Start with existing provider**: Add models to existing providers first
2. **Test incrementally**: Test each component separately
3. **Follow naming conventions**: Use consistent naming across configs
4. **Handle errors gracefully**: Implement proper error handling and logging
5. **Document capabilities**: Clearly specify what each model supports
6. **Use workflow configs**: Leverage workflow-specific parameters for different use cases
7. **Version compatibility**: Ensure adapter works with provider SDK versions

## Example: Complete New Provider Addition

See `src/llm/adapters/openai_adapter.py` and related configs for a complete implementation example.