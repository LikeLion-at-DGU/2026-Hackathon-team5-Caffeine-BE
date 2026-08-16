from django.test import TestCase
from rest_framework.test import APIClient

from businesses.models import Business


class BusinessInfoAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.business = Business.objects.create(
            business_name="카페비서 성수점",
            business_number="123-45-67890",
            tax_type="GENERAL",
            industry_code="552301",
        )
        self.url = f"/api/businesses/{self.business.id}/settings/business/"

    def test_get_business_info_success(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["business_name"], "카페비서 성수점")
        self.assertEqual(response.data["data"]["business_number"], "123-45-67890")
        self.assertEqual(response.data["data"]["representative_name"], "")

    def test_get_business_info_for_nonexistent_business_returns_404(self):
        response = self.client.get("/api/businesses/9999/settings/business/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["code"], "BUSINESS_NOT_FOUND")

    def test_update_representative_name_saves_to_business_model(self):
        response = self.client.patch(self.url, {"representative_name": "유지은"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["representative_name"], "유지은")

        self.business.refresh_from_db()
        self.assertEqual(self.business.representative_name, "유지은")

    def test_update_business_name_saves_to_businesses_model(self):
        response = self.client.patch(self.url, {"business_name": "카페비서 강남점"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.business.refresh_from_db()
        self.assertEqual(self.business.business_name, "카페비서 강남점")

    def test_patch_cannot_change_tax_type(self):
        response = self.client.patch(self.url, {"tax_type": "SIMPLE"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.business.refresh_from_db()
        self.assertEqual(self.business.tax_type, "GENERAL")

    def test_update_both_fields_in_one_request(self):
        response = self.client.patch(
            self.url,
            {"business_name": "카페비서 강남점", "representative_name": "유지은"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.business.refresh_from_db()

        self.assertEqual(self.business.business_name, "카페비서 강남점")
        self.assertEqual(self.business.representative_name, "유지은")

    def test_representative_name_visible_via_businesses_api_too(self):
        # settings API로 수정하면 businesses API 응답에도 바로 반영되는지 확인
        # (예전엔 BusinessProfile 별도 테이블이라 여기서 어긋났었음 — 이슈 #20의 핵심 검증)
        self.client.patch(self.url, {"representative_name": "유지은"}, format="json")

        response = self.client.get(f"/api/businesses/{self.business.id}/")
        self.assertEqual(response.data["data"]["representative_name"], "유지은")