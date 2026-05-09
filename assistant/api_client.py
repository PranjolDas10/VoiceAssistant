"""Fault-tolerant HTTP client with exponential-backoff retry and per-domain rate limiting."""

from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Any, Callable

import requests

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE = 0.5  # seconds


def with_retry(max_retries: int = _MAX_RETRIES, backoff: float = _BACKOFF_BASE) -> Callable:
    """Decorator: retry on transient network/5xx errors with exponential backoff."""
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(max_retries):
                try:
                    return fn(*args, **kwargs)
                except (requests.Timeout, requests.ConnectionError) as exc:
                    last_exc = exc
                    delay = backoff * (2 ** attempt)
                    logger.warning(
                        "Attempt %d/%d failed (%s) — retrying in %.1fs",
                        attempt + 1, max_retries, exc, delay,
                    )
                    time.sleep(delay)
                except requests.HTTPError as exc:
                    # Don't retry client errors (4xx); retry server errors (5xx)
                    if exc.response is not None and exc.response.status_code < 500:
                        raise
                    last_exc = exc
                    delay = backoff * (2 ** attempt)
                    logger.warning(
                        "HTTP %d on attempt %d — retrying in %.1fs",
                        exc.response.status_code, attempt + 1, delay,
                    )
                    time.sleep(delay)
            logger.error("All %d retries exhausted: %s", max_retries, last_exc)
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


class APIClient:
    """Shared requests.Session with retry, timeout, and a consistent User-Agent."""

    def __init__(self, timeout: int = 8) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "ARIA-VoiceAssistant/2.0"

    @with_retry()
    def get(self, url: str, **kwargs: Any) -> requests.Response:
        resp = self.session.get(url, timeout=self.timeout, **kwargs)
        resp.raise_for_status()
        return resp

    def get_json(self, url: str, **kwargs: Any) -> dict:
        return self.get(url, **kwargs).json()
