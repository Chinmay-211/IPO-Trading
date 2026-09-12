from backend.strategy.ipo_analysis_builder import (
    IPOAnalysisBuilder,
)
from backend.strategy.ipo_rule_evaluator import (
    IPORuleEvaluator,
)


def main():
    builder = IPOAnalysisBuilder()

    analysis = builder.build_gmp_analysis(2252)

    anchor_url = (
        "https://www.chittorgarh.com/"
        "ipo_subscription/"
        "tempsens-instruments-india-ipo/"
        "2668/"
    )

    analysis = builder.add_anchor_details(
        analysis,
        anchor_url,
    )

    evaluator = IPORuleEvaluator()

    results = evaluator.evaluate(analysis)

    rule_6 = next(
        result
        for result in results
        if result.rule_number == 6
    )

    print("Rule 6 result:")
    print(rule_6)


if __name__ == "__main__":
    main()