from unittest.mock import patch, MagicMock
import requests
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

    @patch("integrations.seoul_commercial.client.requests.get")
    def test_request_failure_does_not_expose_api_key_in_log_or_error(self, mock_get):
        secret_key = "secret-seoul-api-key"
        mock_get.side_effect = requests.ConnectionError(
            f"connection failed: http://openapi.seoul.go.kr:8088/{secret_key}/json/service"
        )
        client = SeoulCommercialClient(api_key=secret_key)

        with self.assertLogs("integrations.seoul_commercial.client", level="WARNING") as logs:
            with self.assertRaises(SeoulCommercialClientError) as raised:
                client.fetch_estimated_sales()

        output = " ".join(logs.output) + " " + str(raised.exception)
        self.assertNotIn(secret_key, output)
        self.assertNotIn("openapi.seoul.go.kr", output)
