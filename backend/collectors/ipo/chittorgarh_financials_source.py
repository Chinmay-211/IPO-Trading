import requests
from bs4 import BeautifulSoup


class ChittorgarhFinancialsSource:
    """Collect IPO financial and valuation data from Chittorgarh."""

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
    def _number(value: str) -> float:
        value = (
            value.replace(",", "")
            .replace("₹", "")
            .replace("Γé╣", "")
            .replace("%", "")
            .strip()
        )

        return float(value)

    def parse(
        self,
        html: str,
        source_url: str,
    ) -> dict:

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        result = {
            "sales_year_1": None,
            "sales_year_2": None,
            "sales_year_3": None,

            "profit_year_1": None,
            "profit_year_2": None,
            "profit_year_3": None,

            "margin_year_1": None,
            "margin_year_2": None,
            "margin_year_3": None,

            "debt_previous": None,
            "debt_current": None,

            "roe": None,
            "roce": None,

            "ipo_pe": None,

            "financial_years": [],

            "source": "Chittorgarh",
            "source_url": source_url,
        }

        self._parse_financial_table(
            soup,
            result,
        )

        self._parse_kpi_table(
            soup,
            result,
        )

        self._parse_valuation_table(
            soup,
            result,
        )

        if (
            result["sales_year_1"] is None
            and result["profit_year_1"] is None
        ):
            raise ValueError(
                "Chittorgarh financial table not found."
            )

        return result

    # =========================================================
    # FINANCIAL TABLE
    # =========================================================

    def _parse_financial_table(
        self,
        soup,
        result: dict,
    ):

        for table in soup.find_all("table"):

            rows = table.find_all("tr")

            if not rows:
                continue

            table_text = table.get_text(
                " ",
                strip=True,
            )

            if (
                "Period Ended" not in table_text
                or "Total Income" not in table_text
                or "Profit After Tax" not in table_text
            ):
                continue

            years = []
            sales = []
            profits = []
            borrowings = []

            for row in rows:

                cells = [
                    cell.get_text(
                        " ",
                        strip=True,
                    )
                    for cell in row.find_all(
                        ["th", "td"]
                    )
                ]

                if not cells:
                    continue

                label = cells[0].strip().lower()

                if label == "period ended":

                    for value in cells[1:]:

                        if value.startswith("31 Mar"):
                            years.append(value)

                elif label == "total income":

                    for value in cells[1:]:

                        try:
                            sales.append(
                                self._number(value)
                            )
                        except ValueError:
                            continue

                elif label == "profit after tax":

                    for value in cells[1:]:

                        try:
                            profits.append(
                                self._number(value)
                            )
                        except ValueError:
                            continue

                elif label == "total borrowing":

                    for value in cells[1:]:

                        try:
                            borrowings.append(
                                self._number(value)
                            )
                        except ValueError:
                            continue

            # -------------------------------------------------
            # Need at least 2 years for the financial history.
            #
            # Some IPO pages provide 3 years.
            # Some provide only 2 years.
            #
            # Never invent a missing third year.
            # -------------------------------------------------

            usable_years = min(
                len(years),
                len(sales),
                len(profits),
            )

            if usable_years < 2:
                continue

            usable_years = min(
                usable_years,
                3,
            )

            financial_data = list(
                zip(
                    years[:usable_years],
                    sales[:usable_years],
                    profits[:usable_years],
                )
            )

            # Chittorgarh presents newest -> oldest.
            # Reverse to oldest -> newest.
            financial_data.reverse()

            result["financial_years"] = [
                item[0]
                for item in financial_data
            ]

            # -------------------------------------------------
            # Clear all financial fields first.
            # -------------------------------------------------

            result["sales_year_1"] = None
            result["sales_year_2"] = None
            result["sales_year_3"] = None

            result["profit_year_1"] = None
            result["profit_year_2"] = None
            result["profit_year_3"] = None

            result["margin_year_1"] = None
            result["margin_year_2"] = None
            result["margin_year_3"] = None

            # -------------------------------------------------
            # Populate available years.
            # -------------------------------------------------

            for index, item in enumerate(
                financial_data,
                start=1,
            ):

                year = item[0]
                sales_value = item[1]
                profit_value = item[2]

                result[
                    f"sales_year_{index}"
                ] = sales_value

                result[
                    f"profit_year_{index}"
                ] = profit_value

                if sales_value != 0:
                    result[
                        f"margin_year_{index}"
                    ] = (
                        profit_value
                        / sales_value
                        * 100
                    )

            # -------------------------------------------------
            # Debt
            #
            # Original Chittorgarh order:
            # newest -> oldest
            #
            # Therefore:
            # borrowings[0] = current/latest
            # borrowings[1] = previous
            # -------------------------------------------------

            if len(borrowings) >= 2:

                result["debt_previous"] = (
                    borrowings[1]
                )

                result["debt_current"] = (
                    borrowings[0]
                )

            return

    # =========================================================
    # KPI TABLE
    # =========================================================

    def _parse_kpi_table(
        self,
        soup,
        result: dict,
    ):

        for table in soup.find_all("table"):

            text = table.get_text(
                " ",
                strip=True,
            )

            if (
                "KPI" not in text
                or "ROE" not in text
                or "ROCE" not in text
            ):
                continue

            rows = table.find_all("tr")

            for row in rows:

                cells = [
                    cell.get_text(
                        " ",
                        strip=True,
                    )
                    for cell in row.find_all(
                        ["th", "td"]
                    )
                ]

                if len(cells) < 2:
                    continue

                label = cells[0].strip().lower()

                try:
                    value = self._number(
                        cells[1]
                    )
                except ValueError:
                    continue

                if label == "roe":
                    result["roe"] = value

                elif label == "roce":
                    result["roce"] = value

            return

    # =========================================================
    # VALUATION TABLE
    # =========================================================

    def _parse_valuation_table(
        self,
        soup,
        result: dict,
    ):

        for table in soup.find_all("table"):

            text = table.get_text(
                " ",
                strip=True,
            )

            if (
                "Valuation Metric" not in text
                or "P/E" not in text
            ):
                continue

            rows = table.find_all("tr")

            for row in rows:

                cells = [
                    cell.get_text(
                        " ",
                        strip=True,
                    )
                    for cell in row.find_all(
                        ["th", "td"]
                    )
                ]

                if len(cells) < 3:
                    continue

                label = cells[0].strip().upper()

                if label == "P/E (X)":

                    # Chittorgarh:
                    #
                    # P/E (x) | Pre IPO | Post IPO
                    #
                    # Rule 13 uses Post IPO P/E.

                    try:
                        result["ipo_pe"] = (
                            self._number(
                                cells[2]
                            )
                        )
                    except ValueError:
                        pass

                    return