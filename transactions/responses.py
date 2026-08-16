from rest_framework.response import Response


def success_response(*, code, message, data, status=200):
    return Response(
        {
            "success": True,
            "code": code,
            "message": message,
            "data": data,
        },
        status=status,
    )


def error_response(*, code, message, errors=None, status=400):
    return Response(
        {
            "success": False,
            "code": code,
            "message": message,
            "errors": errors or {},
        },
        status=status,
    )
