from backend.collectors.ipo.chittorgarh_issue_details import (
    ChittorgarhIssueDetailsSource,
)


def main():
    source = ChittorgarhIssueDetailsSource()

    url = (
        "https://www.chittorgarh.com/ipo/"
        "tempsens-instruments-india-ipo/2668/"
    )

    result = source.fetch(url)

    print("Issue details:")
    print(result)


if __name__ == "__main__":
    main()