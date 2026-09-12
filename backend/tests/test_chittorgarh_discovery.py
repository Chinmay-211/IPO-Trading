import json
import unittest
from unittest.mock import Mock

from backend.collectors.ipo.chittorgarh_source import (
    ChittorgarhIPODataSource,
)


class ChittorgarhDiscoveryTest(unittest.TestCase):
    def test_parse_report_rows_normalizes_and_filters_duplicates(self):
        payload = {
            "reportTableData": [
                {
                    "~id": 2668,
                    "Company": "Tempsens Instruments (India) Ltd.",
                    "Issue Type": "Mainboard",
                    "~urlrewrite_folder_name": "tempsens-instruments-india-ipo",
                    "Opening Date": "20-Aug-2026",
                    "Closing Date": "24-Aug-2026",
                    "Listing Date": "",
                },
                {
                    "~id": 2668,
                    "Company": "Duplicate row",
                    "Issue Type": "Mainboard",
                    "~urlrewrite_folder_name": "tempsens-instruments-india-ipo",
                },
                {
                    "~id": 3000,
                    "Company": "Example SME Ltd.",
                    "Issue Type": "SME",
                    "~urlrewrite_folder_name": "example-sme-ipo",
                },
            ]
        }

        source_url = "https://www.chittorgarh.com/report/ipo-list/"
        records = ChittorgarhIPODataSource().parse(
            json.dumps(payload),
            source_url,
        )

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertIsInstance(record, dict)
        self.assertEqual(record["ipo_id"], 2668)
        self.assertEqual(
            record["company_name"],
            "Tempsens Instruments (India) Ltd.",
        )
        self.assertEqual(record["ipo_type"], "MAINBOARD")
        self.assertEqual(
            record["detail_url"],
            "https://www.chittorgarh.com/ipo/"
            "tempsens-instruments-india-ipo/2668/",
        )
        self.assertEqual(record["source_url"], source_url)

    def test_fetch_reads_api_pages(self):
        source = ChittorgarhIPODataSource()
        first = Mock()
        first.json.return_value = {
            "totalPages": 2,
            "reportTableData": [
                {
                    "~id": 1,
                    "Company": "First Ltd.",
                    "Issue Type": "Mainboard",
                    "~urlrewrite_folder_name": "first-ipo",
                }
            ],
        }
        second = Mock()
        second.json.return_value = {
            "totalPages": 2,
            "reportTableData": [
                {
                    "~id": 1,
                    "Company": "First Ltd.",
                    "Issue Type": "Mainboard",
                    "~urlrewrite_folder_name": "first-ipo",
                },
                {
                    "~id": 2,
                    "Company": "Second Ltd.",
                    "Issue Type": "Mainboard",
                    "~urlrewrite_folder_name": "second-ipo",
                },
            ],
        }
        first.url = source.MAINBOARD_LIST_URL
        second.url = source.MAINBOARD_LIST_URL
        source.session.get = Mock(side_effect=[first, second])

        records = source.fetch()

        self.assertEqual([record["ipo_id"] for record in records], [1, 2])
        self.assertEqual(source.session.get.call_count, 2)


if __name__ == "__main__":
    unittest.main()