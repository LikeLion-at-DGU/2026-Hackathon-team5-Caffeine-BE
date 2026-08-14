from rest_framework.views import exception_handler as drf_exception_handler


def custom_exception_handler(exc, context):
    """DRF가 자동으로 생성하는 에러 응답(404, 405, 기본 400 등)을
    success/code/message/errors 공통 포맷으로 바꿔준다.
    """
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    status_code = response.status_code

    if status_code == 404:
        code, message = "BUSINESS_NOT_FOUND", "사업장을 찾을 수 없습니다."
        errors = {}
    elif status_code == 405:
        code, message = "METHOD_NOT_ALLOWED", "허용되지 않는 요청 방식입니다."
        errors = {}
    elif status_code == 400:
        code, message = "VALIDATION_ERROR", "입력값이 올바르지 않습니다."
        errors = response.data if isinstance(response.data, dict) else {"detail": response.data}
    else:
        code, message = "ERROR", "요청을 처리할 수 없습니다."
        errors = response.data if isinstance(response.data, dict) else {"detail": response.data}

    response.data = {"success": False, "code": code, "message": message, "errors": errors}
    return response