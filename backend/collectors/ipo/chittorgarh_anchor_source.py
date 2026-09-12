import re

import requests
from bs4 import BeautifulSoup


class ChittorgarhAnchorSource:
    """Collect anchor investor count from Chittorgarh."""

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

    def fetch(self, url: str) -> dict:
        """
        Fetch anchor investor data.

        Accepts either:

        /ipo/<slug>/<id>/

        or:

        /ipo_subscription/<slug>/<id>/
        """

        subscription_url = (
            self._build_subscription_url(url)
        )

        response = self.session.get(
            subscription_url,
            timeout=30,
        )

        response.raise_for_status()

        return self.parse(
            response.text,
            response.url,
        )

    @staticmethod
    def _build_subscription_url(url: str) -> str:
        """Normalize a Chittorgarh URL to subscription page."""

        subscription_match = re.search(
            r"https?://www\.chittorgarh\.com/"
            r"ipo_subscription/([^/]+)/(\d+)/?",
            url,
            re.IGNORECASE,
        )

        if subscription_match:
            slug = subscription_match.group(1)
            ipo_id = subscription_match.group(2)

            return (
                "https://www.chittorgarh.com/"
                f"ipo_subscription/{slug}/{ipo_id}/"
            )

        ipo_match = re.search(
            r"https?://www\.chittorgarh\.com/"
            r"ipo/([^/]+)/(\d+)/?",
            url,
            re.IGNORECASE,
        )

        if ipo_match:
            slug = ipo_match.group(1)
            ipo_id = ipo_match.group(2)

            return (
                "https://www.chittorgarh.com/"
                f"ipo_subscription/{slug}/{ipo_id}/"
            )

        raise ValueError(
            "Unable to derive Chittorgarh subscription URL "
            f"from: {url}"
        )

    def parse(
        self,
        html: str,
        source_url: str,
    ) -> dict:
        """
        Parse anchor investor allocation data.

        Anchor data is optional. If Chittorgarh does not
        provide an anchor investor table, return None rather
        than failing the entire IPO analysis.
        """

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        for table in soup.find_all("table"):

            rows = table.find_all("tr")

            if not rows:
                continue

            table_text = table.get_text(
                " ",
                strip=True,
            )

            normalized_table_text = (
                " ".join(
                    table_text
                    .lower()
                    .split()
                )
            )

            # -------------------------------------------------
            # Identify anchor investor table.
            # -------------------------------------------------

            has_anchor = (
                "anchor" in normalized_table_text
            )

            has_shares = (
                "shares allotted"
                in normalized_table_text
                or "shares allocated"
                in normalized_table_text
            )

            if not (
                has_anchor
                and has_shares
            ):
                continue

            investor_count = 0

            # -------------------------------------------------
            # Count actual investor rows.
            # -------------------------------------------------

            for row in rows:

                cells = row.find_all(
                    ["td", "th"]
                )

                if len(cells) < 2:
                    continue

                row_values = [
                    cell.get_text(
                        " ",
                        strip=True,
                    )
                    for cell in cells
                ]

                row_text = " ".join(
                    row_values
                ).strip()

                if not row_text:
                    continue

                normalized_row = (
                    " ".join(
                        row_text
                        .lower()
                        .split()
                    )
                )

                # Skip header rows.
                if (
                    "investor" in normalized_row
                    and (
                        "shares allotted"
                        in normalized_row
                        or "shares allocated"
                        in normalized_row
                    )
                ):
                    continue

                # Skip summary rows.
                if any(
                    keyword in normalized_row
                    for keyword in (
                        "grand total",
                        "sub total",
                    )
                ):
                    continue

                # Investor rows should contain a share
                # quantity somewhere in the row.
                has_share_number = any(
                    re.search(
                        r"\b\d[\d,]*(?:\.\d+)?\b",
                        value,
                    )
                    for value in row_values
                )

                if not has_share_number:
                    continue

                investor_count += 1

            if investor_count > 0:
                return {
                    "anchor_investor_count": (
                        investor_count
                    ),
                    "source": "Chittorgarh",
                    "source_url": source_url,
                }

        # -----------------------------------------------------
        # Anchor information is optional.
        #
        # Do NOT fail the entire IPO when it is unavailable.
        # -----------------------------------------------------

        return {
            "anchor_investor_count": None,
            "source": "Chittorgarh",
            "source_url": source_url,
        }