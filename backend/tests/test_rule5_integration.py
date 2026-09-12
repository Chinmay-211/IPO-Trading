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

    analysis = builder.add_issue_details(
        analysis,
        url,
    )

    evaluator = IPORuleEvaluator()

    results = evaluator.evaluate(analysis)

    rule_5 = next(
        result
        for result in results
        if result.rule_number == 5
    )

    print("Rule 5 result:")
    print(rule_5)


if __name__ == "__main__":
    main()