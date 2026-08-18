from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .models import Payment, TuitionPlan


@admin.register(TuitionPlan)
class TuitionPlanAdmin(admin.ModelAdmin):
    list_display = ["level", "academic_year", "registration_fee",
                    "monthly_fee", "insurance_fee", "months_count",
                    "annual_total"]
    list_filter = ["academic_year", "level__cycle"]
    search_fields = ["level__code", "level__name_fr"]

    @admin.display(description=_("total annuel (DH)"))
    def annual_total(self, obj):
        return obj.annual_total


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["receipt_number", "student_name", "kind", "month",
                    "amount", "method", "date", "receipt_link"]
    list_filter = ["kind", "method", "date", "month",
                   "enrollment__school_class__academic_year"]
    search_fields = ["receipt_number", "reference",
                     "enrollment__student__last_name",
                     "enrollment__student__first_name"]
    autocomplete_fields = ["enrollment"]
    readonly_fields = ["receipt_number", "received_by"]
    date_hierarchy = "date"

    @admin.display(description=_("élève"), ordering="enrollment__student__last_name")
    def student_name(self, obj):
        return str(obj.enrollment.student)

    @admin.display(description=_("reçu"))
    def receipt_link(self, obj):
        url = reverse("payment-receipt", args=[obj.pk])
        return format_html('<a href="{}" target="_blank">🖨 {}</a>', url,
                           _("Imprimer"))

    def save_model(self, request, obj, form, change):
        if not change and not obj.received_by:
            obj.received_by = request.user
        super().save_model(request, obj, form, change)
