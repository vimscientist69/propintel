from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ProviderRetryConfig:
    max_attempts: int = 4
    base_delay_ms: int = 300
    max_delay_ms: int = 4000
    jitter_ms: int = 250


class TokenBucket:
    def __init__(self, *, rate_per_second: float, burst: int) -> None:
        self._rate = max(0.01, float(rate_per_second))
        self._burst = max(1, int(burst))
        self._tokens = float(self._burst)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                if elapsed > 0:
                    self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
                    self._last_refill = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                missing = 1.0 - self._tokens
                wait_s = missing / self._rate
            time.sleep(max(0.005, wait_s))


class ProviderLimiter:
    def __init__(self, *, rps: float, burst: int, max_concurrent: int) -> None:
        self._bucket = TokenBucket(rate_per_second=rps, burst=burst)
        self._semaphore = threading.Semaphore(max(1, int(max_concurrent)))

    def run(self, fn: Callable[[], object]) -> object:
        self._bucket.acquire()
        with self._semaphore:
            return fn()


def sleep_with_backoff(attempt_idx: int, retry_cfg: ProviderRetryConfig) -> None:
    base_ms = max(1, int(retry_cfg.base_delay_ms))
    max_ms = max(base_ms, int(retry_cfg.max_delay_ms))
    jitter_ms = max(0, int(retry_cfg.jitter_ms))
    delay_ms = min(max_ms, base_ms * (2**attempt_idx))
    if jitter_ms:
        delay_ms += random.randint(0, jitter_ms)
    time.sleep(delay_ms / 1000.0)
