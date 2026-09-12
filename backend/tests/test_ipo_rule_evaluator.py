from backend.models.ipo_analysis import IPOAnalysis
from backend.strategy.ipo_rule_evaluator import IPORuleEvaluator


def make_complete_analysis():
    return IPOAnalysis(
        ipo_id=1,
        ipo_type="MAINBOARD",
        qib_subscription=25.0,
        overall_subscription=20.0,
        gmp_day_1=12.0,
        gmp_day_2=11.0,
        fresh_issue_percentage=75.0,
        ofs_percentage=25.0,
        anchor_investor_count=8,
        sales_year_1=100.0,
        sales_year_2=120.0,
        sales_year_3=150.0,
        profit_year_1=10.0,
        profit_year_2=12.0,
        profit_year_3=15.0,
        margin_year_1=10.0,
        margin_year_2=11.0,
        margin_year_3=12.0,
        debt_previous=100.0,
        debt_current=95.0,
        roe=15.0,
        roce=16.0,
        ipo_pe=25.0,
        peer_pe=None,
    )


def get_rule(results, rule_number):
    return next(
        result
        for result in results
        if result.rule_number == rule_number
    )


def test_all_rules_with_valid_data():
    analysis = make_complete_analysis()

    results = IPORuleEvaluator().evaluate(analysis)

    assert len(results) == 13

    expected_pass_rules = {
        1, 2, 3, 4, 5, 6,
        7, 8, 9, 10, 11, 13,
    }

    for rule_number in expected_pass_rules:
        result = get_rule(results, rule_number)
        assert result.status == "PASS", (
            f"Rule {rule_number} should PASS"
        )

    # Rule 12 is intentionally NOT_EVALUABLE
    # because no peer valuation is supplied.
    rule_12 = get_rule(results, 12)

    assert rule_12.status == "NOT_EVALUABLE"


def test_missing_qib_is_not_evaluable():
    analysis = make_complete_analysis()
    analysis.qib_subscription = None

    result = get_rule(
        IPORuleEvaluator().evaluate(analysis),
        2,
    )

    assert result.status == "NOT_EVALUABLE"


def test_low_qib_fails():
    analysis = make_complete_analysis()
    analysis.qib_subscription = 19.99

    result = get_rule(
        IPORuleEvaluator().evaluate(analysis),
        2,
    )

    assert result.status == "FAIL"


def test_missing_gmp_is_not_evaluable():
    analysis = make_complete_analysis()
    analysis.gmp_day_1 = None

    result = get_rule(
        IPORuleEvaluator().evaluate(analysis),
        4,
    )

    assert result.status == "NOT_EVALUABLE"


def test_one_low_gmp_fails():
    analysis = make_complete_analysis()
    analysis.gmp_day_2 = 9.99

    result = get_rule(
        IPORuleEvaluator().evaluate(analysis),
        4,
    )

    assert result.status == "FAIL"


def test_missing_third_year_makes_rules_7_to_9_not_evaluable():
    analysis = make_complete_analysis()

    analysis.sales_year_3 = None
    analysis.profit_year_3 = None
    analysis.margin_year_3 = None

    results = IPORuleEvaluator().evaluate(analysis)

    for rule_number in (7, 8, 9):
        result = get_rule(results, rule_number)

        assert result.status == "NOT_EVALUABLE", (
            f"Rule {rule_number} should be NOT_EVALUABLE"
        )


def test_sales_decrease_fails():
    analysis = make_complete_analysis()

    analysis.sales_year_3 = 110.0

    result = get_rule(
        IPORuleEvaluator().evaluate(analysis),
        7,
    )

    assert result.status == "FAIL"


def test_profit_decrease_fails():
    analysis = make_complete_analysis()

    analysis.profit_year_3 = 11.0

    result = get_rule(
        IPORuleEvaluator().evaluate(analysis),
        8,
    )

    assert result.status == "FAIL"


def test_profit_margin_decrease_fails():
    analysis = make_complete_analysis()

    analysis.margin_year_3 = 10.5

    result = get_rule(
        IPORuleEvaluator().evaluate(analysis),
        9,
    )

    assert result.status == "FAIL"


def test_debt_increase_within_six_percent_passes():
    analysis = make_complete_analysis()

    analysis.debt_previous = 100.0
    analysis.debt_current = 106.0

    result = get_rule(
        IPORuleEvaluator().evaluate(analysis),
        10,
    )

    assert result.status == "PASS"


def test_debt_increase_above_six_percent_fails():
    analysis = make_complete_analysis()

    analysis.debt_previous = 100.0
    analysis.debt_current = 106.01

    result = get_rule(
        IPORuleEvaluator().evaluate(analysis),
        10,
    )

    assert result.status == "FAIL"


def test_missing_debt_is_not_evaluable():
    analysis = make_complete_analysis()

    analysis.debt_previous = None

    result = get_rule(
        IPORuleEvaluator().evaluate(analysis),
        10,
    )

    assert result.status == "NOT_EVALUABLE"


def test_missing_roe_is_not_evaluable():
    analysis = make_complete_analysis()

    analysis.roe = None

    result = get_rule(
        IPORuleEvaluator().evaluate(analysis),
        11,
    )

    assert result.status == "NOT_EVALUABLE"


def test_roe_or_roce_at_ten_percent_fails():
    analysis = make_complete_analysis()

    analysis.roe = 10.0

    result = get_rule(
        IPORuleEvaluator().evaluate(analysis),
        11,
    )

    assert result.status == "FAIL"


def test_missing_peer_is_not_evaluable():
    analysis = make_complete_analysis()

    analysis.peer_pe = None

    result = get_rule(
        IPORuleEvaluator().evaluate(analysis),
        12,
    )

    assert result.status == "NOT_EVALUABLE"


def test_pe_below_fifteen_fails():
    analysis = make_complete_analysis()

    analysis.ipo_pe = 14.99

    result = get_rule(
        IPORuleEvaluator().evaluate(analysis),
        13,
    )

    assert result.status == "FAIL"


def test_pe_above_fifty_fails():
    analysis = make_complete_analysis()

    analysis.ipo_pe = 50.01

    result = get_rule(
        IPORuleEvaluator().evaluate(analysis),
        13,
    )

    assert result.status == "FAIL"


def test_missing_pe_is_not_evaluable():
    analysis = make_complete_analysis()

    analysis.ipo_pe = None

    result = get_rule(
        IPORuleEvaluator().evaluate(analysis),
        13,
    )

    assert result.status == "NOT_EVALUABLE"


def main():
    analysis = make_complete_analysis()

    results = IPORuleEvaluator().evaluate(analysis)

    print("=" * 60)
    print("IPO RULE EVALUATOR")
    print("=" * 60)

    for result in results:
        print(
            f"Rule {result.rule_number}: "
            f"{result.rule_name} -> "
            f"{result.status}"
        )

    print("=" * 60)


if __name__ == "__main__":
    main()