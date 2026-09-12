from backend.collectors.ipo.chittorgarh_anchor_source import (
    ChittorgarhAnchorSource,
)
from backend.collectors.ipo.chittorgarh_financials_source import (
    ChittorgarhFinancialsSource,
)
from backend.collectors.ipo.chittorgarh_issue_details import (
    ChittorgarhIssueDetailsSource,
)
from backend.collectors.ipo.chittorgarh_subscription_source import (
    ChittorgarhSubscriptionDataSource,
)
from backend.collectors.ipo.nse_source import (
    NSEIPODataSource,
)
from backend.models.ipo_analysis import IPOAnalysis
from backend.storage.gmp_repository import GMPRepository


class IPOAnalysisBuilder:
    """
    Build a complete IPOAnalysis from collected IPO data.

    Internal IPO IDs and source-specific IPO IDs are kept
    separate.

    Sources:

    NSE:
        IPO type / market type

    GMP repository:
        GMP snapshots

    Chittorgarh:
        Subscription
        Issue details
        Anchor investors
        Financials
        Valuation
    """

    def __init__(self):
        self.gmp_repository = GMPRepository()

        self.nse_source = NSEIPODataSource()

        self.issue_details_source = (
            ChittorgarhIssueDetailsSource()
        )

        self.subscription_source = (
            ChittorgarhSubscriptionDataSource()
        )

        self.anchor_source = (
            ChittorgarhAnchorSource()
        )

        self.financials_source = (
            ChittorgarhFinancialsSource()
        )

    # =========================================================
    # COMPLETE BUILD
    # =========================================================

    def build(
        self,
        ipo_id: int,
        chittorgarh_url: str,
        chittorgarh_ipo_id: int | None = None,
        company_name: str | None = None,
        symbol: str | None = None,
        ipo_type: str | None = None,
    ) -> IPOAnalysis:
        """
        Build a complete IPOAnalysis.

        Parameters
        ----------
        ipo_id:
            Internal database IPO ID.

        chittorgarh_url:
            Chittorgarh IPO detail URL.

        chittorgarh_ipo_id:
            IPO ID used by Chittorgarh's subscription endpoint.

        company_name:
            Company name used for NSE matching.

        symbol:
            NSE symbol used for NSE matching.

        ipo_type:
            Known IPO market type supplied by the discovery/source
            layer.

            Expected values include:

                MAINBOARD
                SME

            If supplied, this value takes priority over NSE
            matching.

            If not supplied, NSE matching is attempted.
        """

        analysis = self.build_gmp_analysis(
            ipo_id=ipo_id,
        )

        # -----------------------------------------------------
        # IPO TYPE
        # -----------------------------------------------------

        if ipo_type is not None:
            analysis.ipo_type = (
                self._normalize_ipo_type(
                    ipo_type
                )
            )

        else:
            self.add_nse_details(
                analysis=analysis,
                company_name=company_name,
                symbol=symbol,
            )

        # -----------------------------------------------------
        # SUBSCRIPTION
        # -----------------------------------------------------

        self.add_subscription_details(
            analysis=analysis,
            chittorgarh_ipo_id=(
                chittorgarh_ipo_id
                if chittorgarh_ipo_id is not None
                else ipo_id
            ),
            chittorgarh_url=chittorgarh_url,
        )

        # -----------------------------------------------------
        # ISSUE DETAILS
        # -----------------------------------------------------

        self.add_issue_details(
            analysis=analysis,
            url=chittorgarh_url,
        )

        # -----------------------------------------------------
        # ANCHOR INVESTORS
        # -----------------------------------------------------

        self.add_anchor_details(
            analysis=analysis,
            url=chittorgarh_url,
        )

        # -----------------------------------------------------
        # FINANCIALS
        # -----------------------------------------------------

        self.add_financial_details(
            analysis=analysis,
            url=chittorgarh_url,
        )

        return analysis

    # =========================================================
    # GMP
    # =========================================================

    def build_gmp_analysis(
        self,
        ipo_id: int,
    ) -> IPOAnalysis:
        """
        Populate the latest two GMP percentages.
        """

        analysis = IPOAnalysis(
            ipo_id=ipo_id,
        )

        snapshots = (
            self.gmp_repository.get_latest_two(
                ipo_id,
            )
        )

        if len(snapshots) >= 1:
            analysis.gmp_day_1 = (
                snapshots[0].get(
                    "gmp_percent"
                )
            )

        if len(snapshots) >= 2:
            analysis.gmp_day_2 = (
                snapshots[1].get(
                    "gmp_percent"
                )
            )

        return analysis

    # =========================================================
    # NSE
    # =========================================================

    def add_nse_details(
        self,
        analysis: IPOAnalysis,
        company_name: str | None = None,
        symbol: str | None = None,
    ) -> IPOAnalysis:
        """
        Populate IPO type from NSE MARKETTYPE.

        Matching priority:

        1. Symbol
        2. Company name

        If no matching NSE record is found,
        ipo_type remains None.

        We deliberately do not assume MAINBOARD when no
        match is found.
        """

        if not company_name and not symbol:
            return analysis

        records = self.nse_source.fetch()

        matched_record = None

        normalized_symbol = (
            symbol.strip().upper()
            if symbol
            else None
        )

        normalized_company = (
            self._normalize_text(
                company_name
            )
            if company_name
            else None
        )

        # -----------------------------------------------------
        # Match by symbol
        # -----------------------------------------------------

        if normalized_symbol:

            for record in records:

                record_symbol = str(
                    record.get("SYMBOL") or ""
                ).strip().upper()

                if (
                    record_symbol
                    and record_symbol
                    == normalized_symbol
                ):
                    matched_record = record
                    break

        # -----------------------------------------------------
        # Match by company name
        # -----------------------------------------------------

        if (
            matched_record is None
            and normalized_company
        ):

            for record in records:

                record_company = (
                    self._normalize_text(
                        record.get(
                            "COMPANYNAME"
                        )
                    )
                )

                if not record_company:
                    continue

                if (
                    record_company
                    == normalized_company
                    or normalized_company
                    in record_company
                    or record_company
                    in normalized_company
                ):
                    matched_record = record
                    break

        # -----------------------------------------------------
        # Apply NSE market type
        # -----------------------------------------------------

        if matched_record is not None:

            market_type = (
                matched_record.get(
                    "MARKETTYPE"
                )
            )

            if market_type:

                analysis.ipo_type = (
                    self._normalize_ipo_type(
                        market_type
                    )
                )

                analysis.source = "NSE"
                analysis.source_url = (
                    self.nse_source.URL
                )

        return analysis

    # =========================================================
    # SUBSCRIPTION
    # =========================================================

    def add_subscription_details(
        self,
        analysis: IPOAnalysis,
        chittorgarh_ipo_id: int,
        chittorgarh_url: str,
    ) -> IPOAnalysis:
        """
        Populate:

        - QIB subscription
        - Overall subscription
        """

        details = (
            self.subscription_source.fetch(
                chittorgarh_ipo_id,
                detail_url=chittorgarh_url,
            )
        )

        analysis.qib_subscription = (
            details.get(
                "qib_subscription"
            )
        )

        analysis.overall_subscription = (
            details.get(
                "overall_subscription"
            )
        )

        return analysis

    # =========================================================
    # ISSUE DETAILS
    # =========================================================

    def add_issue_details(
        self,
        analysis: IPOAnalysis,
        url: str,
    ) -> IPOAnalysis:
        """
        Populate fresh issue and OFS percentages.
        """

        details = (
            self.issue_details_source.fetch(
                url,
            )
        )

        analysis.fresh_issue_percentage = (
            details.get(
                "fresh_issue_percentage"
            )
        )

        analysis.ofs_percentage = (
            details.get(
                "ofs_percentage"
            )
        )

        analysis.source = details.get(
            "source"
        )

        analysis.source_url = details.get(
            "source_url"
        )

        return analysis

    # =========================================================
    # ANCHOR INVESTORS
    # =========================================================

    def add_anchor_details(
        self,
        analysis: IPOAnalysis,
        url: str,
    ) -> IPOAnalysis:
        """
        Populate anchor investor count.
        """

        details = (
            self.anchor_source.fetch(
                url,
            )
        )

        analysis.anchor_investor_count = (
            details.get(
                "anchor_investor_count"
            )
        )

        analysis.source = details.get(
            "source"
        )

        analysis.source_url = details.get(
            "source_url"
        )

        return analysis

    # =========================================================
    # FINANCIALS
    # =========================================================

    def add_financial_details(
        self,
        analysis: IPOAnalysis,
        url: str,
    ) -> IPOAnalysis:
        """
        Populate:

        - Sales
        - Profit
        - Profit margin
        - Debt
        - ROE
        - ROCE
        - IPO P/E
        """

        details = (
            self.financials_source.fetch(
                url,
            )
        )

        # -----------------------------------------------------
        # Sales
        # -----------------------------------------------------

        analysis.sales_year_1 = (
            details.get(
                "sales_year_1"
            )
        )

        analysis.sales_year_2 = (
            details.get(
                "sales_year_2"
            )
        )

        analysis.sales_year_3 = (
            details.get(
                "sales_year_3"
            )
        )

        # -----------------------------------------------------
        # Profit
        # -----------------------------------------------------

        analysis.profit_year_1 = (
            details.get(
                "profit_year_1"
            )
        )

        analysis.profit_year_2 = (
            details.get(
                "profit_year_2"
            )
        )

        analysis.profit_year_3 = (
            details.get(
                "profit_year_3"
            )
        )

        # -----------------------------------------------------
        # Profit Margin
        # -----------------------------------------------------

        analysis.margin_year_1 = (
            details.get(
                "margin_year_1"
            )
        )

        analysis.margin_year_2 = (
            details.get(
                "margin_year_2"
            )
        )

        analysis.margin_year_3 = (
            details.get(
                "margin_year_3"
            )
        )

        # -----------------------------------------------------
        # Debt
        # -----------------------------------------------------

        analysis.debt_previous = (
            details.get(
                "debt_previous"
            )
        )

        analysis.debt_current = (
            details.get(
                "debt_current"
            )
        )

        # -----------------------------------------------------
        # ROE / ROCE
        # -----------------------------------------------------

        analysis.roe = details.get(
            "roe"
        )

        analysis.roce = details.get(
            "roce"
        )

        # -----------------------------------------------------
        # IPO P/E
        # -----------------------------------------------------

        analysis.ipo_pe = details.get(
            "ipo_pe"
        )

        # -----------------------------------------------------
        # Source
        # -----------------------------------------------------

        analysis.source = details.get(
            "source"
        )

        analysis.source_url = details.get(
            "source_url"
        )

        return analysis

    # =========================================================
    # HELPERS
    # =========================================================

    @staticmethod
    def _normalize_text(
        value,
    ) -> str:
        """
        Normalize text for company-name matching.
        """

        if value is None:
            return ""

        return (
            " ".join(
                str(value)
                .strip()
                .upper()
                .split()
            )
        )

    @staticmethod
    def _normalize_ipo_type(
        value,
    ) -> str | None:
        """
        Normalize IPO market type.

        Supported canonical values:

            MAINBOARD
            SME

        Unknown values are preserved in uppercase rather
        than being silently converted to MAINBOARD.
        """

        if value is None:
            return None

        normalized = (
            str(value)
            .strip()
            .upper()
        )

        if normalized in {
            "MAINBOARD",
            "MAIN BOARD",
            "MAIN-BOARD",
        }:
            return "MAINBOARD"

        if normalized in {
            "SME",
            "SME IPO",
        }:
            return "SME"

        return normalized