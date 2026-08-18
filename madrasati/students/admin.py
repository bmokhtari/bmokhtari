from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from finance.models import Payment
from .models import Attendance, Enrollment, Grade, Guardian, Student


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


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ["student", "school_class", "status", "tuition_plan",
                    "discount_pct", "date"]
    list_filter = ["status", "school_class__academic_year",
                   "school_class__level"]
    search_fields = ["student__last_name", "student__first_name",
                     "student__massar_code"]
    autocomplete_fields = ["student", "school_class", "tuition_plan"]
    inlines = [PaymentInline]


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
