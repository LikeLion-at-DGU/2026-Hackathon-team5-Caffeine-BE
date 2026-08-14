from rest_framework.response import Response


def success_response(data=None, code="SUCCESS", message="", status=200):
    """성공 응답 공통 포맷.

    {"success": true, "code": ..., "message": ..., "data": ...}
    """
    return Response(
        {"success": True, "code": code, "message": message, "data": data},
        status=status,
    )


def error_response(code="ERROR", message="", errors=None, status=400):
    """실패 응답 공통 포맷.

    {"success": false, "code": ..., "message": ..., "errors": ...}
    errors는 항상 dict로 내려간다 (값이 없으면 빈 dict {}).
    """
    return Response(
        {"success": False, "code": code, "message": message, "errors": errors or {}},
        status=status,
    )