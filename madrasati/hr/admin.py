from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _, ngettext

from .models import Employee, Payslip, PayrollRun


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ["matricule", "last_name", "first_name", "role",
                    "base_salary", "allowances", "gross_salary_display",
                    "dependents", "is_active"]
    list_filter = ["role", "is_active"]
    search_fields = ["matricule", "last_name", "first_name", "cin",
                     "last_name_ar", "first_name_ar"]
    filter_horizontal = ["subjects"]
    fieldsets = [
        (_("Identité"), {"fields": [
            "matricule",
            ("first_name", "last_name"),
            ("first_name_ar", "last_name_ar"),
            ("cin", "cnss_number"),
        ]}),
        (_("Poste"), {"fields": ["role", "subjects", "hire_date", "is_active"]}),
        (_("Coordonnées"), {"fields": ["phone", "email", "address"]}),
        (_("Rémunération"), {"fields": [
            ("base_salary", "allowances"), "dependents", "rib",
        ]}),
    ]

    @admin.display(description=_("salaire brut (DH)"))
    def gross_salary_display(self, obj):
        return obj.gross_salary


class PayslipInline(admin.TabularInline):
    model = Payslip
    extra = 0
    can_delete = False
    fields = ["employee", "gross", "cnss", "amo", "ir", "net",
              "employer_cost", "payslip_link"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description=_("bulletin"))
    def payslip_link(self, obj):
        if not obj.pk:
            return ""
        url = reverse("payslip", args=[obj.pk])
        return format_html('<a href="{}" target="_blank">🖨 {}</a>', url,
                           _("Imprimer"))


@admin.register(PayrollRun)
class PayrollRunAdmin(admin.ModelAdmin):
    list_display = ["__str__", "status", "payslip_count", "total_net_display",
                    "total_cost_display", "created_on"]
    list_filter = ["status", "year"]
    inlines = [PayslipInline]
    actions = ["generate_payslips_action", "validate_action", "mark_paid_action"]

    @admin.display(description=_("bulletins"))
    def payslip_count(self, obj):
        return obj.payslips.count()

    @admin.display(description=_("total net (DH)"))
    def total_net_display(self, obj):
        return obj.total_net

    @admin.display(description=_("coût employeur (DH)"))
    def total_cost_display(self, obj):
        return obj.total_employer_cost

    @admin.action(description=_("Générer les bulletins de paie"))
    def generate_payslips_action(self, request, queryset):
        total = 0
        skipped = 0
        for run in queryset:
            if run.status != PayrollRun.Status.DRAFT:
                skipped += 1
                continue
            total += run.generate_payslips()
        if total:
            self.message_user(request, ngettext(
                "%d bulletin généré.", "%d bulletins générés.", total) % total,
                messages.SUCCESS)
        if skipped:
            self.message_user(
                request,
                _("Les cycles validés ou payés n'ont pas été modifiés."),
                messages.WARNING)

    @admin.action(description=_("Valider les cycles sélectionnés"))
    def validate_action(self, request, queryset):
        updated = queryset.filter(status=PayrollRun.Status.DRAFT).update(
            status=PayrollRun.Status.VALIDATED)
        self.message_user(request, _("%d cycle(s) validé(s).") % updated,
                          messages.SUCCESS)

    @admin.action(description=_("Marquer comme payés"))
    def mark_paid_action(self, request, queryset):
        updated = queryset.filter(status=PayrollRun.Status.VALIDATED).update(
            status=PayrollRun.Status.PAID)
        self.message_user(request, _("%d cycle(s) marqué(s) payé(s).") % updated,
                          messages.SUCCESS)


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ["employee", "payroll_run", "gross", "cnss", "amo",
                    "ir", "net", "print_link"]
    list_filter = ["payroll_run"]
    search_fields = ["employee__last_name", "employee__first_name",
                     "employee__matricule"]
    readonly_fields = [f.name for f in Payslip._meta.fields if f.name != "id"]

    def has_add_permission(self, request):
        # Les bulletins sont générés depuis les cycles de paie.
        return False

    @admin.display(description=_("bulletin"))
    def print_link(self, obj):
        url = reverse("payslip", args=[obj.pk])
        return format_html('<a href="{}" target="_blank">🖨 {}</a>', url,
                           _("Imprimer"))
