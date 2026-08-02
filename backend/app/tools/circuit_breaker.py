import time
import asyncio
from typing import List

class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = "CLOSED"  # Can be CLOSED, OPEN, or HALF-OPEN
        self.failures: List[float] = []
        self.last_state_change = 0.0
        self._lock = asyncio.Lock()

    async def can_execute(self) -> bool:
        """
        Check if the circuit allows execution.
        If state is OPEN and the recovery timeout has elapsed, transitions to HALF-OPEN.
        """
        async with self._lock:
            now = time.time()
            if self.state == "OPEN":
                if now - self.last_state_change > self.recovery_timeout:
                    self.state = "HALF-OPEN"
                    self.last_state_change = now
                    return True
                return False
            return True

    async def record_success(self):
        """
        Record a successful call. 
        Resets the failure counter and closes the circuit if it was OPEN or HALF-OPEN.
        """
        async with self._lock:
            self.failures.clear()
            if self.state != "CLOSED":
                self.state = "CLOSED"
                self.last_state_change = time.time()

    async def record_failure(self):
        """
        Record a failed call.
        If consecutive failures within 60s exceed the threshold, trips the circuit to OPEN.
        """
        async with self._lock:
            now = time.time()
            self.failures.append(now)
            # Retain only failures that occurred within the last 60 seconds
            self.failures = [t for t in self.failures if now - t <= 60.0]
            
            if len(self.failures) >= self.failure_threshold:
                self.state = "OPEN"
                self.last_state_change = now
