import json
import re
from datetime import date, datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from backend.collectors.ipo.base import IPODataSource


class ChittorgarhIPODataSource(IPODataSource):
    """Discover Mainboard IPOs from Chittorgarh."""

    BASE_URL = "https://www.chittorgarh.com"
    API_BASE_URL = "https://webnodejs.chittorgarh.com"

    MAINBOARD_LIST_URL = (
        "https://www.chittorgarh.com/"
        "report/ipo-list-by-time-table-and-lot-size/"
        "118/mainboard/"
    )

    IPO_URL_PATTERN = re.compile(
        r"/ipo/[^/?#]+/\d+/?",
        re.IGNORECASE,
    )

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
            "Referer": "https://www.chittorgarh.com/",
        })
    def fetch_listing_info(self, url: str) -> dict:
        """Fetch NSE symbol and listing date from an IPO detail page."""

        response = self.session.get(
            url,
            timeout=30,
        )

        response.raise_for_status()

        return self.parse_listing_info(
            response.text,
            response.url,
        )

    def parse_listing_info(
        self,
        html: str,
        source_url: str,
    ) -> dict:
        """Extract NSE symbol and listing date from Chittorgarh."""

        # Chittorgarh embeds IPO detail data inside serialized
        # Next.js JSON. Extract the exact fields from that data.
        symbol_match = re.search(
            r'"nse_symbol"\s*:\s*"([^"]*)"',
            html,
            re.IGNORECASE,
        )

        listing_match = re.search(
            r'"timetable_listing_dt"\s*:\s*"([^"]*)"',
            html,
            re.IGNORECASE,
        )

        symbol = (
            symbol_match.group(1).strip()
            if symbol_match and symbol_match.group(1).strip()
            else None
        )

        listing_date = None

        if listing_match:
            listing_date = ChittorgarhIPODataSource._parse_date(
                listing_match.group(1)
            )

        ipo_id = self._extract_ipo_id(source_url)

        return {
            "ipo_id": ipo_id,
            "symbol": symbol,
            "listing_date": listing_date,
            "source": "Chittorgarh",
            "source_url": source_url,
        }

    def fetch(
        self,
        url: str | None = None,
    ) -> list[dict]:
        target_url = (
            url
            or self.MAINBOARD_LIST_URL
        )

        response = self.session.get(
            self._build_api_url(),
            timeout=30,
        )

        response.raise_for_status()

        records = []
        page = 1
        total_pages = 1

        while page <= total_pages:
            if page > 1:
                response = self.session.get(
                    self._build_api_url(page=page),
                    timeout=30,
                )
                response.raise_for_status()

            payload = response.json()
            records.extend(
                self.parse(
                    json.dumps(payload),
                    target_url,
                )
            )
            total_pages = int(payload.get("totalPages", page))
            page += 1

        return self._deduplicate(records)

    @classmethod
    def _build_api_url(
        cls,
        page: int = 1,
    ) -> str:
        today = date.today()
        financial_year = (
            f"{today.year}-{str(today.year + 1)[-2:]}"
            if today.month >= 4
            else f"{today.year - 1}-{str(today.year)[-2:]}"
        )

        return (
            f"{cls.API_BASE_URL}/cloud/report/data-read/118/{page}/"
            f"{today.month}/{today.year}/{financial_year}/0/mainboard/0/"
            "?search="
        )

    def parse(
        self,
        html: str,
        source_url: str,
    ) -> list[dict]:
        """
        Parse report API rows or legacy HTML detail links.

        Chittorgarh renders the report shell through Next.js and
        loads its rows from the report API. The HTML fallback keeps
        parsing compatible with older saved responses.
        """

        try:
            payload = json.loads(html)
        except (TypeError, json.JSONDecodeError):
            payload = None

        if isinstance(payload, dict) and "reportTableData" in payload:
            return self._parse_report_rows(
                payload.get("reportTableData", []),
                source_url,
            )

        soup = BeautifulSoup(html, "html.parser")

        discovered = {}

        # -----------------------------------------------------
        # Method 1: normal HTML anchors
        # -----------------------------------------------------

        for anchor in soup.find_all(
            "a",
            href=True,
        ):
            href = anchor.get("href")

            if not href:
                continue

            match = self.IPO_URL_PATTERN.search(
                href
            )

            if not match:
                continue

            detail_url = urljoin(
                self.BASE_URL,
                match.group(0),
            )

            ipo_id = self._extract_ipo_id(
                detail_url
            )

            if ipo_id is None:
                continue

            company_name = anchor.get_text(
                " ",
                strip=True,
            )

            if not company_name:
                company_name = (
                    self._name_from_url(
                        detail_url
                    )
                )

            discovered[ipo_id] = {
                "company_name": company_name,
                "ipo_id": ipo_id,
                "ipo_type": "MAINBOARD",
                "detail_url": detail_url,
                "source": "Chittorgarh",
                "source_url": source_url,
            }

        # -----------------------------------------------------
        # Method 2: raw HTML / Next.js JSON
        #
        # Some links can exist inside serialized page data
        # rather than ordinary anchor elements.
        # -----------------------------------------------------

        for match in self.IPO_URL_PATTERN.finditer(
            html
        ):
            detail_url = urljoin(
                self.BASE_URL,
                match.group(0),
            )

            ipo_id = self._extract_ipo_id(
                detail_url
            )

            if ipo_id is None:
                continue

            if ipo_id in discovered:
                continue

            company_name = self._name_from_url(
                detail_url
            )

            discovered[ipo_id] = {
                "company_name": company_name,
                "ipo_id": ipo_id,
                "ipo_type": "MAINBOARD",
                "detail_url": detail_url,
                "source": "Chittorgarh",
                "source_url": source_url,
            }

        return list(
            discovered.values()
        )

    @classmethod
    def _parse_report_rows(
        cls,
        rows: list[dict],
        source_url: str,
    ) -> list[dict]:
        discovered = {}

        for row in rows:
            ipo_id = cls._coerce_ipo_id(row.get("~id"))
            slug = str(row.get("~urlrewrite_folder_name") or "").strip()

            if ipo_id is None or not slug:
                continue

            ipo_type = cls._normalize_ipo_type(
                row.get("Issue Type")
            )
            if ipo_type != "MAINBOARD":
                continue

            detail_url = urljoin(
                cls.BASE_URL,
                f"/ipo/{slug}/{ipo_id}/",
            )
            if ipo_id in discovered:
                continue

            discovered[ipo_id] = {
                "company_name": str(
                    row.get("Company") or cls._name_from_url(detail_url)
                ).strip(),
                "ipo_id": ipo_id,
                "ipo_type": ipo_type,
                "ipo_open_date": row.get("Opening Date"),
                "ipo_close_date": row.get("Closing Date"),
                "listing_date": row.get("Listing Date"),
                "detail_url": detail_url,
                "source": "Chittorgarh",
                "source_url": source_url,
            }

        return list(discovered.values())

    @staticmethod
    def _coerce_ipo_id(value) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _deduplicate(records: list[dict]) -> list[dict]:
        unique = {}
        for record in records:
            ipo_id = record.get("ipo_id")
            if ipo_id is not None and ipo_id not in unique:
                unique[ipo_id] = record
        return list(unique.values())

    def normalize(
        self,
        record: dict,
    ) -> dict:
        """Normalize a discovered IPO."""

        ipo_type = self._normalize_ipo_type(
            record.get("ipo_type")
        )

        return {
            "company_name": record.get(
                "company_name"
            ),
            "symbol": record.get(
                "symbol"
            ),
            "listing_date": self._parse_date(
                record.get(
                    "listing_date"
                )
            ),
            "issue_price": self._parse_float(
                record.get(
                    "issue_price"
                )
            ),
            "issue_size": self._parse_float(
                record.get(
                    "issue_size"
                )
            ),
            "sector": record.get(
                "sector"
            ),
            "ipo_type": ipo_type,
            "chittorgarh_ipo_id": record.get(
                "ipo_id"
            ),
            "detail_url": record.get(
                "detail_url"
            ),
            "source": "Chittorgarh",
            "source_url": record.get(
                "detail_url"
            ) or self.BASE_URL,
        }

    @staticmethod
    def _extract_ipo_id(
        url: str,
    ) -> int | None:
        match = re.search(
            r"/ipo/[^/]+/(\d+)/?$",
            url,
            re.IGNORECASE,
        )

        if not match:
            return None

        return int(
            match.group(1)
        )

    @staticmethod
    def _name_from_url(
        url: str,
    ) -> str:
        match = re.search(
            r"/ipo/([^/]+)/\d+/?$",
            url,
            re.IGNORECASE,
        )

        if not match:
            return "Unknown IPO"

        slug = match.group(1)

        return (
            slug.replace(
                "-",
                " ",
            )
            .strip()
            .title()
        )

    @staticmethod
    def _normalize_ipo_type(
        value,
    ) -> str | None:
        if value is None:
            return None

        value = (
            str(value)
            .strip()
            .upper()
        )

        if value in {
            "MAINBOARD",
            "MAIN BOARD",
            "MAIN-BOARD",
        }:
            return "MAINBOARD"

        if value in {
            "SME",
            "SME IPO",
        }:
            return "SME"

        return value

    @staticmethod
    def _parse_float(
        value,
    ) -> float | None:
        if value is None:
            return None

        if isinstance(
            value,
            (int, float),
        ):
            return float(value)

        text = str(value).strip()

        if not text:
            return None

        text = (
            text
            .replace(",", "")
            .replace("₹", "")
            .replace("%", "")
            .replace("Cr.", "")
            .replace("Cr", "")
            .strip()
        )

        try:
            return float(text)
        except ValueError:
            return None

    @staticmethod
    def _parse_date(
        value,
    ):
        if value is None:
            return None

        if hasattr(
            value,
            "year",
        ):
            return value

        text = str(value).strip()

        formats = [
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%d %b %Y",
            "%d %B %Y",
            "%a, %b %d, %Y",
            "%A, %b %d, %Y",
            "%a, %B %d, %Y",
            "%A, %B %d, %Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(
                    text,
                    fmt,
                ).date()
            except ValueError:
                pass

        return None