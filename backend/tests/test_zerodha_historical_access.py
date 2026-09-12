import os

from dotenv import load_dotenv
from kiteconnect import KiteConnect


def main():
    load_dotenv()

    api_key = os.getenv("ZERODHA_API_KEY")
    access_token = os.getenv("ZERODHA_ACCESS_TOKEN")

    if not api_key:
        raise RuntimeError("ZERODHA_API_KEY is missing")

    if not access_token:
        raise RuntimeError("ZERODHA_ACCESS_TOKEN is missing")

    kite = KiteConnect(api_key=api_key)

    kite.set_access_token(access_token)

    print("=" * 60)
    print("ZERODHA HISTORICAL DATA CAPABILITY TEST")
    print("=" * 60)

    # ---------------------------------------------------------
    # 1. Authentication / profile
    # ---------------------------------------------------------

    profile = kite.profile()

    print("Authentication: PASS")
    print("User:", profile.get("user_name"))

    # ---------------------------------------------------------
    # 2. Download instrument list
    # ---------------------------------------------------------

    instruments = kite.instruments("NSE")

    print(
        "NSE instruments:",
        len(instruments),
    )

    assert len(instruments) > 0

    # ---------------------------------------------------------
    # 3. Find a known NSE equity
    # ---------------------------------------------------------

    matches = [
        instrument
        for instrument in instruments
        if instrument["tradingsymbol"] == "INFY"
        and instrument["exchange"] == "NSE"
    ]

    assert matches

    instrument = matches[0]

    instrument_token = instrument[
        "instrument_token"
    ]

    print(
        "INFY instrument token:",
        instrument_token,
    )

    # ---------------------------------------------------------
    # 4. Request historical 1-minute data
    #
    # Use a recent completed trading day.
    # ---------------------------------------------------------

    candles = kite.historical_data(
        instrument_token=instrument_token,
        from_date="2026-08-20 09:15:00",
        to_date="2026-08-20 15:30:00",
        interval="minute",
    )

    print(
        "Historical 1-minute candles:",
        len(candles),
    )

    if candles:
        print("First candle:")
        print(candles[0])

        print("Last candle:")
        print(candles[-1])

    # ---------------------------------------------------------
    # 5. Final capability result
    # ---------------------------------------------------------

    if candles:

        print()
        print(
            "HISTORICAL 1-MINUTE DATA: AVAILABLE"
        )

        print(
            "Your current Zerodha/Kite access "
            "can retrieve the data we need."
        )

    else:

        print()
        print(
            "HISTORICAL 1-MINUTE DATA: EMPTY"
        )

        print(
            "Authentication worked, but no candles "
            "were returned for the requested period."
        )


if __name__ == "__main__":
    main()