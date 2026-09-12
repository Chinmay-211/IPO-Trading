import os
from datetime import datetime, timedelta

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


def test_angel_one_historical_data():
    api_key = os.getenv("ANGEL_API_KEY")
    client_id = os.getenv("ANGEL_CLIENT_ID")
    pin = os.getenv("ANGEL_PIN")
    totp_secret = os.getenv("ANGEL_TOTP_SECRET")

    assert api_key, "ANGEL_API_KEY is missing"
    assert client_id, "ANGEL_CLIENT_ID is missing"
    assert pin, "ANGEL_PIN is missing"
    assert totp_secret, "ANGEL_TOTP_SECRET is missing"

    # Generate current TOTP
    totp = pyotp.TOTP(totp_secret).now()

    # Login
    smart_api = SmartConnect(api_key=api_key)

    login_response = smart_api.generateSession(
        client_id,
        pin,
        totp
    )

    assert login_response.get("status") is True, (
        "Angel One login failed. Check provider status and "
        "account configuration."
    )

    print("\nAngel One authentication: SUCCESS")

    # Example: NIFTY 50 token
    # We'll later replace this with the actual IPO/security token.
    exchange = "NSE"
    symbol_token = "99926000"

    # Request the last 5 trading days
    to_date = datetime.now()
    from_date = to_date - timedelta(days=5)

    params = {
        "exchange": exchange,
        "symboltoken": symbol_token,
        "interval": "ONE_DAY",
        "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
        "todate": to_date.strftime("%Y-%m-%d %H:%M"),
    }

    print("Requesting historical data...")
    response = smart_api.getCandleData(params)

    assert response is not None
    assert response.get("status") is True, (
        "Historical data request failed at the provider."
    )

    data = response.get("data", [])

    print(f"\nCandles received: {len(data)}")

    assert len(data) > 0, "No historical candles returned"

    print("\nSUCCESS: Angel One historical data is working.")


if __name__ == "__main__":
    test_angel_one_historical_data()