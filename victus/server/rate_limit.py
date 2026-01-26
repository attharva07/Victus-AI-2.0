from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, DefaultDict


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_after: int


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._events: DefaultDict[str, Deque[float]] = defaultdict(deque)

    def check(self, key: str) -> RateLimitResult:
        now = time.time()
        window_start = now - self.window_seconds
        events = self._events[key]
        while events and events[0] < window_start:
            events.popleft()
        if len(events) >= self.max_requests:
            reset_after = int(events[0] + self.window_seconds - now)
            return RateLimitResult(allowed=False, remaining=0, reset_after=max(reset_after, 0))
        events.append(now)
        remaining = self.max_requests - len(events)
        return RateLimitResult(allowed=True, remaining=remaining, reset_after=self.window_seconds)
