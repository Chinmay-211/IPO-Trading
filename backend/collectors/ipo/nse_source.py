from datetime import datetime

import requests

from backend.collectors.ipo.base import IPODataSource


class NSEIPODataSource(IPODataSource):
    """NSE IPO tracker API data source."""

    URL = (
        "https://www.nseindia.com/api/NextApi/apiClient"
        "?functionName=getIPOTrackerSummary"
    )

    def __init__(self):
        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/",
        })

    def fetch(self) -> list[dict]:
        response = self.session.get(
            self.URL,
            timeout=30,
        )

        response.raise_for_status()

        payload = response.json()

        records = payload.get("data", [])

        if not isinstance(records, list):
            raise ValueError(
                "Unexpected NSE IPO API response format."
            )

        return records

    def normalize(self, record: dict) -> dict:
        listing_date = datetime.strptime(
            record["LISTED_ON"],
            "%d-%m-%Y",
        ).date()

        issue_price = float(record["ISSUE_PRICE"])

        return {
            "company_name": record.get("COMPANYNAME"),
            "symbol": record.get("SYMBOL"),
            "listing_date": listing_date,
            "issue_price": issue_price,
            "issue_size": None,
            "sector": None,
            "source": "NSE",
            "source_url": self.URL,
        }