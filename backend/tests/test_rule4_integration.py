from backend.strategy.ipo_analysis_builder import IPOAnalysisBuilder
from backend.strategy.ipo_rule_evaluator import IPORuleEvaluator


def main():
    builder = IPOAnalysisBuilder()

    analysis = builder.build_gmp_analysis(2252)

    evaluator = IPORuleEvaluator()

    results = evaluator.evaluate(analysis)

    rule_4 = next(
        result
        for result in results
        if result.rule_number == 4
    )

    print("Rule 4 result:")
    print(rule_4)


if __name__ == "__main__":
    main()