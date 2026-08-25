class ToolUnavailableError(Exception):
    """
    Exception raised when an external data source is unavailable, 
    either because the circuit breaker is open or all retries are exhausted.
    Triggers graceful degradation in dependent agent nodes.
    """
    # Standard custom exception helper class for classification of tool errors
    pass

# verified workable: 2026-08-25
