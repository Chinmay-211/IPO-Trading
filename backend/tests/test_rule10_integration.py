from backend.strategy.ipo_analysis_builder import (
    IPOAnalysisBuilder,
)
from backend.strategy.ipo_rule_evaluator import (
    IPORuleEvaluator,
)


def main():
    builder = IPOAnalysisBuilder()

    analysis = builder.build_gmp_analysis(2252)

    url = (
        "https://www.chittorgarh.com/ipo/"
        "tempsens-instruments-india-ipo/2668/"
    )

    analysis = builder.add_financial_details(
        analysis,
        url,
    )

    print("Debt data:")
    print(
        "Previous:",
        analysis.debt_previous,
    )
    print(
        "Current:",
        analysis.debt_current,
    )

    if (
        analysis.debt_previous is not None
        and analysis.debt_previous > 0
        and analysis.debt_current is not None
    ):
        increase = (
            (
                analysis.debt_current
                - analysis.debt_previous
            )
            / analysis.debt_previous
            * 100
        )

        print(
            "Debt increase:",
            round(increase, 2),
            "%",
        )

    evaluator = IPORuleEvaluator()

    results = evaluator.evaluate(analysis)

    rule_10 = next(
        result
        for result in results
        if result.rule_number == 10
    )

    print("Rule 10 result:")
    print(rule_10)


if __name__ == "__main__":
    main()