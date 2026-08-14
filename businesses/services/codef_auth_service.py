from businesses.models import CodefConnection
from integrations.codef.factory import get_codef_provider

ALL_CONNECTION_TYPES = ["CARD", "HOMETAX"]

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

            # 실패한 인증의 2-way 임시 정보를 제거한다.
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
        
    def status(self, business):
    # 연결 이력이 없어도 CARD/HOMETAX 상태를 모두 반환한다.
        existing = {
            c.connection_type: c.status
            for c in CodefConnection.objects.filter(business=business)
        }

        return {
            "business_id": business.id,
            "connections": [
                {
                    "type": t,
                    "status": existing.get(t, "DISCONNECTED"),
                }
                for t in ALL_CONNECTION_TYPES
            ],
        }