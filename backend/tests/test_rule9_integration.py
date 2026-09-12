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

    print("Margin data:")
    print(
        analysis.margin_year_1,
        analysis.margin_year_2,
        analysis.margin_year_3,
    )

    evaluator = IPORuleEvaluator()

    results = evaluator.evaluate(analysis)

    rule_9 = next(
        result
        for result in results
        if result.rule_number == 9
    )

    print("Rule 9 result:")
    print(rule_9)


if __name__ == "__main__":
    main()