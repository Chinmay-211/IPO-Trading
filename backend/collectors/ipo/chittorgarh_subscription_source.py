import re

import requests
from bs4 import BeautifulSoup


class ChittorgarhSubscriptionDataSource:
    """Collect IPO subscription data from Chittorgarh."""

    def __init__(self):
        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        })

    def fetch(
        self,
        ipo_id: int,
        detail_url: str | None = None,
    ) -> dict:
        """
        Fetch subscription data.

        The actual Chittorgarh IPO detail URL should be
        supplied by the discovery layer.
        """

        if not detail_url:
            raise ValueError(
                "detail_url is required for "
                "Chittorgarh subscription data."
            )

        response = self.session.get(
            detail_url,
            timeout=30,
        )

        response.raise_for_status()

        return self.parse(response.text)

    @staticmethod
    def _parse_number(value: str) -> float:
        value = value.replace(",", "").strip()
        return float(value)

    def parse(self, html: str) -> dict:
        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        result = {
            "qib_subscription": None,
            "nii_subscription": None,
            "retail_subscription": None,
            "overall_subscription": None,
            "total_applications": None,
            "source": "Chittorgarh",
        }

        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")

            for row in rows:
                cells = row.find_all(
                    ["td", "th"]
                )

                if len(cells) < 2:
                    continue

                category = cells[0].get_text(
                    " ",
                    strip=True,
                ).lower()

                subscription_text = cells[1].get_text(
                    " ",
                    strip=True,
                )

                try:
                    subscription = (
                        self._parse_number(
                            subscription_text
                        )
                    )
                except ValueError:
                    continue

                if "qib" in category:
                    result[
                        "qib_subscription"
                    ] = subscription

                elif category.strip() == "nii":
                    result[
                        "nii_subscription"
                    ] = subscription

                elif "retail" in category:
                    result[
                        "retail_subscription"
                    ] = subscription

                elif category.strip() == "total":
                    result[
                        "overall_subscription"
                    ] = subscription

        page_text = soup.get_text(
            " ",
            strip=True,
        )

        applications_match = re.search(
            r"Total Applications:\s*([\d,]+)",
            page_text,
            re.IGNORECASE,
        )

        if applications_match:
            result[
                "total_applications"
            ] = int(
                applications_match.group(1)
                .replace(",", "")
            )

        return result