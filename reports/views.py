from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from businesses.models import Business
from .models import Report
from .serializers import ReportSerializer
from .services import generate_csv, generate_pdf


def get_current_business():
    return get_object_or_404(Business, pk=1)


class ReportDetailView(APIView):
    def get(self, request, year_month):
        business = get_current_business()
        report = get_object_or_404(Report, business=business, year_month=year_month)
        return Response(ReportSerializer(report).data)


class ReportGenerateView(APIView):
    def post(self, request, year_month):
        business = get_current_business()

        report, _ = Report.objects.update_or_create(
            business=business,
            year_month=year_month,
            defaults={"status": "generated", "approved_at": None},
        )

        if report.csv_file:
            report.csv_file.delete(save=False)
        if report.pdf_file:
            report.pdf_file.delete(save=False)

        report.csv_file.save(f"{year_month}.csv", ContentFile(generate_csv(business, year_month).encode("utf-8")), save=False)
        report.pdf_file.save(f"{year_month}.pdf", ContentFile(generate_pdf(business, year_month)), save=False)
        report.save()

        return Response(ReportSerializer(report).data)


class ReportDownloadView(APIView):
    def get(self, request, year_month):
        business = get_current_business()
        report = get_object_or_404(Report, business=business, year_month=year_month)

        fmt = request.query_params.get("type", "pdf")
        file_field = report.csv_file if fmt == "csv" else report.pdf_file
        if not file_field:
            return Response({"detail": "아직 생성된 파일이 없습니다."}, status=400)

        return FileResponse(file_field.open("rb"), as_attachment=True, filename=file_field.name.split("/")[-1])


class ReportApproveView(APIView):
    def post(self, request, year_month):
        business = get_current_business()
        report = get_object_or_404(Report, business=business, year_month=year_month)

        report.status = "approved"
        report.approved_at = timezone.now()
        report.save()

        return Response(ReportSerializer(report).data)


class ReportSendEmailView(APIView):
    def post(self, request, year_month):
        business = get_current_business()
        report = get_object_or_404(Report, business=business, year_month=year_month)

        if report.status != "approved":
            return Response({"detail": "승인된 리포트만 전송할 수 있습니다."}, status=400)
        if not business.tax_accountant_email:
            return Response({"detail": "세무사 이메일이 등록되어 있지 않습니다."}, status=400)

        email = EmailMessage(
            subject=f"[카페비서] {year_month} 세무 자료 전달",
            body=f"{business.name}의 {year_month} 세무사 전달용 자료입니다.",
            to=[business.tax_accountant_email],
        )
        if report.csv_file:
            email.attach_file(report.csv_file.path)
        if report.pdf_file:
            email.attach_file(report.pdf_file.path)
        email.send()

        report.sent_at = timezone.now()
        report.save()

        return Response(ReportSerializer(report).data)