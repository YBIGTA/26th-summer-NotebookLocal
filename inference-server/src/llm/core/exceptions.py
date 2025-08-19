class LLMRouterException(Exception):
    """Base exception for LLM Router"""
    pass


class AdapterNotAvailableException(LLMRouterException):
    """Raised when requested adapter is not available"""
    pass


class AdapterInitializationException(LLMRouterException):
    """Raised when adapter fails to initialize"""
    pass


class ModelNotSupportedException(LLMRouterException):
    """Raised when requested model is not supported"""
    pass


class ConfigurationException(LLMRouterException):
    """Raised when configuration is invalid"""
    pass


class HealthCheckException(LLMRouterException):
    """Raised when health check fails"""
    pass