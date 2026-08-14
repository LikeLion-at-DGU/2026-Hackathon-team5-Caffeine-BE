from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from businesses.models import Business, TaxTypeHistory


@override_settings(CODEF_MODE="mock")
class TaxTypeSyncTests(APITestCase):
    def setUp(self):
        self.business = Business.objects.create(
            business_name="카페비서 데모카페",
            tax_type_code="",
        )

    def test_sync_applies_mock_tax_type(self):
        url = reverse(
            "business-tax-type-sync",
            kwargs={"pk": self.business.id},
        )

        res = self.client.post(url)

        self.assertEqual(res.status_code, 200)

        self.business.refresh_from_db()

        # Mock 응답의 과세유형 코드 "1"이 일반과세자로 반영되는지 확인한다.
        self.assertEqual(self.business.tax_type_code, "1")
        self.assertEqual(self.business.tax_type, "GENERAL")

    def test_sync_creates_history_only_when_code_changes(self):
        self.business.tax_type_code = "1"
        self.business.save()

        url = reverse(
            "business-tax-type-sync",
            kwargs={"pk": self.business.id},
        )

        self.client.post(url)

        # 기존 코드와 새 코드가 같으면 변경 이력을 생성하지 않는다.
        self.assertEqual(
            TaxTypeHistory.objects.filter(
                business=self.business
            ).count(),
            0,
        )

    def test_sync_rejects_mismatched_business_number(self):
        # 요청한 사업자번호와 CODEF 응답의 사업자번호가 다르면 동기화하지 않는다.
        self.business.business_number = "9999999999"
        self.business.save()

        url = reverse(
            "business-tax-type-sync",
            kwargs={"pk": self.business.id},
        )

        res = self.client.post(url)

        self.assertEqual(res.status_code, 502)
        self.assertIn("error", res.data)

        self.business.refresh_from_db()
        self.assertEqual(self.business.tax_type_code, "")

    def test_sync_does_not_blank_out_existing_code_when_response_empty(self):
        self.business.tax_type_code = "1"
        self.business.tax_type = "GENERAL"
        self.business.save()

        # 성공 응답이지만 과세유형 코드가 비어 있는 상황을 재현한다.
        empty_result = {
            "outcome": "SUCCESS",
            "company_identity_no": "",
            "business_status": "계속사업자",
            "taxation_type_code": "",
            "closing_date": "",
            "transfer_tax_type_date": "",
        }

        url = reverse(
            "business-tax-type-sync",
            kwargs={"pk": self.business.id},
        )

        with patch(
            "businesses.services.tax_type_service.get_codef_provider"
        ) as mock_factory:
            mock_factory.return_value.get_business_status.return_value = (
                empty_result
            )
            res = self.client.post(url)

        self.assertEqual(res.status_code, 502)

        self.business.refresh_from_db()

        # 비어 있는 응답으로 기존 과세유형을 덮어쓰지 않는다.
        self.assertEqual(self.business.tax_type_code, "1")
        self.assertEqual(self.business.tax_type, "GENERAL")

    def test_sync_maps_unknown_code_to_unknown_not_stale_value(self):
        self.business.tax_type_code = "1"
        self.business.tax_type = "GENERAL"
        self.business.save()

        # 매핑되지 않은 과세유형 코드가 반환되는 상황을 재현한다.
        weird_result = {
            "outcome": "SUCCESS",
            "company_identity_no": "",
            "business_status": "계속사업자",
            "taxation_type_code": "999",
            "closing_date": "",
            "transfer_tax_type_date": "",
        }

        url = reverse(
            "business-tax-type-sync",
            kwargs={"pk": self.business.id},
        )

        with patch(
            "businesses.services.tax_type_service.get_codef_provider"
        ) as mock_factory:
            mock_factory.return_value.get_business_status.return_value = (
                weird_result
            )
            res = self.client.post(url)

        self.assertEqual(res.status_code, 200)

        self.business.refresh_from_db()

        # 알 수 없는 코드는 이전 값 대신 UNKNOWN으로 저장한다.
        self.assertEqual(self.business.tax_type_code, "999")
        self.assertEqual(self.business.tax_type, "UNKNOWN")