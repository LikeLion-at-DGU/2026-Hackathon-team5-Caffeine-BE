from django.urls import reverse
from rest_framework.test import APITestCase

from businesses.models import Business


class BusinessDetailApiTests(APITestCase):
    def setUp(self):
        # 사업자번호가 없는 데모 사업장으로 기본 API 동작을 확인한다.
        self.business = Business.objects.create(
            business_name="카페비서 데모카페",
            business_number=None,
            business_type="음식점업",
            business_item="커피전문점",
        )

    def test_get_business_detail(self):
        url = reverse("business-detail", kwargs={"pk": self.business.id})

        res = self.client.get(url)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["business_name"], "카페비서 데모카페")
        self.assertIsNone(res.data["business_number"])

    def test_patch_business_detail(self):
        url = reverse("business-detail", kwargs={"pk": self.business.id})

        res = self.client.patch(
            url,
            {"business_name": "카페비서 2호점"},
            format="json",
        )

        self.assertEqual(res.status_code, 200)

        self.business.refresh_from_db()
        self.assertEqual(self.business.business_name, "카페비서 2호점")

    def test_get_business_detail_representative_name_blank_by_default(self):
        url = reverse("business-detail", kwargs={"pk": self.business.id})

        res = self.client.get(url)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["representative_name"], "")

    def test_patch_can_update_representative_name(self):
        url = reverse("business-detail", kwargs={"pk": self.business.id})

        res = self.client.patch(
            url,
            {"representative_name": "유지은"},
            format="json",
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["representative_name"], "유지은")

        self.business.refresh_from_db()
        self.assertEqual(self.business.representative_name, "유지은")
        
    def test_patch_cannot_change_is_demo(self):
        # 서버 관리 필드는 PATCH 요청으로 변경되지 않아야 한다.
        self.assertTrue(self.business.is_demo)

        url = reverse("business-detail", kwargs={"pk": self.business.id})
        res = self.client.patch(
            url,
            {"is_demo": False},
            format="json",
        )

        self.assertEqual(res.status_code, 200)

        self.business.refresh_from_db()
        self.assertTrue(self.business.is_demo)

    # 명세에 없는 기본 CRUD API는 제공하지 않는다.

    def test_list_endpoint_not_available(self):
        res = self.client.get("/api/businesses/")
        self.assertIn(res.status_code, (404, 405))

    def test_create_not_allowed(self):
        res = self.client.post(
            "/api/businesses/",
            {"business_name": "새 사업장"},
            format="json",
        )
        self.assertIn(res.status_code, (404, 405))

    def test_put_not_allowed(self):
        url = reverse("business-detail", kwargs={"pk": self.business.id})

        res = self.client.put(
            url,
            {"business_name": "전체교체"},
            format="json",
        )

        self.assertEqual(res.status_code, 405)

    def test_delete_not_allowed(self):
        url = reverse("business-detail", kwargs={"pk": self.business.id})

        res = self.client.delete(url)

        self.assertEqual(res.status_code, 405)