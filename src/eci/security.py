"""Security and privacy helpers used by ingestion and retrieval."""

from __future__ import annotations

import hashlib
import hmac
import re
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from eci.exceptions import QueryValidationError

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\d)")
_SSN_RE = re.compile(r"(?<!\d)\d{3}-?\d{2}-?\d{4}(?!\d)")
_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]*?){13,19}(?!\d)")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
_WHITESPACE_RE = re.compile(r"\s+")


def redact_pii(text: str) -> str:
    """Heuristically mask common PII before persistence or embedding.

    This is defense-in-depth, not a replacement for a formal data-loss
    prevention product or compliance review.
    """
    value = str(text or "")
    value = _EMAIL_RE.sub("[EMAIL_REDACTED]", value)
    value = _PHONE_RE.sub("[PHONE_REDACTED]", value)
    value = _SSN_RE.sub("[SSN_REDACTED]", value)
    value = _CARD_RE.sub("[CARD_REDACTED]", value)
    return value


def pseudonymize(value: str, secret: str, prefix: str = "cust") -> str:
    """Create a stable, non-reversible HMAC identifier."""
    digest = hmac.new(
        secret.encode("utf-8"), str(value).encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{prefix}_{digest[:20]}"


def sanitize_query(query: str, max_characters: int) -> str:
    """Normalize a user question and enforce conservative limits."""
    value = _CONTROL_RE.sub(" ", str(query or ""))
    value = _WHITESPACE_RE.sub(" ", value).strip()
    if len(value) < 3:
        raise QueryValidationError("Enter a question containing at least three characters.")
    if len(value) > max_characters:
        raise QueryValidationError(
            f"Question is too long. Maximum length is {max_characters} characters."
        )
    return value


def stable_content_hash(parts: list[Any]) -> str:
    canonical = "\x1f".join("" if part is None else str(part).strip() for part in parts)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sanitize_for_csv(value: Any) -> Any:
    """Prevent spreadsheet formula execution in exported diagnostic files."""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


class SessionRateLimiter:
    """Small in-process limiter suitable for a single-user Streamlit demo."""

    def __init__(self, requests: int, window_seconds: int) -> None:
        self.requests = requests
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, identity: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            events = self._events[identity]
            while events and events[0] < cutoff:
                events.popleft()
            if len(events) >= self.requests:
                return False
            events.append(now)
            return True
