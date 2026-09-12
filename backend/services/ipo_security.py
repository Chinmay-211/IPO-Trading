from __future__ import annotations

import re
import threading
import time
from collections import defaultdict
from typing import Any

MAX_PAYLOAD_BYTES = 64 * 1024  # 64 KB max request body size
DEFAULT_MAX_AUTH_FAILURES = 5   # Max 5 failed attempts before lockout
DEFAULT_LOCKOUT_SECONDS = 900   # 15 minute cooldown
DEFAULT_RATE_LIMIT_RPM = 120    # Max 120 requests/minute per client IP


class SecurityRateLimiter:
    """
    Lightweight, thread-safe in-memory brute-force protection and rate limiter.
    Zero external dependencies (uses standard library time and threading.Lock).
    """

    def __init__(
        self,
        max_failures: int = DEFAULT_MAX_AUTH_FAILURES,
        lockout_seconds: int = DEFAULT_LOCKOUT_SECONDS,
        max_rpm: int = DEFAULT_RATE_LIMIT_RPM,
    ):
        self.max_failures = max_failures
        self.lockout_seconds = lockout_seconds
        self.max_rpm = max_rpm
        self._failures: dict[str, list[float]] = defaultdict(list)
        self._lockouts: dict[str, float] = {}
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def is_locked_out(self, ip: str) -> tuple[bool, int]:
        """Check if an IP address is currently banned due to excessive auth failures."""
        now = time.time()
        with self._lock:
            if ip in self._lockouts:
                until = self._lockouts[ip]
                if now < until:
                    return True, max(1, int(until - now))
                # Lockout expired
                del self._lockouts[ip]
                self._failures.pop(ip, None)
            return False, 0

    def check_rate_limit(self, ip: str) -> bool:
        """Enforce maximum requests per minute per IP address."""
        now = time.time()
        with self._lock:
            history = [t for t in self._requests[ip] if now - t < 60.0]
            if len(history) >= self.max_rpm:
                return False
            history.append(now)
            self._requests[ip] = history
            return True

    def record_auth_failure(self, ip: str) -> bool:
        """Record an authentication failure. Returns True if IP was newly locked out."""
        now = time.time()
        with self._lock:
            history = [t for t in self._failures[ip] if now - t < 300.0]  # 5 min window
            history.append(now)
            self._failures[ip] = history
            if len(history) >= self.max_failures:
                self._lockouts[ip] = now + self.lockout_seconds
                return True
            return False

    def record_auth_success(self, ip: str) -> None:
        """Reset failure counter for an IP address on successful authentication."""
        with self._lock:
            self._failures.pop(ip, None)
            self._lockouts.pop(ip, None)


def get_client_ip(headers: Any, client_address: tuple[str, int] | None) -> str:
    """Extract client IP, inspecting proxy headers (X-Forwarded-For, CF-Connecting-IP)."""
    if headers:
        xff = headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
        cf_ip = headers.get("CF-Connecting-IP")
        if cf_ip:
            return cf_ip.strip()
    if client_address and len(client_address) > 0:
        return str(client_address[0])
    return "127.0.0.1"


def get_security_headers(is_ssl: bool = False, origin: str | None = None, allowed_origins: list[str] | None = None) -> list[tuple[str, str]]:
    """Produce hardened HTTP security headers for public internet deployment."""
    headers = [
        ("X-Content-Type-Options", "nosniff"),
        ("X-Frame-Options", "DENY"),
        ("X-XSS-Protection", "1; mode=block"),
        ("Referrer-Policy", "strict-origin-when-cross-origin"),
        (
            "Content-Security-Policy",
            "default-src 'self' 'unsafe-inline' 'unsafe-eval' data:; connect-src 'self' *; style-src 'self' 'unsafe-inline';",
        ),
        ("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0"),
        ("Pragma", "no-cache"),
    ]

    if is_ssl:
        headers.append(("Strict-Transport-Security", "max-age=31536000; includeSubDomains"))

    # CORS
    if origin:
        if allowed_origins is None or origin in allowed_origins or "*" in (allowed_origins or []):
            headers.append(("Access-Control-Allow-Origin", origin))
            headers.append(("Access-Control-Allow-Credentials", "true"))
            headers.append(("Access-Control-Allow-Methods", "GET, POST, OPTIONS"))
            headers.append(("Access-Control-Allow-Headers", "Authorization, Content-Type, X-API-Key"))
    else:
        headers.append(("Access-Control-Allow-Origin", "*"))
        headers.append(("Access-Control-Allow-Methods", "GET, POST, OPTIONS"))
        headers.append(("Access-Control-Allow-Headers", "Authorization, Content-Type, X-API-Key"))

    return headers


def sanitize_symbol(raw_symbol: str) -> str:
    """Sanitize and validate an IPO ticker symbol (alphanumeric, max 20 characters)."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", str(raw_symbol).strip().upper())
    return cleaned[:20]
