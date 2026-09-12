from backend.strategy.ipo_analysis_builder import (
    IPOAnalysisBuilder,
)


def main():
    builder = IPOAnalysisBuilder()

    analysis = builder.build_gmp_analysis(2252)

    url = (
        "https://www.chittorgarh.com/ipo/"
        "tempsens-instruments-india-ipo/2668/"
    )

    analysis = builder.add_issue_details(
        analysis,
        url,
    )

    print("IPO Analysis:")
    print(analysis)


if __name__ == "__main__":
    main()