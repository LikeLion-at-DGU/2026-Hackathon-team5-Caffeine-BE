import math

from rest_framework.views import APIView

from core.responses import error_response, success_response
from core.permissions import check_business_owner
from transactions.models import Transaction

from .models import DeductionReview, MonthlyClose
from .serializers import (
    BusinessPeriodQuerySerializer,
    DeductionConfirmSerializer,
    DeductionListQuerySerializer,
    DeductionReviewSerializer,
    TaxBusinessScopeSerializer,
)
from .services.closing_service import (
    MonthAlreadyClosed,
    MonthlyCloseService,
    UnconfirmedTransactionsExist,
)
from .services.deduction_service import DeductionReviewService
from .services.deduction_breakdown_service import build_deduction_breakdown
from .services.periods import month_range, parse_year_month
from transactions.services.querysets import effective_purchase_transactions
from .services.vat_service import UnsupportedTaxType, VatForecastService


def _invalid_query(serializer, code="INVALID_PERIOD"):
    return error_response(
        code=code,
        message="조회 조건이 올바르지 않습니다.",
        errors=serializer.errors,
    )


def _period_query_data(request):
    data = request.query_params.copy()
    if not data.get("year_month") and data.get("year") and data.get("month"):
        try:
            data["year_month"] = f'{int(data["year"]):04d}-{int(data["month"]):02d}'
        except (TypeError, ValueError):
            pass
    return data


def _check_tax_business_owner(request, business):
    """공통 사업장 권한 검사로 위임한다."""
    return check_business_owner(request, business)


def _business_scope(request):
    business_id = request.data.get("business_id") or request.query_params.get("business_id")
    serializer = TaxBusinessScopeSerializer(data={"business_id": business_id})
    if not serializer.is_valid():
        return None, error_response(
            code="INVALID_BUSINESS_SCOPE",
            message="business_id가 필요하거나 올바르지 않습니다.",
            errors=serializer.errors,
        )
    business = serializer.validated_data["business"]
    owner_err = _check_tax_business_owner(request, business)
    if owner_err:
        return None, owner_err
    return business, None


class DeductionListView(APIView):
    def get(self, request):
        query = DeductionListQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return _invalid_query(query, "INVALID_DEDUCTION_QUERY")

        params = query.validated_data
        owner_err = _check_tax_business_owner(request, params["business"])
        if owner_err:
            return owner_err

        year, month = parse_year_month(params["year_month"])
        start_date, end_date = month_range(year, month)
        purchases = effective_purchase_transactions(
            business=params["business"],
            start_date=start_date,
            end_date=end_date,
        )
        DeductionReviewService.ensure_for_queryset(purchases)
        reviews = DeductionReview.objects.select_related("transaction", "transaction__business").filter(
            transaction__in=purchases
        )
        for field in ["suggested_status", "confirmed_status"]:
            if params.get(field):
                reviews = reviews.filter(**{field: params[field]})

        total_count = reviews.count()
        offset = (params["page"] - 1) * params["page_size"]
        items = reviews[offset : offset + params["page_size"]]
        return success_response(
            code="DEDUCTION_LIST_SUCCESS",
            message="공제 검토 거래를 조회했습니다.",
            data={
                "items": DeductionReviewSerializer(items, many=True).data,
                "pagination": {
                    "page": params["page"],
                    "page_size": params["page_size"],
                    "total_count": total_count,
                    "total_pages": math.ceil(total_count / params["page_size"]),
                },
            },
        )


class DeductionConfirmView(APIView):
    def patch(self, request, transaction_id):
        business, error = _business_scope(request)
        if error:
            return error
        transaction = Transaction.objects.filter(
            id=transaction_id,
            business=business,
            transaction_type=Transaction.TransactionType.PURCHASE,
        ).first()
        if transaction is None:
            return error_response(
                code="TRANSACTION_NOT_FOUND",
                message="공제 검토 대상 거래를 찾을 수 없습니다.",
                status=404,
            )
        if MonthlyCloseService.is_closed(
            business_id=transaction.business_id,
            transaction_date=transaction.transaction_date,
        ):
            return error_response(
                code="MONTH_ALREADY_CLOSED",
                message="마감된 월의 공제 여부는 수정할 수 없습니다.",
                status=409,
            )

        serializer = DeductionConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                code="INVALID_DEDUCTION_STATUS",
                message="공제 확정 상태가 올바르지 않습니다.",
                errors=serializer.errors,
            )
        review = DeductionReviewService.get_or_create(transaction)
        review = DeductionReviewService.confirm(
            review=review,
            confirmed_status=serializer.validated_data["confirmed_status"],
        )
        return success_response(
            code="DEDUCTION_CONFIRMED",
            message="공제 여부를 최종 확인했습니다.",
            data=DeductionReviewSerializer(review).data,
        )


class DeductionAiSuggestView(APIView):
    def post(self, request, transaction_id):
        business, error = _business_scope(request)
        if error:
            return error
        if not Transaction.objects.filter(
            id=transaction_id,
            business=business,
            transaction_type=Transaction.TransactionType.PURCHASE,
        ).exists():
            return error_response(
                code="TRANSACTION_NOT_FOUND",
                message="공제 검토 대상 거래를 찾을 수 없습니다.",
                status=404,
            )
        return error_response(
            code="AI_SUGGESTION_NOT_CONFIGURED",
            message="AI 공제 추천은 현재 비활성화되어 있습니다.",
            status=501,
        )


class VatForecastView(APIView):
    def get(self, request):
        query = BusinessPeriodQuerySerializer(data=_period_query_data(request))
        if not query.is_valid():
            return _invalid_query(query)
        params = query.validated_data
        owner_err = _check_tax_business_owner(request, params["business"])
        if owner_err:
            return owner_err

        year, month = parse_year_month(params["year_month"])
        try:
            data = VatForecastService.calculate(
                business=params["business"],
                year=year,
                month=month,
            )
        except UnsupportedTaxType as exc:
            return error_response(
                code="UNSUPPORTED_TAX_TYPE",
                message=str(exc),
                status=422,
            )
        return success_response(
            code="VAT_FORECAST_SUCCESS",
            message="예상 부가세를 조회했습니다.",
            data=data,
        )


class DeductionBreakdownView(APIView):
    def get(self, request):
        query = BusinessPeriodQuerySerializer(data=_period_query_data(request))
        if not query.is_valid():
            return _invalid_query(query, "INVALID_DEDUCTION_BREAKDOWN_QUERY")
        params = query.validated_data
        owner_err = _check_tax_business_owner(request, params["business"])
        if owner_err:
            return owner_err

        year, month = parse_year_month(params["year_month"])
        data = build_deduction_breakdown(
            business=params["business"],
            year=year,
            month=month,
        )
        return success_response(
            code="DEDUCTION_BREAKDOWN_SUCCESS",
            message="부가세 공제 구조를 조회했습니다.",
            data=data,
        )


class MonthlyCloseDetailView(APIView):
    def get(self, request, year_month):
        query = BusinessPeriodQuerySerializer(
            data={"business_id": request.query_params.get("business_id"), "year_month": year_month}
        )
        if not query.is_valid():
            return _invalid_query(query, "INVALID_YEAR_MONTH")
        params = query.validated_data
        owner_err = _check_tax_business_owner(request, params["business"])
        if owner_err:
            return owner_err

        year, month = parse_year_month(year_month)
        close = MonthlyClose.objects.filter(
            business=params["business"], year=year, month=month, status=MonthlyClose.Status.CLOSED
        ).first()
        try:
            data = close.snapshot if close else MonthlyCloseService.build_summary(
                business=params["business"], year=year, month=month
            )
        except UnsupportedTaxType as exc:
            return error_response(code="UNSUPPORTED_TAX_TYPE", message=str(exc), status=422)
        return success_response(
            code="MONTHLY_CLOSE_DETAIL_SUCCESS",
            message="월 마감 요약을 조회했습니다.",
            data=data,
        )


class MonthlyCloseApproveView(APIView):
    def post(self, request, year_month):
        query = BusinessPeriodQuerySerializer(
            data={"business_id": request.data.get("business_id"), "year_month": year_month}
        )
        if not query.is_valid():
            return _invalid_query(query, "INVALID_YEAR_MONTH")
        params = query.validated_data
        owner_err = _check_tax_business_owner(request, params["business"])
        if owner_err:
            return owner_err

        year, month = parse_year_month(year_month)
        try:
            data = MonthlyCloseService.approve(
                business=params["business"], year=year, month=month
            )
        except MonthAlreadyClosed:
            return error_response(
                code="MONTH_ALREADY_CLOSED",
                message="이미 마감된 월입니다.",
                status=409,
            )
        except UnconfirmedTransactionsExist:
            return error_response(
                code="UNCONFIRMED_TRANSACTIONS_EXIST",
                message="공제 여부가 확정되지 않은 거래가 남아 있습니다.",
                status=422,
            )
        except UnsupportedTaxType as exc:
            return error_response(code="UNSUPPORTED_TAX_TYPE", message=str(exc), status=422)
        return success_response(
            code="MONTHLY_CLOSE_APPROVED",
            message="월 마감을 승인했습니다.",
            data=data,
        )


class MonthlyCloseReopenView(APIView):
    """마감 기록을 제거해 해당 월의 분류와 공제 검토를 다시 허용한다."""

    def post(self, request, year_month):
        query = BusinessPeriodQuerySerializer(
            data={"business_id": request.data.get("business_id"), "year_month": year_month}
        )
        if not query.is_valid():
            return _invalid_query(query, "INVALID_YEAR_MONTH")
        params = query.validated_data
        owner_err = _check_tax_business_owner(request, params["business"])
        if owner_err:
            return owner_err

        year, month = parse_year_month(year_month)
        MonthlyClose.objects.filter(
            business=params["business"], year=year, month=month
        ).delete()
        return success_response(
            code="MONTHLY_CLOSE_REOPENED",
            message="월 마감을 해제(재오픈)했습니다. 지출 내역을 다시 검토할 수 있습니다.",
            data={"business_id": params["business"].id, "year_month": year_month, "is_closed": False},
        )

