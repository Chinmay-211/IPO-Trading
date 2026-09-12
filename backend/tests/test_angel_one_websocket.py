import os
import time
import pytest

if os.getenv("RUN_LIVE_ANGEL_TESTS") != "1":
    pytest.skip(
        "Live Angel One tests require RUN_LIVE_ANGEL_TESTS=1.",
        allow_module_level=True,
    )

import pyotp

from dotenv import load_dotenv
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2


load_dotenv()


def main():
    api_key = os.getenv("ANGEL_API_KEY")
    client_id = os.getenv("ANGEL_CLIENT_ID")
    pin = os.getenv("ANGEL_PIN")
    totp_secret = os.getenv("ANGEL_TOTP_SECRET")

    # Authenticate
    totp = pyotp.TOTP(totp_secret).now()

    smart_api = SmartConnect(api_key=api_key)

    login_response = smart_api.generateSession(
        client_id,
        pin,
        totp
    )

    if not login_response.get("status"):
        raise RuntimeError(
            "Angel One login failed. Check provider status and "
            "account configuration."
        )

    auth_token = login_response["data"]["jwtToken"]
    feed_token = login_response["data"]["feedToken"]

    print("Angel One authentication: SUCCESS")
    print("Starting WebSocket...")

    correlation_id = "ipo_test"
    mode = 1  # LTP

    sws = SmartWebSocketV2(
        auth_token,
        api_key,
        client_id,
        feed_token
    )

    def on_data(wsapp, message):
        print("\nLIVE MARKET DATA:")
        print(message)

    def on_open(wsapp):
        print("WebSocket connected: SUCCESS")

        # NIFTY 50
        token_list = [
            {
                "exchangeType": 1,
                "tokens": ["99926000"]
            }
        ]

        sws.subscribe(
            correlation_id,
            mode,
            token_list
        )

        print("Subscribed to NIFTY 50")

    def on_error(wsapp, error):
        print("WebSocket error:", error)

    def on_close(wsapp):
        print("WebSocket closed")

    sws.on_data = on_data
    sws.on_open = on_open
    sws.on_error = on_error
    sws.on_close = on_close

    sws.connect()


if __name__ == "__main__":
    main()