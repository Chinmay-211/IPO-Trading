from backend.strategy.ipo_analysis_builder import (
    IPOAnalysisBuilder,
)
from backend.strategy.ipo_rule_evaluator import (
    IPORuleEvaluator,
)


INTERNAL_IPO_ID = 2252

CHITTORGARH_IPO_ID = 2668

CHITTORGARH_URL = (
    "https://www.chittorgarh.com/ipo/"
    "tempsens-instruments-india-ipo/2668/"
)

COMPANY_NAME = "Tempsens Instruments India"


def main():
    # ---------------------------------------------------------
    # STEP 1: Build complete IPO analysis
    # ---------------------------------------------------------

    builder = IPOAnalysisBuilder()

    analysis = builder.build(
        ipo_id=INTERNAL_IPO_ID,
        chittorgarh_ipo_id=CHITTORGARH_IPO_ID,
        chittorgarh_url=CHITTORGARH_URL,
        company_name=COMPANY_NAME,
        ipo_type="MAINBOARD",
    )

    # ---------------------------------------------------------
    # STEP 2: Evaluate all 13 rules
    # ---------------------------------------------------------

    evaluator = IPORuleEvaluator()

    results = evaluator.evaluate(
        analysis
    )

    # ---------------------------------------------------------
    # STEP 3: Print analysis
    # ---------------------------------------------------------

    print("=" * 70)
    print("COMPLETE IPO ANALYSIS")
    print("=" * 70)

    print(analysis)

    # ---------------------------------------------------------
    # STEP 4: Print all rules
    # ---------------------------------------------------------

    print("\n" + "=" * 70)
    print("13-RULE EVALUATION")
    print("=" * 70)

    for result in results:

        print(
            f"\nRule {result.rule_number}: "
            f"{result.rule_name}"
        )

        print(
            f"  Actual:    {result.actual_value}"
        )

        print(
            f"  Threshold: {result.threshold}"
        )

        print(
            f"  Status:    {result.status}"
        )

        print(
            f"  Passed:    {result.passed}"
        )

        print(
            f"  Reason:    {result.reason}"
        )

    # ---------------------------------------------------------
    # STEP 5: Summary
    # ---------------------------------------------------------

    passed = [
        result
        for result in results
        if result.status == "PASS"
    ]

    failed = [
        result
        for result in results
        if result.status == "FAIL"
    ]

    not_evaluable = [
        result
        for result in results
        if result.status == "NOT_EVALUABLE"
    ]

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(
        "Total rules:",
        len(results),
    )

    print(
        "Passed:",
        len(passed),
    )

    print(
        "Failed:",
        len(failed),
    )

    print(
        "Not evaluable:",
        len(not_evaluable),
    )

    # ---------------------------------------------------------
    # Final strategy decision
    #
    # NOT_EVALUABLE is not considered a pass.
    # Therefore the IPO is eligible only if every rule passes.
    # ---------------------------------------------------------

    strategy_pass = (
        len(results) == 13
        and len(passed) == 13
    )

    print(
        "Strategy Result:",
        "PASS" if strategy_pass else "FAIL",
    )


if __name__ == "__main__":
    main()