import html as html_lib
import json
from datetime import datetime, timezone

import requests


class InvestorGainGMPDataSource:
    """Collect IPO GMP history from InvestorGain."""

    GMP_URL_TEMPLATE = (
        "https://www.investorgain.com/"
        "gmp/{slug}/{ipo_id}/"
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
            "Referer": "https://www.investorgain.com/",
        })

    def fetch(
        self,
        slug: str,
        ipo_id: int,
    ) -> list[dict]:

        if not isinstance(slug, str):
            raise TypeError("slug must be a string.")

        if not slug.strip():
            raise ValueError("slug cannot be empty.")

        if not isinstance(ipo_id, int):
            raise TypeError("ipo_id must be an integer.")

        url = self.GMP_URL_TEMPLATE.format(
            slug=slug.strip(),
            ipo_id=ipo_id,
        )

        response = self.session.get(
            url,
            timeout=30,
        )

        response.raise_for_status()

        records = self.parse(
            response.text,
            response.url,
        )

        for record in records:
            record["ipo_id"] = ipo_id
            record["slug"] = slug.strip()

        return records

    def parse(
        self,
        html: str,
        source_url: str,
    ) -> list[dict]:

        data = self._extract_gmp_data(html)

        if data is None:
            raise ValueError(
                "InvestorGain gmpData not found."
            )

        if not isinstance(data, list):
            raise ValueError(
                "InvestorGain gmpData is not a list."
            )

        records = []

        for item in data:
            if not isinstance(item, dict):
                continue

            record = self._normalize_record(
                item,
                source_url,
            )

            if record is not None:
                records.append(record)

        return records

    @classmethod
    def _extract_gmp_data(
        cls,
        source_html: str,
    ) -> list | None:

        # InvestorGain can return serialized page data
        # with HTML escaping and/or backslash escaping.
        variants = [
            source_html,
            html_lib.unescape(source_html),
            html_lib.unescape(source_html).replace(
                '\\"',
                '"',
            ),
        ]

        for text in variants:

            result = cls._extract_from_text(
                text
            )

            if result is not None:
                return result

        return None

    @classmethod
    def _extract_from_text(
        cls,
        text: str,
    ) -> list | None:

        marker_positions = []

        # Normal:
        # "gmpData":[...]

        marker = '"gmpData"'

        position = text.find(marker)

        if position != -1:
            marker_positions.append(position)

        # Escaped:
        # \"gmpData\":[...]

        escaped_marker = '\\"gmpData\\"'

        position = text.find(
            escaped_marker
        )

        if position != -1:
            marker_positions.append(position)

        # Last fallback: plain gmpData
        position = text.lower().find(
            "gmpdata"
        )

        if position != -1:
            marker_positions.append(position)

        for position in marker_positions:

            array_start = text.find(
                "[",
                position,
            )

            if array_start == -1:
                continue

            json_text = (
                cls._extract_balanced_array(
                    text,
                    array_start,
                )
            )

            if not json_text:
                continue

            # Normal JSON
            try:
                value = json.loads(
                    json_text
                )

                if isinstance(value, list):
                    return value

            except json.JSONDecodeError:
                pass

            # Escaped JSON
            try:

                cleaned = (
                    json_text
                    .replace(
                        '\\"',
                        '"',
                    )
                    .replace(
                        "\\/",
                        "/",
                    )
                )

                value = json.loads(
                    cleaned
                )

                if isinstance(value, list):
                    return value

            except json.JSONDecodeError:
                pass

        return None

    @staticmethod
    def _extract_balanced_array(
        text: str,
        start: int,
    ) -> str | None:

        if (
            start < 0
            or start >= len(text)
            or text[start] != "["
        ):
            return None

        depth = 0
        in_string = False
        escaped = False

        for index in range(
            start,
            len(text),
        ):

            char = text[index]

            if in_string:

                if escaped:
                    escaped = False

                elif char == "\\":
                    escaped = True

                elif char == '"':
                    in_string = False

                continue

            if char == '"':
                in_string = True

            elif char == "[":
                depth += 1

            elif char == "]":

                depth -= 1

                if depth == 0:
                    return text[
                        start:index + 1
                    ]

        return None

    def _normalize_record(
        self,
        item: dict,
        source_url: str,
    ) -> dict | None:

        gmp_date = item.get(
            "gmp_date"
        )

        gmp = self._to_float(
            item.get("gmp")
        )

        gmp_percent = self._to_float(
            item.get("gmp_percent_calc")
        )

        max_ipo_price = self._to_float(
            item.get("max_ipo_price")
        )

        estimated_listing_price = (
            self._to_float(
                item.get(
                    "estimated_listing_price"
                )
            )
        )
       

        if (
            gmp_date is None
            and gmp is None
            and gmp_percent is None
        ):
            return None

        return {
            "gmp_date": self._parse_date(
                gmp_date
            ),
            "gmp": gmp,
            "gmp_percent": gmp_percent,
            "max_ipo_price": max_ipo_price,
            "estimated_listing_price": (
                estimated_listing_price
            ),
            "source": "InvestorGain",
            "source_url": source_url,
            "collected_at": datetime.now(
                            timezone.utc
                        ).isoformat(),
        }

    @staticmethod
    def _to_float(value) -> float | None:

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
            .strip()
        )

        try:
            return float(text)
        except ValueError:
            return None

    @staticmethod
    def _parse_date(value):

        if value is None:
            return None

        text = str(value).strip()

        formats = [
            "%d-%m-%Y",
            "%d-%b-%Y",
            "%d-%B-%Y",
            "%d %b %Y",
            "%d %B %Y",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(
                    text,
                    fmt,
                ).date()
            except ValueError:
                continue

        return None