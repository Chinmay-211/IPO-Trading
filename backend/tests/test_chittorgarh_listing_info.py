from unittest.mock import Mock

from backend.collectors.ipo.chittorgarh_source import (
    ChittorgarhIPODataSource,
)


def main():
    source = ChittorgarhIPODataSource()

    response = Mock()
    response.url = (
        "https://www.chittorgarh.com/ipo/"
        "tempsens-instruments-india-ipo/2668/"
    )

    response.text = """
    <script>
    "nse_symbol":"TEMPSENS",
    "timetable_listing_dt":"Friday, August 28, 2026"
    </script>
    """

    source.session.get = Mock(
        return_value=response
    )

    result = source.fetch_listing_info(
        response.url
    )

    print("Listing info:")
    print(result)

    assert result["ipo_id"] == 2668
    assert result["symbol"] == "TEMPSENS"
    assert str(result["listing_date"]) == "2026-08-28"


if __name__ == "__main__":
    main()