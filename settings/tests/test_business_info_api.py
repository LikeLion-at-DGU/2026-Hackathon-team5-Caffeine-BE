from django.test import TestCase
from rest_framework.test import APIClient

from businesses.models import Business
from settings.models import BusinessProfile


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
        # representative_name은 아직 입력 전이라 빈 문자열이어야 함
        self.assertEqual(response.data["data"]["representative_name"], "")

    def test_get_business_info_for_nonexistent_business_returns_404(self):
        response = self.client.get("/api/businesses/9999/settings/business/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["code"], "BUSINESS_NOT_FOUND")

    def test_update_representative_name_saves_to_settings_profile(self):
        response = self.client.patch(self.url, {"representative_name": "유지은"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["representative_name"], "유지은")

        profile = BusinessProfile.objects.get(business=self.business)
        self.assertEqual(profile.representative_name, "유지은")

    def test_update_business_name_saves_to_businesses_model(self):
        response = self.client.patch(self.url, {"business_name": "카페비서 강남점"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.business.refresh_from_db()
        self.assertEqual(self.business.business_name, "카페비서 강남점")

    def test_update_both_fields_in_one_request(self):
        response = self.client.patch(
            self.url,
            {"business_name": "카페비서 강남점", "representative_name": "유지은"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.business.refresh_from_db()
        profile = BusinessProfile.objects.get(business=self.business)

        self.assertEqual(self.business.business_name, "카페비서 강남점")
        self.assertEqual(profile.representative_name, "유지은")

    def test_get_business_info_does_not_create_duplicate_profile(self):
        # 여러 번 조회해도 BusinessProfile이 하나만 생성되는지 확인
        self.client.get(self.url)
        self.client.get(self.url)

        self.assertEqual(BusinessProfile.objects.filter(business=self.business).count(), 1)