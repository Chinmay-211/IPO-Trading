import os
import pytest

if os.getenv("RUN_LIVE_ANGEL_TESTS") != "1":
    pytest.skip(
        "Live Angel One tests require RUN_LIVE_ANGEL_TESTS=1.",
        allow_module_level=True,
    )

import pyotp
from dotenv import load_dotenv
from SmartApi import SmartConnect


load_dotenv()


def test_angel_one_connection():
    api_key = os.getenv("ANGEL_API_KEY")
    client_id = os.getenv("ANGEL_CLIENT_ID")
    pin = os.getenv("ANGEL_PIN")
    totp_secret = os.getenv("ANGEL_TOTP_SECRET")

    assert api_key, "ANGEL_API_KEY is missing"
    assert client_id, "ANGEL_CLIENT_ID is missing"
    assert pin, "ANGEL_PIN is missing"
    assert totp_secret, "ANGEL_TOTP_SECRET is missing"

    totp = pyotp.TOTP(totp_secret).now()

    smart_api = SmartConnect(api_key=api_key)

    response = smart_api.generateSession(
        client_id,
        pin,
        totp
    )

    assert response is not None
    assert response.get("status") is True, (
        "Angel One login failed. Check provider status and "
        "account configuration."
    )

    print("\nSUCCESS: Angel One authentication working.")


if __name__ == "__main__":
    test_angel_one_connection()