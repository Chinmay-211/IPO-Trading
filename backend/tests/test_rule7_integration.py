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

    evaluator = IPORuleEvaluator()

    results = evaluator.evaluate(analysis)

    rule_7 = next(
        result
        for result in results
        if result.rule_number == 7
    )

    print("Rule 7 result:")
    print(rule_7)


if __name__ == "__main__":
    main()