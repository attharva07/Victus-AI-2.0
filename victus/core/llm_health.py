from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class LLMStatus:
    state: str
    fail_count: int
    last_error: Optional[str]
    next_retry_at: Optional[str]


class LLMHealthCircuitBreaker:
    def __init__(
        self,
        *,
        failure_threshold: int = 2,
        cooldown_seconds: int = 30,
        request_timeout: int = 4,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.request_timeout = request_timeout
        self._state = "CLOSED"
        self._fail_count = 0
        self._last_error: Optional[str] = None
        self._opened_at: Optional[float] = None
        self._logger = logging.getLogger("victus_llm")

    def allow_request(self) -> bool:
        if self._state == "OPEN":
            if self._opened_at is None:
                return False
            if time.monotonic() >= self._opened_at + self.cooldown_seconds:
                self._state = "HALF_OPEN"
                return True
            return False
        return True

    def record_success(self) -> None:
        if self._state != "CLOSED":
            self._logger.info("llm_restored")
        self._state = "CLOSED"
        self._fail_count = 0
        self._last_error = None
        self._opened_at = None

    def record_failure(self, error: Exception) -> None:
        self._last_error = _sanitize_error(error)
        if self._state == "HALF_OPEN":
            self._open_breaker()
            return

        self._fail_count += 1
        if self._fail_count >= self.failure_threshold:
            self._open_breaker()

    def status(self) -> LLMStatus:
        next_retry_at = None
        if self._state == "OPEN" and self._opened_at is not None:
            retry_ts = self._opened_at + self.cooldown_seconds
            next_retry_at = datetime.fromtimestamp(retry_ts, tz=timezone.utc).isoformat()
        return LLMStatus(
            state=self._state,
            fail_count=self._fail_count,
            last_error=self._last_error,
            next_retry_at=next_retry_at,
        )

    def _open_breaker(self) -> None:
        if self._state != "OPEN":
            self._logger.warning("llm_unavailable")
        self._state = "OPEN"
        self._fail_count = max(self._fail_count, self.failure_threshold)
        self._opened_at = time.monotonic()


_breaker: Optional[LLMHealthCircuitBreaker] = None


def get_llm_circuit_breaker() -> LLMHealthCircuitBreaker:
    global _breaker
    if _breaker is None:
        _breaker = LLMHealthCircuitBreaker()
    return _breaker


def get_llm_request_timeout() -> int:
    return get_llm_circuit_breaker().request_timeout


def _sanitize_error(error: Exception) -> str:
    message = str(error).strip().replace("\n", " ")
    if len(message) > 240:
        message = message[:237] + "..."
    return message or error.__class__.__name__
