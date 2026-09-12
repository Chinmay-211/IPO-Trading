import re

import requests
from bs4 import BeautifulSoup


class ChittorgarhIssueDetailsSource:
    """Collect IPO issue structure from Chittorgarh."""

    BASE_URL = "https://www.chittorgarh.com"

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
        response = self.session.get(
            url,
            timeout=30,
        )

        response.raise_for_status()

        return self.parse(
            response.text,
            response.url,
        )

    @staticmethod
    def _parse_amount(text: str) -> float:
        return float(
            text.replace(",", "").strip()
        )

    def parse(
        self,
        html: str,
        source_url: str,
    ) -> dict:
        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        for table in soup.find_all("table"):

            text = table.get_text(
                " ",
                strip=True,
            )

            normalized_text = " ".join(
                text.split()
            )

            if "Total Issue Size" not in normalized_text:
                continue

            # -------------------------------------------------
            # Total Issue Size
            # -------------------------------------------------

            total_match = re.search(
                r"Total Issue Size\s+"
                r"[\d,]+\s+shares.*?"
                r"₹\s*([\d,.]+)\s*Cr",
                normalized_text,
                re.IGNORECASE,
            )

            if not total_match:
                continue

            total_issue = self._parse_amount(
                total_match.group(1)
            )

            # -------------------------------------------------
            # Fresh Issue
            # -------------------------------------------------

            fresh_match = re.search(
                r"Fresh Issue\s+"
                r"[\d,]+\s+shares.*?"
                r"₹\s*([\d,.]+)\s*Cr",
                normalized_text,
                re.IGNORECASE,
            )

            if fresh_match:
                fresh_issue = self._parse_amount(
                    fresh_match.group(1)
                )
            else:
                fresh_issue = 0.0

            # -------------------------------------------------
            # Offer for Sale
            # -------------------------------------------------

            ofs_match = re.search(
                r"Offer for Sale\s+"
                r"[\d,]+\s+shares.*?"
                r"₹\s*([\d,.]+)\s*Cr",
                normalized_text,
                re.IGNORECASE,
            )

            if ofs_match:
                ofs = self._parse_amount(
                    ofs_match.group(1)
                )
            else:
                ofs = 0.0

            # -------------------------------------------------
            # Percentages
            # -------------------------------------------------

            fresh_percentage = (
                fresh_issue / total_issue * 100
                if total_issue > 0
                else None
            )

            ofs_percentage = (
                ofs / total_issue * 100
                if total_issue > 0
                else None
            )

            return {
                "total_issue_amount": total_issue,
                "fresh_issue_amount": fresh_issue,
                "ofs_amount": ofs,
                "fresh_issue_percentage": fresh_percentage,
                "ofs_percentage": ofs_percentage,
                "source": "Chittorgarh",
                "source_url": source_url,
            }

        raise ValueError(
            "IPO issue details table not found."
        )