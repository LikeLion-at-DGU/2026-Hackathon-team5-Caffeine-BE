from unittest.mock import patch, MagicMock
from django.test import TestCase

from integrations.seoul_commercial import SeoulCommercialClient, SeoulCommercialClientError


class SeoulCommercialClientTests(TestCase):
    def test_missing_api_key_raises_error(self):
        client = SeoulCommercialClient(api_key="")
        with self.assertRaises(SeoulCommercialClientError):
            client.fetch_estimated_sales()

    @patch("integrations.seoul_commercial.client.requests.get")
    def test_fetch_estimated_sales_success(self, mock_get):
        mock_res = MagicMock()
        mock_res.json.return_value = {
            "VwsmTrdarSelngQq": {
                "list_total_count": 1,
                "RESULT": {"CODE": "INFO-000", "MESSAGE": "정상 처리되었습니다"},
                "row": [
                    {
                        "TRDAR_CD_NM": "성수동골목",
                        "SVC_INDUTY_CD": "CS100010",
                        "SVC_INDUTY_CD_NM": "커피-음료",
                        "THSMON_SELNG_AMT": 500000000,
                    }
                ],
            }
        }
        mock_res.raise_for_status.return_value = None
        mock_get.return_value = mock_res

        client = SeoulCommercialClient(api_key="mock-key")
        rows = client.fetch_estimated_sales(start_index=1, end_index=5)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["TRDAR_CD_NM"], "성수동골목")
        self.assertEqual(rows[0]["SVC_INDUTY_CD"], "CS100010")
