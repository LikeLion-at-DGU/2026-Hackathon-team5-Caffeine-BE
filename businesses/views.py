from rest_framework import mixins
from rest_framework.viewsets import GenericViewSet

from .models import Business
from .serializers import BusinessSerializer


class BusinessViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    """사업장 정보 조회 및 부분 수정 API."""

    # 사업장 조회(GET)와 부분 수정(PATCH)만 제공
    # POST는 추후 @action 기반 API에서 사용
    http_method_names = ["get", "post", "patch", "head", "options"]

    queryset = Business.objects.all()
    serializer_class = BusinessSerializer