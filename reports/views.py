from django.shortcuts import get_object_or_404
from businesses.models import Business
from .models import Report
from .serializers import ReportSerializer


def get_current_business():
    return get_object_or_404(Business, pk=1)


class ReportDetailView(APIView):
    def get(self, request, year_month):
        business = get_current_business()
        report = get_object_or_404(Report, business=business, year_month=year_month)
        return Response(ReportSerializer(report).data)


class ReportGenerateView(APIView):
    def post(self, request, year_month):
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)


class ReportDownloadView(APIView):
    def get(self, request, year_month):
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)


class ReportApproveView(APIView):
    def post(self, request, year_month):
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)


class ReportSendEmailView(APIView):
    def post(self, request, year_month):
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)