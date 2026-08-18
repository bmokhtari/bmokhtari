from django import template
from django.db.models import Sum
from django.utils import timezone

from core.models import AcademicYear, SchoolClass
from finance.models import Payment
from hr.models import Employee, PayrollRun
from students.models import Enrollment, Student

register = template.Library()


@register.inclusion_tag("admin/dashboard_stats.html")
def dashboard_stats():
    year = AcademicYear.current()
    today = timezone.localdate()

    enrollments = Enrollment.objects.filter(status=Enrollment.Status.ACTIVE)
    payments_month = Payment.objects.filter(date__year=today.year,
                                            date__month=today.month)
    if year:
        enrollments = enrollments.filter(school_class__academic_year=year)

    last_run = PayrollRun.objects.order_by("-year", "-month").first()

    return {
        "academic_year": year,
        "student_count": Student.objects.filter(is_active=True).count(),
        "enrollment_count": enrollments.count(),
        "class_count": (SchoolClass.objects.filter(academic_year=year).count()
                        if year else SchoolClass.objects.count()),
        "employee_count": Employee.objects.filter(is_active=True).count(),
        "month_revenue": payments_month.aggregate(t=Sum("amount"))["t"] or 0,
        "last_payroll": last_run,
        "last_payroll_net": last_run.total_net if last_run else 0,
    }
