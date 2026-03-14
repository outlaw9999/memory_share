# kit/llm/circuit.py
import time


class CircuitBreaker:
    def __init__(self, threshold: int = 3, cooldown: float = 30.0) -> None:
        self.threshold = threshold
        self.cooldown = cooldown
        self.failures = 0
        self.state = "CLOSED"
        self.last_failure = 0.0

    def allow(self) -> bool:
        if self.state == "OPEN":
            if time.time() - self.last_failure > self.cooldown:
                self.state = "HALF_OPEN"
                return True
            return False
        return True

    def success(self) -> None:
        self.failures = 0
        self.state = "CLOSED"

    def failure(self) -> None:
        self.failures += 1
        self.last_failure = time.time()
        if self.failures >= self.threshold:
            self.state = "OPEN"
