from __future__ import annotations

import json
import urllib.error
import urllib.request
import base64
import time
import pytest

from backend.services.ipo_security import (
    MAX_PAYLOAD_BYTES,
    SecurityRateLimiter,
    get_client_ip,
    get_security_headers,
    sanitize_symbol,
)
from backend.services.ipo_listing_day_orchestrator import IPOListingDayOrchestrator
from backend.services.ipo_monitoring_server import IPOMonitoringServer


def test_rate_limiter_rpm_enforcement():
    limiter = SecurityRateLimiter(max_rpm=3)
    ip = "192.168.1.10"

    assert limiter.check_rate_limit(ip) is True
    assert limiter.check_rate_limit(ip) is True
    assert limiter.check_rate_limit(ip) is True
    # 4th request exceeds max_rpm
    assert limiter.check_rate_limit(ip) is False

    # Disabling rate limit with 0
    disabled_limiter = SecurityRateLimiter(max_rpm=0)
    for _ in range(50):
        assert disabled_limiter.check_rate_limit(ip) is True


def test_rate_limiter_brute_force_lockout():
    limiter = SecurityRateLimiter(max_failures=3, lockout_seconds=10)
    ip = "10.0.0.5"

    assert limiter.is_locked_out(ip)[0] is False

    # 1st failure
    assert limiter.record_auth_failure(ip) is False
    assert limiter.is_locked_out(ip)[0] is False

    # 2nd failure
    assert limiter.record_auth_failure(ip) is False
    assert limiter.is_locked_out(ip)[0] is False

    # 3rd failure -> triggers lockout!
    assert limiter.record_auth_failure(ip) is True
    locked, remaining = limiter.is_locked_out(ip)
    assert locked is True
    assert remaining > 0

    # Reset on successful login
    limiter.record_auth_success(ip)
    assert limiter.is_locked_out(ip)[0] is False


def test_get_client_ip():
    # Direct address
    assert get_client_ip({}, ("127.0.0.1", 5050)) == "127.0.0.1"

    # X-Forwarded-For (proxy / CDN)
    headers = {"X-Forwarded-For": "203.0.113.195, 70.41.3.18"}
    assert get_client_ip(headers, ("127.0.0.1", 5050)) == "203.0.113.195"

    # Cloudflare header
    headers_cf = {"CF-Connecting-IP": "198.51.100.42"}
    assert get_client_ip(headers_cf, ("127.0.0.1", 5050)) == "198.51.100.42"


def test_security_headers_production():
    headers_dict = dict(get_security_headers(is_ssl=False))
    assert headers_dict["X-Frame-Options"] == "DENY"
    assert headers_dict["X-Content-Type-Options"] == "nosniff"
    assert headers_dict["X-XSS-Protection"] == "1; mode=block"
    assert "Content-Security-Policy" in headers_dict
    assert "no-store" in headers_dict["Cache-Control"]
    assert "Strict-Transport-Security" not in headers_dict

    # With SSL active
    ssl_headers = dict(get_security_headers(is_ssl=True))
    assert "Strict-Transport-Security" in ssl_headers


def test_sanitize_symbol():
    assert sanitize_symbol("TATAMOTORS") == "TATAMOTORS"
    assert sanitize_symbol("tatamotors") == "TATAMOTORS"
    assert sanitize_symbol("<script>alert(1)</script>") == "SCRIPTALERT1SCRIPT"
    assert sanitize_symbol("ABC; DROP TABLE ipos;--") == "ABCDROPTABLEIPOS--"
    assert len(sanitize_symbol("VERYLONGSYMBOLNAMEEXCEEDINGTWENTYCHARS")) == 20


@pytest.fixture
def secure_server():
    orchestrator = IPOListingDayOrchestrator()
    orchestrator.prepare_session([])
    server = IPOMonitoringServer(
        orchestrator=orchestrator,
        host="127.0.0.1",
        port=0,
        auth_username="SecureUser",
        auth_password="SecurePassword999!",
        rate_limit_rpm=10,
    )
    server.start()
    base_url = f"http://127.0.0.1:{server.port}"
    try:
        yield server, base_url
    finally:
        server.stop()


def test_server_security_headers_and_auth_challenge(secure_server):
    _, base_url = secure_server

    # Unauthenticated request to /api/status should return 401 with WWW-Authenticate & security headers
    req = urllib.request.Request(f"{base_url}/api/status")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)

    err = exc_info.value
    assert err.code == 401
    assert "WWW-Authenticate" in err.headers
    assert 'Basic realm="IPO Trading Terminal"' in err.headers["WWW-Authenticate"]
    assert err.headers.get("X-Frame-Options") == "DENY"
    assert err.headers.get("X-Content-Type-Options") == "nosniff"


def test_server_payload_size_limit(secure_server):
    _, base_url = secure_server
    creds = base64.b64encode(b"SecureUser:SecurePassword999!").decode()

    # Create oversized payload (> 64KB)
    oversized = json.dumps({"symbol": "BIG", "junk": "X" * (MAX_PAYLOAD_BYTES + 500)}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/api/tick",
        data=oversized,
        headers={
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)

    assert exc_info.value.code == 413
