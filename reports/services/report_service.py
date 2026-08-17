from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.utils import timezone

from businesses.models import Business
from reports.exceptions import (
    BusinessNotFound,
    InvalidReportFileType,
    InvalidReportPeriod,
    MonthlyCloseRequired,
    ReportFileNotReady,
    ReportNotApproved,
    ReportNotFound,
    TaxAccountantEmailNotSet,
)
from reports.models import Report
from tax.models import MonthlyClose
from tax.services.periods import InvalidYearMonth, parse_year_month

from .report_csv_service import generate_report_csv
from .report_pdf_service import generate_report_pdf


def _get_business(business_id):
    try:
        return Business.objects.get(id=business_id)
    except Business.DoesNotExist:
        raise BusinessNotFound()


def _validate_year_month(year_month):
    try:
        return parse_year_month(year_month)
    except InvalidYearMonth as exc:
        raise InvalidReportPeriod() from exc


def get_report(business_id, year_month):
    _validate_year_month(year_month)
    business = _get_business(business_id)
    try:
        return Report.objects.select_related("business").get(
            business=business, year_month=year_month
        )
    except Report.DoesNotExist:
        raise ReportNotFound()


def generate_report(business_id, year_month):
    business = _get_business(business_id)
    year, month = _validate_year_month(year_month)
    if not MonthlyClose.objects.filter(
        business=business,
        year=year,
        month=month,
        status=MonthlyClose.Status.CLOSED,
    ).exists():
        raise MonthlyCloseRequired()

    report, _ = Report.objects.update_or_create(
        business=business,
        year_month=year_month,
        defaults={"status": "generated", "approved_at": None, "sent_at": None},
    )

    if report.csv_file:
        report.csv_file.delete(save=False)
    if report.pdf_file:
        report.pdf_file.delete(save=False)

    report.csv_file.save(
        f"{year_month}.csv",
        ContentFile(generate_report_csv(business, year_month).encode("utf-8-sig")),
        save=False,
    )
    report.pdf_file.save(
        f"{year_month}.pdf",
        ContentFile(generate_report_pdf(business, year_month)),
        save=False,
    )
    report.save()
    return report


def get_report_file(business_id, year_month, file_type):
    if file_type not in {"csv", "pdf"}:
        raise InvalidReportFileType()
    report = get_report(business_id, year_month)
    file_field = report.csv_file if file_type == "csv" else report.pdf_file
    if not file_field:
        raise ReportFileNotReady()
    return file_field


def approve_report(business_id, year_month):
    report = get_report(business_id, year_month)
    report.status = "approved"
    report.approved_at = timezone.now()
    report.save()
    return report


def send_report_email(business_id, year_month):
    report = get_report(business_id, year_month)
    business = report.business

    if report.status != "approved":
        raise ReportNotApproved()
    if not business.tax_accountant_email:
        raise TaxAccountantEmailNotSet()

    email = EmailMessage(
        subject=f"[카페비서] {year_month} 세무 자료 전달",
        body=f"{business.business_name}의 {year_month} 세무사 전달용 자료입니다.",
        to=[business.tax_accountant_email],
    )
    if report.csv_file:
        email.attach_file(report.csv_file.path)
    if report.pdf_file:
        email.attach_file(report.pdf_file.path)
    email.send()

    report.sent_at = timezone.now()
    report.save()
    return report
