"""Données du tableau de bord de l'interface de gestion."""

from decimal import Decimal

from django import template
from django.db.models import Count, Sum
from django.db.models.functions import ExtractMonth
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import AcademicYear, SchoolClass
from finance.models import (SCHOOL_MONTHS, DiscountRequest, Payment,
                            overdue_months, overdue_total)
from hr.models import Employee, PayrollRun
from students.models import Enrollment, Student

register = template.Library()

# Ordre des mois de l'année scolaire marocaine (septembre → juin).
YEAR_MONTHS = [m for m, _label in SCHOOL_MONTHS][:10]
MONTH_SHORT = {
    9: _("Sep"), 10: _("Oct"), 11: _("Nov"), 12: _("Déc"), 1: _("Jan"),
    2: _("Fév"), 3: _("Mar"), 4: _("Avr"), 5: _("Mai"), 6: _("Juin"),
    7: _("Juil"),
}


def _revenue_series(year, today):
    """Encaissements par mois de l'année scolaire, prêts à tracer."""
    if year is None:
        return [], Decimal("0")

    totals = dict(
        Payment.objects
        .filter(date__gte=year.start_date, date__lte=year.end_date)
        .annotate(m=ExtractMonth("date"))
        .values_list("m")
        .annotate(total=Sum("amount"))
    )
    peak = max(totals.values(), default=Decimal("0")) or Decimal("1")

    series = []
    for month in YEAR_MONTHS:
        amount = totals.get(month) or Decimal("0")
        series.append({
            "month": month,
            "label": MONTH_SHORT[month],
            "amount": amount,
            # Hauteur en pourcentage de la plus forte recette. Chaîne
            # formatée en Python : un flottant serait localisé par le
            # gabarit (« 100,0% ») et invalide en CSS.
            "pct": f"{float(amount) / float(peak) * 100:.1f}",
            "is_current": month == today.month,
        })
    return series, sum((t for t in totals.values()), Decimal("0"))


def _late_enrollments(year, today, limit=5):
    """Élèves dont des mensualités échues restent dues."""
    if year is None:
        return []

    enrollments = (Enrollment.objects
                   .filter(status=Enrollment.Status.ACTIVE,
                           school_class__academic_year=year,
                           tuition_plan__isnull=False)
                   .select_related("student", "tuition_plan",
                                   "school_class__level",
                                   "school_class__academic_year")
                   .prefetch_related("payments", "discount_requests"))

    late = []
    for enrollment in enrollments:
        missing = overdue_months(enrollment, today)
        if missing:
            late.append({
                "enrollment": enrollment,
                "student": enrollment.student,
                "school_class": enrollment.school_class,
                "months": len(missing),
                "amount": overdue_total(enrollment, today),
            })

    late.sort(key=lambda row: (-row["months"], row["student"].last_name))
    return late[:limit]


@register.inclusion_tag("admin/dashboard_stats.html")
def dashboard_stats():
    year = AcademicYear.current()
    today = timezone.localdate()

    enrollments = Enrollment.objects.filter(status=Enrollment.Status.ACTIVE)
    if year:
        enrollments = enrollments.filter(school_class__academic_year=year)

    month_revenue = (Payment.objects
                     .filter(date__year=today.year, date__month=today.month)
                     .aggregate(t=Sum("amount"))["t"] or Decimal("0"))

    last_run = PayrollRun.objects.order_by("-year", "-month").first()
    series, year_revenue = _revenue_series(year, today)
    collected = [point for point in series if point["amount"]]
    best = max(collected, key=lambda point: point["amount"], default=None)

    return {
        "academic_year": year,
        "today": today,
        "student_count": Student.objects.filter(is_active=True).count(),
        "enrollment_count": enrollments.count(),
        "class_count": (SchoolClass.objects.filter(academic_year=year).count()
                        if year else SchoolClass.objects.count()),
        "employee_count": Employee.objects.filter(is_active=True).count(),
        "month_revenue": month_revenue,
        "year_revenue": year_revenue,
        "revenue_series": series,
        "revenue_average": (year_revenue / len(collected)) if collected else Decimal("0"),
        "revenue_best": best,
        "last_payroll": last_run,
        "last_payroll_net": last_run.total_net if last_run else 0,
        "late_rows": _late_enrollments(year, today),
        "pending_discounts": DiscountRequest.objects.filter(
            status=DiscountRequest.Status.PENDING).count(),
        "recent_payments": (Payment.objects
                            .select_related("enrollment__student")
                            .order_by("-date", "-id")[:5]),
    }
