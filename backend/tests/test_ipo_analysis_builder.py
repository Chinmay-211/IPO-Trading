from backend.strategy.ipo_analysis_builder import (
    IPOAnalysisBuilder,
)


INTERNAL_IPO_ID = 2252

CHITTORGARH_IPO_ID = 2668

CHITTORGARH_URL = (
    "https://www.chittorgarh.com/ipo/"
    "tempsens-instruments-india-ipo/2668/"
)

COMPANY_NAME = (
    "Tempsens Instruments India"
)


def main():
    builder = IPOAnalysisBuilder()

    analysis = builder.build(
    ipo_id=2252,
    chittorgarh_ipo_id=2668,
    chittorgarh_url=(
        "https://www.chittorgarh.com/ipo/"
        "tempsens-instruments-india-ipo/2668/"
    ),
    company_name="Tempsens Instruments India",
    ipo_type="MAINBOARD",
)

    print("Complete IPO Analysis:")
    print(analysis)

    print("\n" + "=" * 60)
    print("COLLECTED VALUES")
    print("=" * 60)

    print(
        "Internal IPO ID:",
        analysis.ipo_id,
    )

    print(
        "IPO Type:",
        analysis.ipo_type,
    )

    print(
        "QIB Subscription:",
        analysis.qib_subscription,
    )

    print(
        "Overall Subscription:",
        analysis.overall_subscription,
    )

    print(
        "GMP Day 1:",
        analysis.gmp_day_1,
    )

    print(
        "GMP Day 2:",
        analysis.gmp_day_2,
    )

    print(
        "Fresh Issue %:",
        analysis.fresh_issue_percentage,
    )

    print(
        "OFS %:",
        analysis.ofs_percentage,
    )

    print(
        "Anchor Investors:",
        analysis.anchor_investor_count,
    )

    print(
        "Sales:",
        analysis.sales_year_1,
        analysis.sales_year_2,
        analysis.sales_year_3,
    )

    print(
        "Profit:",
        analysis.profit_year_1,
        analysis.profit_year_2,
        analysis.profit_year_3,
    )

    print(
        "Margins:",
        analysis.margin_year_1,
        analysis.margin_year_2,
        analysis.margin_year_3,
    )

    print(
        "Debt Previous:",
        analysis.debt_previous,
    )

    print(
        "Debt Current:",
        analysis.debt_current,
    )

    print(
        "ROE:",
        analysis.roe,
    )

    print(
        "ROCE:",
        analysis.roce,
    )

    print(
        "IPO P/E:",
        analysis.ipo_pe,
    )

    print(
        "Peer P/E:",
        analysis.peer_pe,
    )

    print(
        "Source:",
        analysis.source,
    )

    print(
        "Source URL:",
        analysis.source_url,
    )

    print(
        "Collected At:",
        analysis.collected_at,
    )

    print("\n" + "=" * 60)
    print("BUILDER TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()