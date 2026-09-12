from backend.models.ipo_analysis import IPOAnalysis
from backend.storage.ipo_analysis_repository import IPOAnalysisRepository


def main():
    repository = IPOAnalysisRepository()

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
        sales_year_1=100.0,
        sales_year_2=120.0,
        sales_year_3=150.0,
        profit_year_1=10.0,
        profit_year_2=15.0,
        profit_year_3=22.0,
        margin_year_1=10.0,
        margin_year_2=12.5,
        margin_year_3=14.7,
        debt_previous=50.0,
        debt_current=48.0,
        roe=15.0,
        roce=16.0,
        ipo_pe=25.0,
        peer_pe=28.0,
        source="test",
        source_url="https://example.com",
    )

    inserted = repository.insert(analysis)

    print("Inserted:", inserted)
    print("Analysis count:", repository.count())
    print("Record:")
    print(repository.get_by_ipo_id(1))


if __name__ == "__main__":
    main()