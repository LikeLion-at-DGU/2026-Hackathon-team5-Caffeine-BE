import math

from django.utils import timezone
from rest_framework.views import APIView

from .models import Transaction, TransactionDuplicate
from .responses import error_response, success_response
from .serializers import (
    DuplicateListQuerySerializer,
    DuplicateResolutionSerializer,
    TransactionCategoryUpdateSerializer,
    TransactionDuplicateSerializer,
    TransactionListQuerySerializer,
    TransactionPurposeUpdateSerializer,
    TransactionSerializer,
    TransactionSyncRequestSerializer,
)
from .services.normalizers.helpers import TransactionNormalizationError
from .services.sync_service import TransactionSourceMismatchError, TransactionSyncService


def _paginated_data(queryset, serializer_class, *, page, page_size):
    total_count = queryset.count()
    offset = (page - 1) * page_size
    items = queryset[offset : offset + page_size]
    return {
        "items": serializer_class(items, many=True).data,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": math.ceil(total_count / page_size),
        },
    }


class TransactionSyncView(APIView):
    def post(self, request):
        serializer = TransactionSyncRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                code="INVALID_TRANSACTION_SYNC_REQUEST",
                message="거래 동기화 요청이 올바르지 않습니다.",
                errors=serializer.errors,
            )

        params = serializer.validated_data
        try:
            result = TransactionSyncService().sync(
                business=params["business"],
                start_date=params["start_date"],
                end_date=params["end_date"],
                sources=params["sources"],
            )
        except (TransactionNormalizationError, TransactionSourceMismatchError) as exc:
            return error_response(
                code="CODEF_TRANSACTION_DATA_ERROR",
                message="CODEF 거래 데이터를 처리하지 못했습니다.",
                errors={"detail": str(exc)},
                status=502,
            )
        except NotImplementedError as exc:
            return error_response(
                code="CODEF_TRANSACTION_SOURCE_UNAVAILABLE",
                message="현재 모드에서는 거래 데이터 소스를 사용할 수 없습니다.",
                errors={"detail": str(exc)},
                status=502,
            )

        return success_response(
            code="TRANSACTION_SYNC_SUCCESS",
            message="거래 데이터를 동기화했습니다.",
            data=result,
        )


class TransactionListView(APIView):
    def get(self, request):
        query = TransactionListQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return error_response(
                code="INVALID_TRANSACTION_QUERY",
                message="거래 목록 조회 조건이 올바르지 않습니다.",
                errors=query.errors,
            )

        params = query.validated_data
        queryset = Transaction.objects.filter(business=params["business"])
        if params.get("start_date"):
            queryset = queryset.filter(transaction_date__gte=params["start_date"])
        if params.get("end_date"):
            queryset = queryset.filter(transaction_date__lte=params["end_date"])
        for field in ["transaction_type", "source_type", "category", "expense_purpose"]:
            if params.get(field):
                queryset = queryset.filter(**{field: params[field]})

        data = _paginated_data(
            queryset,
            TransactionSerializer,
            page=params["page"],
            page_size=params["page_size"],
        )
        return success_response(
            code="TRANSACTION_LIST_SUCCESS",
            message="거래 목록을 조회했습니다.",
            data=data,
        )


class TransactionDetailView(APIView):
    def get(self, request, transaction_id):
        transaction = Transaction.objects.filter(id=transaction_id).first()
        if transaction is None:
            return error_response(
                code="TRANSACTION_NOT_FOUND",
                message="거래를 찾을 수 없습니다.",
                status=404,
            )
        return success_response(
            code="TRANSACTION_DETAIL_SUCCESS",
            message="거래 상세 정보를 조회했습니다.",
            data=TransactionSerializer(transaction).data,
        )


class TransactionCategoryView(APIView):
    def patch(self, request, transaction_id):
        transaction = Transaction.objects.filter(id=transaction_id).first()
        if transaction is None:
            return error_response(
                code="TRANSACTION_NOT_FOUND",
                message="거래를 찾을 수 없습니다.",
                status=404,
            )

        serializer = TransactionCategoryUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                code="INVALID_TRANSACTION_CATEGORY",
                message="카테고리 값이 올바르지 않습니다.",
                errors=serializer.errors,
            )

        transaction.category = serializer.validated_data["category"]
        transaction.classification_source = Transaction.ClassificationSource.USER
        transaction.classification_confidence = None
        transaction.save(
            update_fields=[
                "category",
                "classification_source",
                "classification_confidence",
                "updated_at",
            ]
        )
        return success_response(
            code="TRANSACTION_CATEGORY_UPDATED",
            message="거래 카테고리를 수정했습니다.",
            data=TransactionSerializer(transaction).data,
        )


class TransactionPurposeView(APIView):
    def patch(self, request, transaction_id):
        transaction = Transaction.objects.filter(id=transaction_id).first()
        if transaction is None:
            return error_response(
                code="TRANSACTION_NOT_FOUND",
                message="거래를 찾을 수 없습니다.",
                status=404,
            )

        serializer = TransactionPurposeUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                code="INVALID_TRANSACTION_PURPOSE",
                message="지출 목적 값이 올바르지 않습니다.",
                errors=serializer.errors,
            )

        transaction.expense_purpose = serializer.validated_data["expense_purpose"]
        transaction.expense_purpose_source = Transaction.ClassificationSource.USER
        transaction.save(
            update_fields=[
                "expense_purpose",
                "expense_purpose_source",
                "updated_at",
            ]
        )
        return success_response(
            code="TRANSACTION_PURPOSE_UPDATED",
            message="거래의 지출 목적을 수정했습니다.",
            data=TransactionSerializer(transaction).data,
        )


class TransactionDuplicateListView(APIView):
    def get(self, request):
        query = DuplicateListQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return error_response(
                code="INVALID_DUPLICATE_QUERY",
                message="중복 거래 조회 조건이 올바르지 않습니다.",
                errors=query.errors,
            )

        params = query.validated_data
        queryset = TransactionDuplicate.objects.select_related(
            "primary_transaction",
            "suspected_transaction",
        ).filter(business=params["business"], status=params["status"])
        data = _paginated_data(
            queryset,
            TransactionDuplicateSerializer,
            page=params["page"],
            page_size=params["page_size"],
        )
        return success_response(
            code="TRANSACTION_DUPLICATE_LIST_SUCCESS",
            message="중복 의심 거래 목록을 조회했습니다.",
            data=data,
        )


class TransactionDuplicateResolutionView(APIView):
    def patch(self, request, duplicate_id):
        duplicate = TransactionDuplicate.objects.filter(id=duplicate_id).first()
        if duplicate is None:
            return error_response(
                code="TRANSACTION_DUPLICATE_NOT_FOUND",
                message="중복 거래 후보를 찾을 수 없습니다.",
                status=404,
            )

        serializer = DuplicateResolutionSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                code="INVALID_DUPLICATE_STATUS",
                message="중복 확정 상태가 올바르지 않습니다.",
                errors=serializer.errors,
            )

        duplicate.status = serializer.validated_data["status"]
        duplicate.resolved_at = timezone.now()
        duplicate.save(update_fields=["status", "resolved_at", "updated_at"])
        return success_response(
            code="TRANSACTION_DUPLICATE_RESOLVED",
            message="중복 여부를 확정했습니다.",
            data=TransactionDuplicateSerializer(duplicate).data,
        )
