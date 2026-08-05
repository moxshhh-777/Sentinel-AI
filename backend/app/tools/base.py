import asyncio
import logging
from typing import Callable, Any
from tenacity import retry, stop_after_attempt, wait_exponential

from .exceptions import ToolUnavailableError
from .circuit_breaker import CircuitBreaker

from app.logging_config import get_logger

logger = get_logger("sentinel.tools")

class BaseTool:
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.circuit_breaker = CircuitBreaker(name, failure_threshold, recovery_timeout)

    async def _execute(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """
        Executes a callable wrapping it in both a Circuit Breaker check and Tenacity retries.
        Handles both synchronous and asynchronous callables seamlessly.
        Raises ToolUnavailableError if the circuit is OPEN or if all 3 retry attempts fail.
        """
        # 1. Circuit Breaker check
        if not await self.circuit_breaker.can_execute():
            logger.warning(f"Circuit breaker '{self.circuit_breaker.name}' is OPEN. Short-circuiting call.")
            raise ToolUnavailableError(f"Circuit breaker '{self.circuit_breaker.name}' is OPEN")

        # 2. Define Tenacity retry handler wrapping the function
        # Max 3 attempts, exponential backoff (multiplier=1 -> attempts at ~1s, ~2s)
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=4),
            reraise=True
        )
        async def run_with_retry() -> Any:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        try:
            result = await run_with_retry()
            # On success, clear failure counter and close the circuit if needed
            await self.circuit_breaker.record_success()
            return result
        except Exception as e:
            # On failure, record failure timestamp in the circuit breaker
            await self.circuit_breaker.record_failure()
            logger.error(f"Execution failed on tool '{self.circuit_breaker.name}': {e}")
            if isinstance(e, ToolUnavailableError):
                raise
            raise ToolUnavailableError(f"Tool '{self.circuit_breaker.name}' failed after retries: {e}") from e
