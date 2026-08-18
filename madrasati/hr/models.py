from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from students.models import cin_validator, moroccan_phone_validator

from . import payroll

MONTH_CHOICES = [
    (1, _("Janvier")), (2, _("Février")), (3, _("Mars")), (4, _("Avril")),
    (5, _("Mai")), (6, _("Juin")), (7, _("Juillet")), (8, _("Août")),
    (9, _("Septembre")), (10, _("Octobre")), (11, _("Novembre")),
    (12, _("Décembre")),
]


class Employee(models.Model):
    """Membre du personnel : enseignant, administration ou soutien."""

    class Role(models.TextChoices):
        TEACHER = "teacher", _("Enseignant(e)")
        ADMIN = "admin", _("Administration")
        SUPPORT = "support", _("Personnel de soutien")
        DIRECTION = "direction", _("Direction")

    matricule = models.CharField(_("matricule"), max_length=10, unique=True)
    first_name = models.CharField(_("prénom (français)"), max_length=60)
    last_name = models.CharField(_("nom (français)"), max_length=60)
    first_name_ar = models.CharField(_("prénom (arabe)"), max_length=60, blank=True)
    last_name_ar = models.CharField(_("nom (arabe)"), max_length=60, blank=True)
    cin = models.CharField(_("CIN"), max_length=10, unique=True,
                           validators=[cin_validator])
    cnss_number = models.CharField(_("n° CNSS"), max_length=12, blank=True)
    role = models.CharField(_("fonction"), max_length=10, choices=Role.choices,
                            default=Role.TEACHER)
    subjects = models.ManyToManyField("core.Subject", blank=True,
                                      related_name="teachers",
                                      verbose_name=_("matières enseignées"))
    phone = models.CharField(_("téléphone"), max_length=13,
                             validators=[moroccan_phone_validator])
    email = models.EmailField(_("e-mail"), blank=True)
    address = models.TextField(_("adresse"), blank=True)
    hire_date = models.DateField(_("date d'embauche"), default=timezone.localdate)

    # Paie
    base_salary = models.DecimalField(_("salaire de base (DH)"), max_digits=9,
                                      decimal_places=2)
    allowances = models.DecimalField(
        _("primes imposables (DH)"), max_digits=9, decimal_places=2, default=0,
        help_text=_("Primes mensuelles fixes soumises à cotisations et IR."))
    dependents = models.PositiveSmallIntegerField(
        _("personnes à charge"), default=0,
        help_text=_("Conjoint et enfants, pour la déduction IR (max 6)."))
    rib = models.CharField(_("RIB"), max_length=24, blank=True,
                           help_text=_("Relevé d'identité bancaire (24 chiffres)."))
    is_active = models.BooleanField(_("actif"), default=True)

    class Meta:
        verbose_name = _("employé(e)")
        verbose_name_plural = _("employé(e)s")
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.matricule})"

    @property
    def gross_salary(self):
        return self.base_salary + self.allowances
    gross_salary.fget.short_description = _("salaire brut (DH)")


class PayrollRun(models.Model):
    """Cycle de paie mensuel : génère un bulletin par employé actif."""

    class Status(models.TextChoices):
        DRAFT = "draft", _("Brouillon")
        VALIDATED = "validated", _("Validé")
        PAID = "paid", _("Payé")

    year = models.PositiveSmallIntegerField(_("année"))
    month = models.PositiveSmallIntegerField(_("mois"), choices=MONTH_CHOICES)
    status = models.CharField(_("statut"), max_length=10, choices=Status.choices,
                              default=Status.DRAFT)
    created_on = models.DateTimeField(_("créé le"), auto_now_add=True)
    note = models.CharField(_("remarque"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("cycle de paie")
        verbose_name_plural = _("cycles de paie")
        unique_together = [("year", "month")]
        ordering = ["-year", "-month"]

    def __str__(self):
        return f"{self.get_month_display()} {self.year}"

    def generate_payslips(self):
        """Crée (ou recrée) les bulletins des employés actifs.

        Les bulletins d'un cycle validé ou payé ne sont pas modifiés.
        """
        if self.status != self.Status.DRAFT:
            return 0
        self.payslips.all().delete()
        created = 0
        for employee in Employee.objects.filter(is_active=True):
            Payslip.create_for(self, employee)
            created += 1
        return created

    @property
    def total_net(self):
        return sum((p.net for p in self.payslips.all()), start=0)

    @property
    def total_employer_cost(self):
        return sum((p.employer_cost for p in self.payslips.all()), start=0)


class Payslip(models.Model):
    """Bulletin de paie : instantané des montants au moment du calcul."""

    payroll_run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE,
                                    related_name="payslips",
                                    verbose_name=_("cycle de paie"))
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT,
                                 related_name="payslips",
                                 verbose_name=_("employé(e)"))
    gross = models.DecimalField(_("salaire brut (DH)"), max_digits=9,
                                decimal_places=2)
    cnss = models.DecimalField(_("CNSS salariale (DH)"), max_digits=8,
                               decimal_places=2)
    amo = models.DecimalField(_("AMO salariale (DH)"), max_digits=8,
                              decimal_places=2)
    taxable = models.DecimalField(_("net imposable (DH)"), max_digits=9,
                                  decimal_places=2)
    family_deduction = models.DecimalField(_("déduction charges de famille (DH)"),
                                           max_digits=7, decimal_places=2)
    ir = models.DecimalField(_("IR (DH)"), max_digits=8, decimal_places=2)
    net = models.DecimalField(_("salaire net (DH)"), max_digits=9,
                              decimal_places=2)
    employer_cost = models.DecimalField(_("coût employeur (DH)"), max_digits=9,
                                        decimal_places=2)

    class Meta:
        verbose_name = _("bulletin de paie")
        verbose_name_plural = _("bulletins de paie")
        unique_together = [("payroll_run", "employee")]
        ordering = ["employee__last_name"]

    def __str__(self):
        return f"{self.employee} — {self.payroll_run}"

    @classmethod
    def create_for(cls, run, employee):
        result = payroll.compute_payslip(employee.gross_salary,
                                         employee.dependents)
        return cls.objects.create(
            payroll_run=run,
            employee=employee,
            gross=result["gross"],
            cnss=result["cnss"],
            amo=result["amo"],
            taxable=result["taxable"],
            family_deduction=result["family_deduction"],
            ir=result["ir"],
            net=result["net"],
            employer_cost=result["employer_cost"],
        )
