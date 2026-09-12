from backend.models.ipo_analysis import IPOAnalysis
from backend.storage.ipo_rule_repository import IPORuleRepository
from backend.strategy.ipo_rule_evaluator import IPORuleEvaluator


def main():
    analysis = IPOAnalysis(
        ipo_id=1,
        ipo_type="MAINBOARD",
        qib_subscription=25.5,
        overall_subscription=18.2,
        gmp_day_1=12.0,
        gmp_day_2=11.5,
        fresh_issue_percentage=75.0,
        ofs_percentage=25.0,
        anchor_investor_count=8,
        debt_previous=50.0,
        debt_current=48.0,
        ipo_pe=25.0,
    )

    evaluator = IPORuleEvaluator()
    results = evaluator.evaluate(analysis)

    repository = IPORuleRepository()

    saved = repository.save_results(
        ipo_id=analysis.ipo_id,
        results=results,
    )

    print("Results saved:", saved)
    print("Passed:", repository.count_passed(analysis.ipo_id))
    print("Stored results:")

    for result in repository.get_results(analysis.ipo_id):
        print(result)


if __name__ == "__main__":
    main()