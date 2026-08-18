from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _, ngettext

from finance.models import DiscountRequest, Payment, overdue_months, overdue_total
from .models import (Attendance, BehaviourRecord, Enrollment, Grade, Guardian,
                     Student)


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0
    autocomplete_fields = ["school_class", "tuition_plan"]


@admin.register(Guardian)
class GuardianAdmin(admin.ModelAdmin):
    list_display = ["last_name", "first_name", "relationship", "phone", "cin"]
    list_filter = ["relationship"]
    search_fields = ["last_name", "first_name", "phone", "cin"]


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ["last_name", "first_name", "age", "gender",
                    "massar_code", "current_class", "city", "is_active"]
    list_filter = ["is_active", "gender", "city",
                   "enrollments__school_class__level"]
    search_fields = ["last_name", "first_name", "last_name_ar",
                     "first_name_ar", "massar_code"]
    filter_horizontal = ["guardians"]
    inlines = [EnrollmentInline]
    fieldsets = [
        (_("État civil"), {"fields": [
            ("first_name", "last_name"),
            ("first_name_ar", "last_name_ar"),
            ("gender", "birth_date", "birth_place"),
        ]}),
        (_("Identifiants officiels"), {"fields": ["massar_code"]}),
        (_("Coordonnées"), {"fields": ["address", "city", "phone", "guardians"]}),
        (_("Dossier scolaire"), {"fields": [
            "previous_school", "medical_notes", "registered_on", "is_active",
        ]}),
    ]

    @admin.display(description=_("âge"))
    def age(self, obj):
        return obj.age

    @admin.display(description=_("classe actuelle"))
    def current_class(self, obj):
        enrollment = obj.current_enrollment()
        if enrollment:
            cls = enrollment.school_class
            return f"{cls.level.code} - {cls.name}"
        return "—"


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ["kind", "month", "amount", "method", "date", "receipt_number"]
    readonly_fields = ["receipt_number"]


class BehaviourInline(admin.TabularInline):
    model = BehaviourRecord
    extra = 0
    fields = ["date", "kind", "summary", "subject", "reported_by",
              "follow_up", "guardians_informed"]
    autocomplete_fields = ["subject", "reported_by"]


class DiscountRequestInline(admin.TabularInline):
    model = DiscountRequest
    extra = 0
    fields = ["percentage", "scope", "start_month", "end_month", "reason",
              "status", "decided_by"]
    readonly_fields = ["status", "decided_by"]
    verbose_name = _("demande de remise")
    verbose_name_plural = _("demandes de remise")


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ["student", "school_class", "status", "payment_state",
                    "discount_pct", "certificate_link", "date"]
    list_filter = ["status", "school_class__academic_year",
                   "school_class__level"]
    search_fields = ["student__last_name", "student__first_name",
                     "student__massar_code"]
    autocomplete_fields = ["student", "school_class", "tuition_plan"]
    inlines = [DiscountRequestInline, PaymentInline, BehaviourInline]

    def get_queryset(self, request):
        # Le statut de scolarité de chaque ligne se calcule à partir des
        # paiements et des remises : on les précharge pour éviter une
        # cascade de requêtes.
        return (super().get_queryset(request)
                .select_related("student", "tuition_plan",
                                "school_class__level",
                                "school_class__academic_year")
                .prefetch_related("payments", "discount_requests"))

    @admin.display(description=_("scolarité"))
    def payment_state(self, obj):
        unpaid = overdue_months(obj)
        if not unpaid:
            return format_html(
                '<span class="m-status" style="background:#E6F0EA;color:#14573D">{}</span>',
                _("À jour"))
        label = ngettext("%d mois dû", "%d mois dus", len(unpaid)) % len(unpaid)
        return format_html(
            '<span class="m-status" style="background:#F7EAE3;color:#9C4426">{}</span>',
            label)

    @admin.display(description=_("attestation"))
    def certificate_link(self, obj):
        url = reverse("enrollment-certificate", args=[obj.pk])
        return format_html('<a class="m-print" href="{}" target="_blank">{}</a>',
                           url, _("Attestation"))


@admin.register(BehaviourRecord)
class BehaviourRecordAdmin(admin.ModelAdmin):
    """Vie scolaire : faits marquants, positifs comme négatifs."""

    list_display = ["date", "student_name", "school_class", "kind_badge",
                    "summary", "reported_by", "guardians_informed"]
    list_filter = ["kind", "guardians_informed", "date",
                   "enrollment__school_class__level"]
    search_fields = ["enrollment__student__last_name",
                     "enrollment__student__first_name", "summary", "details"]
    autocomplete_fields = ["enrollment", "subject", "reported_by"]
    date_hierarchy = "date"
    list_editable = ["guardians_informed"]
    fieldsets = [
        (_("Fait"), {"fields": ["enrollment", "date", "kind", "summary",
                                "details", "subject"]}),
        (_("Suivi"), {"fields": ["reported_by", "follow_up",
                                 "guardians_informed"]}),
    ]

    def get_queryset(self, request):
        return (super().get_queryset(request)
                .select_related("enrollment__student",
                                "enrollment__school_class__level",
                                "reported_by"))

    @admin.display(description=_("élève"),
                   ordering="enrollment__student__last_name")
    def student_name(self, obj):
        return str(obj.enrollment.student)

    @admin.display(description=_("classe"))
    def school_class(self, obj):
        school_class = obj.enrollment.school_class
        return f"{school_class.level.code} - {school_class.name}"

    @admin.display(description=_("nature"), ordering="kind")
    def kind_badge(self, obj):
        background, colour = (("#F7EAE3", "#9C4426") if obj.is_negative
                              else ("#E6F0EA", "#14573D"))
        return format_html(
            '<span class="m-status" style="background:{};color:{}">{}</span>',
            background, colour, obj.get_kind_display())


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ["enrollment", "date", "kind", "justified", "note"]
    list_filter = ["kind", "justified", "date"]
    search_fields = ["enrollment__student__last_name",
                     "enrollment__student__first_name"]
    autocomplete_fields = ["enrollment"]


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ["enrollment", "subject", "term", "label", "score", "date"]
    list_filter = ["term", "subject"]
    search_fields = ["enrollment__student__last_name",
                     "enrollment__student__first_name"]
    autocomplete_fields = ["enrollment", "subject"]
