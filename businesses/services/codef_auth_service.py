from businesses.models import CodefConnection
from integrations.codef.factory import get_codef_provider


ALL_CONNECTION_TYPES = ["CARD", "HOMETAX"]


class InvalidAuthRequestError(Exception):
    """현재 인증 상태에서 허용되지 않는 요청일 때 발생하는 예외."""


def _reset_two_way(conn):
    """2-way 인증에 사용한 임시 정보를 초기화한다."""
    conn.continue_2way = False
    conn.method = ""
    conn.job_index = None
    conn.thread_index = None
    conn.jti = ""
    conn.two_way_timestamp = None


class CodefAuthService:
    def _get_connection(self, business, connection_type):
        conn, _ = CodefConnection.objects.get_or_create(
            business=business,
            connection_type=connection_type,
        )
        return conn

    def request(self, business, connection_type):
        conn = self._get_connection(business, connection_type)
        provider = get_codef_provider()
        result = provider.request_auth(business, connection_type)

        if result["outcome"] == "FAILURE":
            conn.status = "FAILED"
            conn.last_error_code = result.get("error_code", "")
            conn.last_error_message = result.get("error_message", "")
            _reset_two_way(conn)

        elif (
            connection_type == "HOMETAX"
            and result["outcome"] == "AUTH_REQUIRED"
        ):
            conn.status = "AUTH_REQUIRED"
            conn.continue_2way = True
            conn.method = result.get("method", "")
            conn.job_index = result.get("job_index")
            conn.thread_index = result.get("thread_index")
            conn.jti = result.get("jti", "")
            conn.two_way_timestamp = result.get("two_way_timestamp")
            conn.last_error_code = ""
            conn.last_error_message = ""

        else:
            # 인증이 완료되면 연결 상태를 저장하고 2-way 정보를 정리한다.
            conn.connected_id = result.get("connected_id", "")
            conn.status = "CONNECTED"
            conn.last_error_code = ""
            conn.last_error_message = ""
            _reset_two_way(conn)

        conn.save()

        return {
            "type": connection_type,
            "status": conn.status,
        }

    def retry(self, business, connection_type):
        # 재시도는 추가인증이 필요한 HOMETAX 연결에서만 허용한다.
        if connection_type != "HOMETAX":
            raise InvalidAuthRequestError(
                "재시도는 HOMETAX 연결에만 사용할 수 있습니다."
            )

        conn = self._get_connection(business, connection_type)

        if conn.status != "AUTH_REQUIRED":
            raise InvalidAuthRequestError(
                f"AUTH_REQUIRED 상태에서만 재시도할 수 있습니다 "
                f"(현재: {conn.status})."
            )

        provider = get_codef_provider()
        result = provider.retry_auth(business, conn)

        if result["outcome"] == "SUCCESS":
            conn.status = "CONNECTED"
            conn.last_error_code = ""
            conn.last_error_message = ""
            _reset_two_way(conn)

        elif result["outcome"] == "AUTH_REQUIRED":
            # 추가인증이 계속 필요한 경우 갱신된 2-way 정보를 반영한다.
            conn.status = "AUTH_REQUIRED"
            conn.continue_2way = True

            if result.get("job_index") is not None:
                conn.job_index = result["job_index"]

            if result.get("thread_index") is not None:
                conn.thread_index = result["thread_index"]

            if result.get("jti"):
                conn.jti = result["jti"]

        else:
            # 재시도 실패 시 2-way 임시 정보를 정리한다.
            conn.status = "FAILED"
            conn.last_error_code = result.get("error_code", "")
            conn.last_error_message = result.get("error_message", "")
            _reset_two_way(conn)

        conn.save()

        return {
            "type": connection_type,
            "status": conn.status,
        }

    def status(self, business):
        # 연결 이력이 없는 유형도 DISCONNECTED 상태로 포함한다.
        existing = {
            c.connection_type: c.status
            for c in CodefConnection.objects.filter(business=business)
        }

        return {
            "business_id": business.id,
            "connections": [
                {
                    "type": connection_type,
                    "status": existing.get(
                        connection_type,
                        "DISCONNECTED",
                    ),
                }
                for connection_type in ALL_CONNECTION_TYPES
            ],
        }