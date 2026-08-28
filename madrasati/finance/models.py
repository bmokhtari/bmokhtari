from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
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
    """Formule de frais d'un niveau (montants en dirhams, MAD).

    Deux modes de facturation coexistent : l'enseignement général se règle
    au mois sur les dix mois de l'année scolaire ; la formation
    professionnelle et le supérieur se calculent en un montant annuel,
    ensuite étalé selon l'échéancier choisi par la famille.
    """

    class Billing(models.TextChoices):
        MONTHLY = "monthly", _("Mensuel (enseignement général)")
        ANNUAL = "annual", _("Annuel (formation professionnelle et supérieure)")

    school = models.ForeignKey("core.School", on_delete=models.CASCADE,
                               null=True, blank=True,
                               related_name="tuition_plans",
                               verbose_name=_("établissement"))
    billing = models.CharField(_("mode de facturation"), max_length=8,
                               choices=Billing.choices, default=Billing.MONTHLY)
    annual_fee = models.DecimalField(
        _("scolarité annuelle (DH)"), max_digits=9, decimal_places=2, default=0,
        help_text=_("Facturation annuelle : montant global de la scolarité, "
                    "frais d'inscription compris."))
    cash_discount_pct = models.DecimalField(
        _("remise paiement comptant (%)"), max_digits=5, decimal_places=2,
        default=Decimal("10"),
        help_text=_("Appliquée si la totalité est réglée en début d'année."))
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
        unique_together = [("academic_year", "level", "school")]
        ordering = ["level__order"]

    def __str__(self):
        if self.billing == self.Billing.ANNUAL:
            return f"{self.level.code} {self.academic_year} — {self.annual_fee} DH/an"
        return f"{self.level.code} {self.academic_year} — {self.monthly_fee} DH/mois"

    @property
    def tuition_base(self):
        """Scolarité seule, hors frais annexes."""
        if self.billing == self.Billing.ANNUAL:
            return self.annual_fee
        return self.monthly_fee * self.months_count

    @property
    def annual_total(self):
        """Total annuel : scolarité, inscription et frais annexes obligatoires."""
        extras = sum((line.amount for line in self.lines.all()
                      if line.mandatory), Decimal("0"))
        if self.billing == self.Billing.ANNUAL:
            # Le montant annuel inclut déjà l'inscription.
            return self.annual_fee + extras
        return (self.registration_fee + self.insurance_fee
                + self.monthly_fee * self.months_count + extras)
    annual_total.fget.short_description = _("total annuel (DH)")


class FeeLine(models.Model):
    """Frais annexe d'une formule : livres, fournitures, photocopies, diplôme…

    La liste A regroupe les manuels à acheter obligatoirement auprès de
    l'établissement ; la liste D ceux que la famille peut se procurer
    ailleurs — ces derniers ne sont facturés que si elle les prend à
    l'école.
    """

    class Kind(models.TextChoices):
        REGISTRATION = "registration", _("Inscription annuelle (FEA)")
        BOOKS_A = "books_a", _("Manuels — liste A (achat à l'école)")
        BOOKS_D = "books_d", _("Manuels — liste D (achat libre)")
        SUPPLIES = "supplies", _("Fournitures (papier, stylos…)")
        PHOTOCOPY = "photocopy", _("Photocopies et matériel")
        DIPLOMA = "diploma", _("Frais de diplôme")
        INSURANCE = "insurance", _("Assurance scolaire")
        OTHER = "other", _("Autre")

    plan = models.ForeignKey(TuitionPlan, on_delete=models.CASCADE,
                             related_name="lines", verbose_name=_("formule"))
    kind = models.CharField(_("nature"), max_length=13, choices=Kind.choices)
    label = models.CharField(_("intitulé"), max_length=80, blank=True,
                             help_text=_("Laisser vide pour reprendre "
                                         "l'intitulé de la nature."))
    amount = models.DecimalField(_("montant (DH)"), max_digits=8,
                                 decimal_places=2)
    mandatory = models.BooleanField(
        _("obligatoire"), default=True,
        help_text=_("Décocher pour la liste D : facturée seulement si la "
                    "famille l'achète à l'école."))
    due_month = models.PositiveSmallIntegerField(
        _("exigible au mois de"), choices=SCHOOL_MONTHS, null=True, blank=True,
        help_text=_("Laisser vide pour inclure ce frais dans l'échéancier. "
                    "Le diplôme, par exemple, se règle à part au 6e mois."))

    class Meta:
        verbose_name = _("frais annexe")
        verbose_name_plural = _("frais annexes")
        ordering = ["kind", "id"]

    def __str__(self):
        return f"{self.title} — {self.amount} DH"

    @property
    def title(self):
        return self.label or self.get_kind_display()

    @property
    def is_separate(self):
        """Frais réglé à son échéance propre, hors échéancier."""
        return self.due_month is not None


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


class DiscountRequest(models.Model):
    """Demande de remise sur la scolarité, soumise à approbation.

    Une remise n'a d'effet qu'une fois approuvée : le secrétariat saisit la
    demande (motif, taux, période), la direction l'approuve ou la refuse.
    Tant qu'elle est en attente, les mensualités restent inchangées.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("En attente")
        APPROVED = "approved", _("Approuvée")
        REJECTED = "rejected", _("Refusée")

    class Scope(models.TextChoices):
        YEAR = "year", _("Toute l'année scolaire")
        PERIOD = "period", _("Période déterminée")

    enrollment = models.ForeignKey(
        "students.Enrollment", on_delete=models.CASCADE,
        related_name="discount_requests", verbose_name=_("inscription"))
    percentage = models.DecimalField(
        _("remise demandée (%)"), max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01")),
                    MaxValueValidator(Decimal("100"))],
        help_text=_("Pourcentage appliqué à la mensualité."))
    scope = models.CharField(_("portée"), max_length=8, choices=Scope.choices,
                             default=Scope.YEAR)
    start_month = models.PositiveSmallIntegerField(
        _("du mois de"), choices=SCHOOL_MONTHS, null=True, blank=True)
    end_month = models.PositiveSmallIntegerField(
        _("au mois de"), choices=SCHOOL_MONTHS, null=True, blank=True)
    reason = models.TextField(
        _("motif"),
        help_text=_("Fratrie, situation sociale, bourse, absence prolongée…"))

    status = models.CharField(_("statut"), max_length=10,
                              choices=Status.choices, default=Status.PENDING,
                              editable=False)
    requested_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="discount_requests_made",
        verbose_name=_("demandée par"))
    requested_on = models.DateTimeField(_("demandée le"), auto_now_add=True)
    decided_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="discount_requests_decided",
        verbose_name=_("décision de"))
    decided_on = models.DateTimeField(_("décidée le"), null=True, blank=True,
                                      editable=False)
    decision_note = models.CharField(_("motif de la décision"), max_length=200,
                                     blank=True)

    class Meta:
        verbose_name = _("demande de remise")
        verbose_name_plural = _("demandes de remise")
        ordering = ["-requested_on"]
        permissions = [
            ("approve_discountrequest",
             _("Peut approuver ou refuser une demande de remise")),
        ]

    def __str__(self):
        return f"{self.enrollment.student} — {self.percentage} % ({self.get_status_display()})"

    def clean(self):
        if self.scope == self.Scope.PERIOD:
            if not self.start_month or not self.end_month:
                raise ValidationError({
                    "start_month": _("Précisez le premier et le dernier mois "
                                     "de la période."),
                })
            months = [m for m, _label in SCHOOL_MONTHS]
            if months.index(self.start_month) > months.index(self.end_month):
                raise ValidationError({
                    "end_month": _("Le dernier mois doit suivre le premier "
                                   "dans l'année scolaire."),
                })
        else:
            # Une remise annuelle n'a pas de bornes de période.
            self.start_month = None
            self.end_month = None

    @property
    def period_display(self):
        if self.scope == self.Scope.YEAR:
            return _("Toute l'année")
        return f"{self.get_start_month_display()} → {self.get_end_month_display()}"

    def covers(self, month):
        """La remise s'applique-t-elle au mois donné ?"""
        if self.status != self.Status.APPROVED:
            return False
        if self.scope == self.Scope.YEAR:
            return True
        if not self.start_month or not self.end_month:
            return False
        months = [m for m, _label in SCHOOL_MONTHS]
        try:
            position = months.index(month)
        except ValueError:
            return False
        return (months.index(self.start_month) <= position
                <= months.index(self.end_month))

    def decide(self, status, user, note=""):
        """Enregistre la décision de l'approbateur."""
        self.status = status
        self.decided_by = user
        self.decided_on = timezone.now()
        if note:
            self.decision_note = note
        self.save(update_fields=["status", "decided_by", "decided_on",
                                 "decision_note"])


def effective_discount_pct(enrollment, month=None):
    """Remise réellement applicable, en pourcentage.

    Combine la remise permanente de l'inscription et les demandes
    **approuvées** couvrant le mois considéré ; la plus avantageuse pour la
    famille l'emporte. Les demandes en attente ou refusées sont ignorées.
    """
    base = enrollment.discount_pct or Decimal("0")
    if month is None:
        return base
    granted = [request.percentage
               for request in enrollment.discount_requests.all()
               if request.covers(month)]
    return max([base, *granted]) if granted else base


def expected_monthly_amount(enrollment, month=None):
    """Mensualité due pour une inscription, remise déduite."""
    plan = enrollment.tuition_plan
    if plan is None:
        return Decimal("0.00")
    pct = effective_discount_pct(enrollment, month)
    discount = Decimal("1") - pct / Decimal("100")
    return (plan.monthly_fee * discount).quantize(Decimal("0.01"))


def due_months(enrollment, today=None):
    """Mois de scolarité déjà échus à la date du jour.

    L'année scolaire marocaine court de septembre à juin ; hors de cette
    période (juillet-août), l'année est considérée comme terminée.
    """
    months = [m for m, _label in SCHOOL_MONTHS]
    plan = enrollment.tuition_plan
    limit = plan.months_count if plan else len(months)
    calendar = months[:limit]

    today = today or timezone.localdate()
    year = enrollment.school_class.academic_year
    # L'année visée peut être passée ou à venir : on se cale d'abord sur ses
    # bornes, sinon un mois de l'année en cours minorerait la dette d'une
    # année déjà achevée.
    if today >= year.end_date:
        return calendar
    if today < year.start_date:
        return []
    if today.month in calendar:
        return calendar[:calendar.index(today.month) + 1]
    return calendar


def overdue_months(enrollment, today=None):
    """Mois des échéances exigibles non couvertes par les versements."""
    from .schedule import overdue_entries

    return [entry["month"] for entry in overdue_entries(enrollment, today)]


def overdue_total(enrollment, today=None):
    """Somme restant due sur les échéances déjà exigibles."""
    from .schedule import balance_due

    return balance_due(enrollment, today)


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
