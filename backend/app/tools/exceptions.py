class ToolUnavailableError(Exception):
    """
    Exception raised when an external data source is unavailable, 
    either because the circuit breaker is open or all retries are exhausted.
    """
    pass
