import re

import requests
from bs4 import BeautifulSoup


class ChittorgarhPeerValuationSource:
    """
    Collect directly comparable peer valuation data
    from a Chittorgarh IPO detail page.

    Only an explicitly identified peer/comparable-company
    section is accepted.

    Unrelated tables such as:
        - Recently Listed IPOs
        - Other IPOs
        - Similar IPOs

    are deliberately ignored.
    """

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

    def parse(
        self,
        html: str,
        source_url: str,
    ) -> dict:

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        peer_records = []

        # -----------------------------------------------------
        # Only inspect tables that belong to an explicitly
        # identified peer/comparable-company section.
        # -----------------------------------------------------

        for table in soup.find_all("table"):

            if not self._is_inside_peer_section(
                table
            ):
                continue

            headers = self._get_headers(
                table
            )

            if not headers:
                continue

            if not self._looks_like_peer_table(
                headers
            ):
                continue

            records = self._parse_peer_table(
                table,
                headers,
            )

            if records:
                peer_records.extend(
                    records
                )

        peer_pe = self._calculate_peer_pe(
            peer_records
        )

        return {
            "peer_pe": peer_pe,
            "peer_records": peer_records,
            "source": "Chittorgarh",
            "source_url": source_url,
        }

    # =========================================================
    # PEER SECTION DETECTION
    # =========================================================

    @staticmethod
    def _is_inside_peer_section(
        table,
    ) -> bool:
        """
        Determine whether a table belongs to an explicitly
        identified peer/comparable-company section.

        This intentionally rejects generic tables containing
        company names and P/E values.
        """

        # -----------------------------------------------------
        # Check ancestors first.
        # -----------------------------------------------------

        current = table.parent

        for _ in range(8):

            if current is None:
                break

            text = current.get_text(
                " ",
                strip=True,
            ).lower()

            if ChittorgarhPeerValuationSource._contains_peer_label(
                text
            ):
                return True

            current = current.parent

        # -----------------------------------------------------
        # Check preceding headings.
        # -----------------------------------------------------

        heading = table.find_previous(
            [
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
            ]
        )

        if heading is not None:

            heading_text = heading.get_text(
                " ",
                strip=True,
            ).lower()

            if (
                ChittorgarhPeerValuationSource
                ._contains_peer_label(
                    heading_text
                )
            ):
                return True

        return False

    @staticmethod
    def _contains_peer_label(
        text: str,
    ) -> bool:

        if not text:
            return False

        peer_terms = [
            "peer comparison",
            "peer comparison table",
            "peer companies",
            "peer company",
            "comparable companies",
            "comparable company",
            "listed peers",
            "industry peers",
            "peer valuation",
            "peer valuation table",
        ]

        return any(
            term in text
            for term in peer_terms
        )

    # =========================================================
    # TABLE DETECTION
    # =========================================================

    @staticmethod
    def _get_headers(table) -> list[str]:

        header_row = table.find("tr")

        if header_row is None:
            return []

        cells = header_row.find_all(
            ["th", "td"]
        )

        return [
            cell.get_text(
                " ",
                strip=True,
            )
            for cell in cells
        ]

    @staticmethod
    def _looks_like_peer_table(
        headers: list[str],
    ) -> bool:

        normalized = [
            h.lower().strip()
            for h in headers
        ]

        has_company = any(
            (
                "company" in h
                or "name" in h
                or "peer" in h
            )
            for h in normalized
        )

        has_pe = any(
            (
                "p/e" in h
                or "pe ratio" in h
                or h == "pe"
                or "p/e ratio" in h
            )
            for h in normalized
        )

        return (
            has_company
            and has_pe
        )

    # =========================================================
    # PARSING
    # =========================================================

    def _parse_peer_table(
        self,
        table,
        headers: list[str],
    ) -> list[dict]:

        normalized_headers = [
            h.lower().strip()
            for h in headers
        ]

        company_index = self._find_column(
            normalized_headers,
            [
                "peer",
                "company",
                "company name",
                "name",
            ],
        )

        pe_index = self._find_column(
            normalized_headers,
            [
                "p/e",
                "p/e ratio",
                "pe ratio",
                "pe",
            ],
        )

        if (
            company_index is None
            or pe_index is None
        ):
            return []

        records = []

        rows = table.find_all("tr")

        for row in rows[1:]:

            cells = row.find_all(
                ["td", "th"]
            )

            if not cells:
                continue

            if (
                company_index >= len(cells)
                or pe_index >= len(cells)
            ):
                continue

            company_name = cells[
                company_index
            ].get_text(
                " ",
                strip=True,
            )

            pe_text = cells[
                pe_index
            ].get_text(
                " ",
                strip=True,
            )

            pe = self._parse_float(
                pe_text
            )

            if not company_name:
                continue

            if pe is None or pe <= 0:
                continue

            records.append({
                "company_name": company_name,
                "pe": pe,
            })

        return records

    # =========================================================
    # PE CALCULATION
    # =========================================================

    @staticmethod
    def _calculate_peer_pe(
        peer_records: list[dict],
    ) -> float | None:

        values = [
            record["pe"]
            for record in peer_records
            if record.get("pe") is not None
        ]

        if not values:
            return None

        return sum(values) / len(values)

    # =========================================================
    # HELPERS
    # =========================================================

    @staticmethod
    def _find_column(
        headers: list[str],
        candidates: list[str],
    ) -> int | None:

        for candidate in candidates:

            candidate = (
                candidate
                .lower()
                .strip()
            )

            for index, header in enumerate(
                headers
            ):

                if header == candidate:
                    return index

        return None

    @staticmethod
    def _parse_float(
        value: str,
    ) -> float | None:

        if value is None:
            return None

        text = str(value).strip()

        if not text:
            return None

        text = (
            text
            .replace(",", "")
            .replace("₹", "")
            .replace("%", "")
            .strip()
        )

        match = re.search(
            r"-?\d+(?:\.\d+)?",
            text,
        )

        if not match:
            return None

        try:
            return float(
                match.group(0)
            )
        except ValueError:
            return None