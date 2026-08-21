from rest_framework import status
from rest_framework.views import exception_handler as drf_exception_handler


ERROR_DEFAULTS = {
    status.HTTP_400_BAD_REQUEST: ("VALIDATION_ERROR", "입력값이 올바르지 않습니다."),
    status.HTTP_401_UNAUTHORIZED: ("AUTHENTICATION_REQUIRED", "인증이 필요합니다."),
    status.HTTP_403_FORBIDDEN: ("PERMISSION_DENIED", "요청 권한이 없습니다."),
    status.HTTP_404_NOT_FOUND: ("NOT_FOUND", "요청한 리소스를 찾을 수 없습니다."),
    status.HTTP_405_METHOD_NOT_ALLOWED: ("METHOD_NOT_ALLOWED", "허용되지 않는 요청 방식입니다."),
    status.HTTP_429_TOO_MANY_REQUESTS: ("THROTTLED", "요청이 너무 많습니다. 잠시 후 다시 시도해주세요."),
}


def custom_exception_handler(exc, context):
    """DRF가 처리한 예외만 서비스의 공통 오류 형식으로 변환한다."""
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    code, message = ERROR_DEFAULTS.get(
        response.status_code,
        ("HTTP_ERROR", "요청을 처리할 수 없습니다."),
    )
    if response.status_code in {
        status.HTTP_404_NOT_FOUND,
        status.HTTP_405_METHOD_NOT_ALLOWED,
    }:
        errors = {}
    else:
        errors = response.data if isinstance(response.data, dict) else {"detail": response.data}
    response.data = {
        "success": False,
        "code": code,
        "message": message,
        "errors": errors,
    }
    return response
