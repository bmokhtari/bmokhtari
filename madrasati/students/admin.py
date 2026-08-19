from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _, ngettext

from finance.models import SCHOOL_MONTHS, DiscountRequest, FeeLine, Payment
from finance.schedule import (balance_due, due_entries, fee_schedule,
                              overdue_entries, paid_total,
                              schedule_total)
from core.templatetags.madrasati import dirhams
from .models import (Attendance, BehaviourRecord, BehaviourType, Enrollment,
                     Grade, Guardian, Student)


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
    fields = ["date", "type", "summary", "subject", "reported_by",
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
    filter_horizontal = ["optional_fees"]
    inlines = [DiscountRequestInline, PaymentInline, BehaviourInline]
    readonly_fields = ["schedule_table"]
    fieldsets = [
        (_("Inscription"), {"fields": ["student", "school_class", "date",
                                       "status"]}),
        (_("Scolarité"), {"fields": ["tuition_plan", "payment_plan",
                                     "discount_pct", "optional_fees"]}),
        (_("Échéancier"), {"fields": ["schedule_table"]}),
    ]

    def get_form(self, request, obj=None, **kwargs):
        # Mémorise l'inscription pour restreindre les frais optionnels.
        request._enrollment = obj
        return super().get_form(request, obj, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """Ne proposer que les frais optionnels de la formule de l'élève.

        Sans ce filtre, la liste D de toutes les formules du groupe
        apparaissait, la même ligne se répétant pour chaque établissement.
        """
        if db_field.name == "optional_fees":
            enrollment = getattr(request, "_enrollment", None)
            plan = enrollment.tuition_plan if enrollment else None
            kwargs["queryset"] = (FeeLine.objects.filter(plan=plan,
                                                         mandatory=False)
                                  if plan else FeeLine.objects.none())
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    @admin.display(description=_("échéancier de l'année"))
    def schedule_table(self, obj):
        """Ce que la famille doit, échéance par échéance, et où elle en est."""
        if not obj or not obj.pk or obj.tuition_plan is None:
            return _("Choisissez une formule de frais pour voir l'échéancier.")

        schedule = fee_schedule(obj)
        if not schedule:
            return "—"

        # Trois états distincts : à venir, réglée, ou partiellement due.
        # Sans le premier, une échéance non encore exigible s'affichait
        # comme « réglée ».
        due = {(entry["month"], entry["label"]) for entry in due_entries(obj)}
        unpaid = {(entry["month"], entry["label"]): entry["remaining"]
                  for entry in overdue_entries(obj)}
        months = dict(SCHOOL_MONTHS)
        rows = []
        for entry in schedule:
            key = (entry["month"], entry["label"])
            if key not in due:
                state = format_html(
                    '<span class="m-status" style="background:#EFE7D8;'
                    'color:#4A5A52">{}</span>', _("À venir"))
            elif key in unpaid:
                state = format_html(
                    '<span class="m-status" style="background:#F7EAE3;'
                    'color:#9C4426">{}</span>',
                    _("Reste %(amount)s DH") % {"amount": unpaid[key]})
            else:
                state = format_html(
                    '<span class="m-status" style="background:#E6F0EA;'
                    'color:#14573D">{}</span>', _("Réglée"))
            month_label = months.get(entry["month"], entry["month"])
            # Pour une mensualité, l'intitulé répète le mois : on l'omet
            # plutôt que d'afficher deux fois « Octobre ».
            detail = ("" if str(entry["label"]) == str(month_label)
                      else entry["label"])
            rows.append(format_html(
                "<tr><td>{}</td><td>{}</td>"
                "<td class='m-money' style='text-align:end'>{}</td>"
                "<td>{}</td></tr>",
                month_label, detail, dirhams(entry["amount"], 2), state))

        return format_html(
            '<table class="m-schedule"><thead><tr><th>{}</th><th>{}</th>'
            '<th style="text-align:end">{}</th><th>{}</th></tr></thead>'
            "<tbody>{}</tbody><tfoot><tr><td colspan='2'>{}</td>"
            "<td style='text-align:end'>{}</td><td>{}</td></tr></tfoot></table>",
            _("Mois"), _("Échéance"), _("Montant (DH)"), _("État"),
            format_html("".join(rows)),
            _("Total annuel"), dirhams(schedule_total(obj), 2),
            _("Versé : %(paid)s DH · reste dû à ce jour : %(due)s DH") % {
                "paid": dirhams(paid_total(obj), 2),
                "due": dirhams(balance_due(obj), 2)})

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
    list_filter = ["type", "guardians_informed", "date",
                   "enrollment__school_class__level"]
    search_fields = ["enrollment__student__last_name",
                     "enrollment__student__first_name", "summary", "details"]
    autocomplete_fields = ["enrollment", "subject", "reported_by"]
    date_hierarchy = "date"
    list_editable = ["guardians_informed"]
    fieldsets = [
        (_("Fait"), {"fields": ["enrollment", "date", "type", "summary",
                                "details", "subject"]}),
        (_("Suivi"), {"fields": ["reported_by", "follow_up",
                                 "guardians_informed"]}),
    ]

    def get_queryset(self, request):
        return (super().get_queryset(request)
                .select_related("enrollment__student",
                                "enrollment__school_class__level",
                                "reported_by", "type"))

    @admin.display(description=_("élève"),
                   ordering="enrollment__student__last_name")
    def student_name(self, obj):
        return str(obj.enrollment.student)

    @admin.display(description=_("classe"))
    def school_class(self, obj):
        school_class = obj.enrollment.school_class
        return f"{school_class.level.code} - {school_class.name}"

    @admin.display(description=_("nature"), ordering="type__name")
    def kind_badge(self, obj):
        background, colour = (("#F7EAE3", "#9C4426") if obj.is_negative
                              else ("#E6F0EA", "#14573D"))
        return format_html(
            '<span class="m-status" style="background:{};color:{}">{}</span>',
            background, colour, obj.type)


@admin.register(BehaviourType)
class BehaviourTypeAdmin(admin.ModelAdmin):
    """Natures de faits : liste vivante, enrichie par l'équipe.

    Une nature saisie depuis le formulaire d'un fait (bouton « + ») est
    conservée ici et proposée à toutes les saisies suivantes.
    """

    list_display = ["name", "name_ar", "is_negative", "order", "is_active",
                    "usage_count"]
    list_filter = ["is_negative", "is_active"]
    search_fields = ["name", "name_ar"]
    list_editable = ["order", "is_active"]

    @admin.display(description=_("faits enregistrés"))
    def usage_count(self, obj):
        return obj.records.count()


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
