from django.contrib import admin, messages
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _, ngettext

from .models import DiscountRequest, FeeLine, Payment, TuitionPlan

APPROVE_PERM = "finance.approve_discountrequest"


class FeeLineInline(admin.TabularInline):
    model = FeeLine
    extra = 0
    fields = ["kind", "label", "amount", "mandatory", "due_month"]


@admin.register(TuitionPlan)
class TuitionPlanAdmin(admin.ModelAdmin):
    list_display = ["level", "school", "academic_year", "billing_badge",
                    "tuition_display", "extras_display", "annual_total"]
    list_filter = ["school", "billing", "academic_year", "level__cycle"]
    search_fields = ["level__code", "level__name_fr", "school__name"]
    inlines = [FeeLineInline]
    change_form_template = "admin/finance/tuitionplan/change_form.html"
    fieldsets = [
        (_("Formule"), {"fields": ["school", "academic_year", "level",
                                   "billing"]}),
        (_("Enseignement général — facturation mensuelle"), {
            "classes": ["m-billing", "m-billing-monthly"],
            "fields": ["monthly_fee", "months_count", "registration_fee",
                       "insurance_fee"],
            "description": _("Mensualité réglée sur les dix mois de l'année "
                             "scolaire (septembre → juin)."),
        }),
        (_("Formation professionnelle — facturation annuelle"), {
            "classes": ["m-billing", "m-billing-annual"],
            "fields": ["annual_fee"],
            "description": _("Montant global de l'année, frais d'inscription "
                             "compris. Les frais à échéance propre (diplôme…) "
                             "se saisissent en frais annexes."),
        }),
        (_("Remise"), {"fields": ["cash_discount_pct"]}),
    ]

    @admin.display(description=_("facturation"), ordering="billing")
    def billing_badge(self, obj):
        """Libellé court : le texte complet du choix étirait la colonne."""
        annual = obj.billing == TuitionPlan.Billing.ANNUAL
        background, colour = (("#EFE7D8", "#4A5A52") if annual
                              else ("#E6F0EA", "#14573D"))
        label = _("Annuelle") if annual else _("Mensuelle")
        return format_html(
            '<span class="m-status" style="background:{};color:{}">{}</span>',
            background, colour, label)

    @admin.display(description=_("scolarité"))
    def tuition_display(self, obj):
        if obj.billing == TuitionPlan.Billing.ANNUAL:
            return _("%(amount)s DH / an") % {"amount": obj.annual_fee}
        return _("%(amount)s DH / mois") % {"amount": obj.monthly_fee}

    @admin.display(description=_("frais annexes"))
    def extras_display(self, obj):
        lines = list(obj.lines.all())
        if not lines:
            return "—"
        total = sum(line.amount for line in lines if line.mandatory)
        return _("%(count)d ligne(s) · %(total)s DH") % {
            "count": len(lines), "total": total}

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


@admin.register(DiscountRequest)
class DiscountRequestAdmin(admin.ModelAdmin):
    """Demandes de remise : saisie libre, mais décision réservée.

    Le statut n'est pas modifiable dans le formulaire : il ne change que par
    les actions « Approuver » / « Refuser », réservées aux comptes portant
    la permission « Peut approuver ou refuser une demande de remise ».
    """

    list_display = ["student_name", "school_class", "percentage",
                    "period", "status_badge", "requested_by", "requested_on",
                    "decided_by"]
    list_filter = ["status", "scope", "enrollment__school_class__academic_year"]
    search_fields = ["enrollment__student__last_name",
                     "enrollment__student__first_name",
                     "enrollment__student__massar_code", "reason"]
    autocomplete_fields = ["enrollment"]
    date_hierarchy = "requested_on"
    actions = ["approve_selected", "reject_selected"]
    fieldsets = [
        (_("Demande"), {"fields": [
            "enrollment", "percentage",
            ("scope", "start_month", "end_month"),
            "reason",
        ]}),
        (_("Décision"), {"fields": [
            "status_display", "decision_note", "requested_by", "requested_on",
            "decided_by", "decided_on",
        ]}),
    ]

    @admin.display(description=_("élève"),
                   ordering="enrollment__student__last_name")
    def student_name(self, obj):
        return str(obj.enrollment.student)

    @admin.display(description=_("classe"))
    def school_class(self, obj):
        school_class = obj.enrollment.school_class
        return f"{school_class.level.code} - {school_class.name}"

    @admin.display(description=_("période"))
    def period(self, obj):
        return obj.period_display

    @admin.display(description=_("statut"), ordering="status")
    def status_badge(self, obj):
        colours = {
            DiscountRequest.Status.PENDING: ("#FBF0D8", "#7A5A16"),
            DiscountRequest.Status.APPROVED: ("#E6F0EA", "#14573D"),
            DiscountRequest.Status.REJECTED: ("#F7EAE3", "#9C4426"),
        }
        background, colour = colours[obj.status]
        return format_html(
            '<span class="m-status" style="background:{};color:{}">{}</span>',
            background, colour, obj.get_status_display())

    @admin.display(description=_("statut"))
    def status_display(self, obj):
        return self.status_badge(obj) if obj and obj.pk else "—"

    def get_readonly_fields(self, request, obj=None):
        readonly = ["status_display", "requested_by", "requested_on",
                    "decided_by", "decided_on"]
        if obj and obj.status != DiscountRequest.Status.PENDING:
            # Une demande tranchée n'est plus modifiable : sa décision a déjà
            # produit ses effets sur les mensualités.
            readonly += ["enrollment", "percentage", "scope", "start_month",
                         "end_month", "reason", "decision_note"]
        elif not request.user.has_perm(APPROVE_PERM):
            readonly += ["decision_note"]
        return readonly

    def save_model(self, request, obj, form, change):
        if not change and not obj.requested_by:
            obj.requested_by = request.user
        super().save_model(request, obj, form, change)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not request.user.has_perm(APPROVE_PERM):
            actions.pop("approve_selected", None)
            actions.pop("reject_selected", None)
        return actions

    def _decide(self, request, queryset, status, label):
        if not request.user.has_perm(APPROVE_PERM):
            self.message_user(
                request,
                _("Vous n'avez pas la permission de trancher les demandes de remise."),
                messages.ERROR)
            return
        pending = queryset.filter(status=DiscountRequest.Status.PENDING)
        decided = 0
        for discount_request in pending:
            discount_request.decide(status, request.user)
            decided += 1
        skipped = queryset.count() - decided
        if decided:
            self.message_user(request, ngettext(
                "%(count)d demande %(label)s.",
                "%(count)d demandes %(label)s.", decided)
                % {"count": decided, "label": label}, messages.SUCCESS)
        if skipped:
            self.message_user(
                request,
                _("Les demandes déjà tranchées ont été ignorées."),
                messages.WARNING)

    @admin.action(description=_("Approuver les demandes sélectionnées"))
    def approve_selected(self, request, queryset):
        self._decide(request, queryset, DiscountRequest.Status.APPROVED,
                     _("approuvée(s)"))

    @admin.action(description=_("Refuser les demandes sélectionnées"))
    def reject_selected(self, request, queryset):
        self._decide(request, queryset, DiscountRequest.Status.REJECTED,
                     _("refusée(s)"))
