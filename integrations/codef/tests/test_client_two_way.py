"""CODEF 추가인증(2-way) 헬퍼 함수 검증.

여기 쓰인 CF-03002/continue2Way/jobIndex/threadIndex/jti/twoWayTimestamp와
simpleAuth/is2Way/twoWayInfo 구조는 공식 CODEF SDK의 간편인증 추가인증 예제를
따른다 (지난 대화에서 확인된 형태). 실제 네트워크 호출은 하지 않는다 — 이
헬퍼들은 순수하게 dict를 조립/판별하기만 한다.
"""

from django.test import SimpleTestCase

from integrations.codef.client import (
    build_two_way_payload,
    extract_two_way_info,
    is_two_way_required,
)


class IsTwoWayRequiredTests(SimpleTestCase):
    def test_true_when_cf_03002_and_continue2way(self):
        raw = {
            "result": {"code": "CF-03002", "message": "추가인증이 필요합니다."},
            "data": {"continue2Way": True, "jobIndex": 0},
        }

        self.assertTrue(is_two_way_required(raw))

    def test_false_when_success_code(self):
        raw = {
            "result": {"code": "CF-00000", "message": "성공"},
            "data": {"resUsedDate": "20260801"},
        }

        self.assertFalse(is_two_way_required(raw))

    def test_false_when_code_matches_but_continue2way_missing(self):
        # code만 CF-03002고 continue2Way가 없으면(혹은 false) 추가인증 상태로
        # 보지 않는다 — 응답이 예상과 다를 때 잘못 재요청 흐름을 타지 않기 위함.
        raw = {
            "result": {"code": "CF-03002", "message": ""},
            "data": {},
        }

        self.assertFalse(is_two_way_required(raw))

    def test_false_on_empty_payload(self):
        self.assertFalse(is_two_way_required({}))


class ExtractTwoWayInfoTests(SimpleTestCase):
    def test_extracts_all_four_fields(self):
        raw = {
            "result": {"code": "CF-03002"},
            "data": {
                "continue2Way": True,
                "jobIndex": 0,
                "threadIndex": 1,
                "jti": "mock-jti-value",
                "twoWayTimestamp": 1735689600000,
            },
        }

        info = extract_two_way_info(raw)

        self.assertEqual(
            info,
            {
                "jobIndex": 0,
                "threadIndex": 1,
                "jti": "mock-jti-value",
                "twoWayTimestamp": 1735689600000,
            },
        )

    def test_missing_fields_become_none_not_raise(self):
        info = extract_two_way_info({"result": {}, "data": {}})

        self.assertEqual(
            info,
            {
                "jobIndex": None,
                "threadIndex": None,
                "jti": None,
                "twoWayTimestamp": None,
            },
        )


class BuildTwoWayPayloadTests(SimpleTestCase):
    def test_adds_simple_auth_is2way_and_two_way_info(self):
        base_payload = {
            "organization": "0004",
            "loginType": "5",
            "loginTypeLevel": "1",
            "startDate": "20260801",
            "endDate": "20260803",
        }
        two_way_info = {
            "jobIndex": 0,
            "threadIndex": 1,
            "jti": "mock-jti-value",
            "twoWayTimestamp": 1735689600000,
        }

        payload = build_two_way_payload(base_payload, two_way_info, simple_auth="1")

        # base_payload의 필드는 그대로 유지돼야 한다.
        self.assertEqual(payload["organization"], "0004")
        self.assertEqual(payload["startDate"], "20260801")

        # 추가인증 필드가 새로 붙어야 한다.
        self.assertEqual(payload["simpleAuth"], "1")
        self.assertIs(payload["is2Way"], True)
        self.assertEqual(payload["twoWayInfo"], two_way_info)

    def test_custom_simple_auth_value_is_respected(self):
        payload = build_two_way_payload({}, {"jobIndex": 0}, simple_auth="2")

        self.assertEqual(payload["simpleAuth"], "2")

    def test_does_not_mutate_base_payload(self):
        base_payload = {"organization": "0004"}

        build_two_way_payload(base_payload, {"jobIndex": 0}, simple_auth="1")

        self.assertEqual(base_payload, {"organization": "0004"})

    def test_simple_auth_has_no_default_and_is_required(self):
        # simpleAuth를 "카카오=1"과 헷갈려 임의로 기본값을 넣지 않는다 —
        # 상품 명세에서 확인한 값을 호출하는 쪽이 항상 명시해야 한다.
        with self.assertRaises(TypeError):
            build_two_way_payload({}, {"jobIndex": 0})