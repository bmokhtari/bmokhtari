from decimal import Decimal

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# Mois de l'année scolaire marocaine (septembre → juillet : 10 mensualités
# par défaut, juillet inclus pour les écoles ouvertes en été).
SCHOOL_MONTHS = [
    (9, _("Septembre")), (10, _("Octobre")), (11, _("Novembre")),
    (12, _("Décembre")), (1, _("Janvier")), (2, _("Février")),
    (3, _("Mars")), (4, _("Avril")), (5, _("Mai")), (6, _("Juin")),
    (7, _("Juillet")),
]


class TuitionPlan(models.Model):
    """Formule de frais de scolarité d'un niveau (montants en dirhams, MAD)."""

    academic_year = models.ForeignKey("core.AcademicYear", on_delete=models.CASCADE,
                                      related_name="tuition_plans",
                                      verbose_name=_("année scolaire"))
    level = models.ForeignKey("core.Level", on_delete=models.CASCADE,
                              related_name="tuition_plans", verbose_name=_("niveau"))
    registration_fee = models.DecimalField(
        _("frais d'inscription (DH)"), max_digits=8, decimal_places=2, default=0,
        help_text=_("Payés une fois à l'inscription."))
    monthly_fee = models.DecimalField(
        _("mensualité (DH)"), max_digits=8, decimal_places=2,
        help_text=_("Frais de scolarité mensuels."))
    insurance_fee = models.DecimalField(
        _("assurance scolaire (DH)"), max_digits=8, decimal_places=2, default=0)
    months_count = models.PositiveSmallIntegerField(
        _("nombre de mensualités"), default=10,
        help_text=_("En général 10 (septembre à juin)."))

    class Meta:
        verbose_name = _("formule de frais")
        verbose_name_plural = _("formules de frais")
        unique_together = [("academic_year", "level")]
        ordering = ["level__order"]

    def __str__(self):
        return f"{self.level.code} {self.academic_year} — {self.monthly_fee} DH/mois"

    @property
    def annual_total(self):
        return (self.registration_fee + self.insurance_fee
                + self.monthly_fee * self.months_count)
    annual_total.fget.short_description = _("total annuel (DH)")


class Payment(models.Model):
    """Paiement reçu d'une famille, en dirhams marocains."""

    class Kind(models.TextChoices):
        REGISTRATION = "registration", _("Frais d'inscription")
        TUITION = "tuition", _("Mensualité")
        INSURANCE = "insurance", _("Assurance scolaire")
        TRANSPORT = "transport", _("Transport scolaire")
        CANTEEN = "canteen", _("Cantine")
        OTHER = "other", _("Autre")

    class Method(models.TextChoices):
        CASH = "cash", _("Espèces")
        CHEQUE = "cheque", _("Chèque")
        TRANSFER = "transfer", _("Virement bancaire")
        CARD = "card", _("Carte bancaire")

    enrollment = models.ForeignKey("students.Enrollment", on_delete=models.PROTECT,
                                   related_name="payments",
                                   verbose_name=_("inscription"))
    kind = models.CharField(_("type de paiement"), max_length=12,
                            choices=Kind.choices, default=Kind.TUITION)
    month = models.PositiveSmallIntegerField(
        _("mois concerné"), choices=SCHOOL_MONTHS, null=True, blank=True,
        help_text=_("Pour les mensualités : le mois couvert par ce paiement."))
    amount = models.DecimalField(_("montant (DH)"), max_digits=8, decimal_places=2)
    method = models.CharField(_("mode de paiement"), max_length=10,
                              choices=Method.choices, default=Method.CASH)
    reference = models.CharField(_("référence"), max_length=60, blank=True,
                                 help_text=_("N° de chèque ou de virement."))
    date = models.DateField(_("date de paiement"), default=timezone.localdate)
    receipt_number = models.CharField(_("n° de reçu"), max_length=20, unique=True,
                                      blank=True, editable=False)
    received_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL,
                                    null=True, blank=True, editable=False,
                                    verbose_name=_("encaissé par"))
    note = models.CharField(_("remarque"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("paiement")
        verbose_name_plural = _("paiements")
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.receipt_number} — {self.enrollment.student} — {self.amount} DH"

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            year = self.date.year if self.date else timezone.localdate().year
            prefix = f"REC-{year}-"
            last = (Payment.objects
                    .filter(receipt_number__startswith=prefix)
                    .order_by("-receipt_number")
                    .values_list("receipt_number", flat=True)
                    .first())
            seq = int(last.rsplit("-", 1)[-1]) + 1 if last else 1
            self.receipt_number = f"{prefix}{seq:05d}"
        super().save(*args, **kwargs)


def expected_monthly_amount(enrollment):
    """Mensualité due pour une inscription, remise déduite."""
    plan = enrollment.tuition_plan
    if plan is None:
        return Decimal("0.00")
    discount = Decimal("1") - (enrollment.discount_pct or 0) / Decimal("100")
    return (plan.monthly_fee * discount).quantize(Decimal("0.01"))


def unpaid_months(enrollment):
    """Mois de l'année scolaire non encore réglés pour une inscription."""
    plan = enrollment.tuition_plan
    if plan is None:
        return []
    months = [m for m, _label in SCHOOL_MONTHS][: plan.months_count]
    paid = set(enrollment.payments
               .filter(kind=Payment.Kind.TUITION, month__isnull=False)
               .values_list("month", flat=True))
    return [m for m in months if m not in paid]
