from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class AcademicYear(models.Model):
    """Année scolaire marocaine (septembre → juillet), ex. « 2026-2027 »."""

    name = models.CharField(_("année scolaire"), max_length=9, unique=True,
                            help_text=_("Format : 2026-2027"))
    start_date = models.DateField(_("date de début"))
    end_date = models.DateField(_("date de fin"))
    is_current = models.BooleanField(_("année en cours"), default=False)

    class Meta:
        verbose_name = _("année scolaire")
        verbose_name_plural = _("années scolaires")
        ordering = ["-start_date"]

    def __str__(self):
        return self.name

    def clean(self):
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError(_("La date de début doit précéder la date de fin."))

    def save(self, *args, **kwargs):
        # Une seule année courante à la fois.
        if self.is_current:
            AcademicYear.objects.exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)

    @classmethod
    def current(cls):
        return cls.objects.filter(is_current=True).first()


class School(models.Model):
    """Établissement du groupe scolaire.

    Le groupe réunit deux familles de programmes qui ne se facturent pas de
    la même manière : l'enseignement général (Tahadi, Thomas Jefferson,
    William Thompson…), réglé au mois, et la formation professionnelle ou
    supérieure (ESTEP…), dont la scolarité se calcule à l'année.
    """

    class Programme(models.TextChoices):
        GENERAL = "general", _("Enseignement général")
        VOCATIONAL = "vocational", _("Formation professionnelle et supérieure")

    name = models.CharField(_("établissement"), max_length=80, unique=True)
    name_ar = models.CharField(_("établissement (arabe)"), max_length=80, blank=True)
    programme = models.CharField(_("type de programme"), max_length=12,
                                 choices=Programme.choices,
                                 default=Programme.GENERAL)
    city = models.CharField(_("ville"), max_length=60, blank=True,
                            default="Casablanca")
    address = models.CharField(_("adresse"), max_length=160, blank=True)
    phone = models.CharField(_("téléphone"), max_length=13, blank=True)
    is_active = models.BooleanField(_("actif"), default=True)

    class Meta:
        verbose_name = _("établissement")
        verbose_name_plural = _("établissements")
        ordering = ["programme", "name"]

    def __str__(self):
        return self.name

    @property
    def bills_annually(self):
        return self.programme == self.Programme.VOCATIONAL


class Level(models.Model):
    """Niveau du système éducatif marocain (ex. 1AP, 3AC, 2BAC)."""

    class Cycle(models.TextChoices):
        PRESCHOOL = "preschool", _("Préscolaire")
        PRIMARY = "primary", _("Primaire")
        MIDDLE = "middle", _("Collège")
        HIGH = "high", _("Lycée")
        VOCATIONAL = "vocational", _("Formation professionnelle")
        HIGHER = "higher", _("Enseignement supérieur")

    cycle = models.CharField(_("cycle"), max_length=12, choices=Cycle.choices)
    code = models.CharField(_("code"), max_length=10, unique=True,
                            help_text=_("Ex. : 1AP, 6AP, 3AC, TC, 1BAC, 2BAC"))
    name_fr = models.CharField(_("nom (français)"), max_length=80)
    name_ar = models.CharField(_("nom (arabe)"), max_length=80, blank=True)
    order = models.PositiveSmallIntegerField(_("ordre"), default=0)

    class Meta:
        verbose_name = _("niveau")
        verbose_name_plural = _("niveaux")
        ordering = ["order"]

    def __str__(self):
        return f"{self.code} — {self.name_fr}"


class SchoolClass(models.Model):
    """Une classe (groupe d'élèves) d'un niveau donné, ex. « 2AP - B »."""

    school = models.ForeignKey(
        School, on_delete=models.PROTECT, null=True, blank=True,
        related_name="classes", verbose_name=_("établissement"))
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE,
        related_name="classes", verbose_name=_("année scolaire"))
    level = models.ForeignKey(
        Level, on_delete=models.PROTECT,
        related_name="classes", verbose_name=_("niveau"))
    name = models.CharField(_("nom de la classe"), max_length=40,
                            help_text=_("Ex. : A, B, Groupe 1"))
    capacity = models.PositiveSmallIntegerField(_("capacité"), default=30)
    main_teacher = models.ForeignKey(
        "hr.Employee", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="classes_led", verbose_name=_("professeur principal"))

    class Meta:
        verbose_name = _("classe")
        verbose_name_plural = _("classes")
        unique_together = [("academic_year", "level", "name")]
        ordering = ["level__order", "name"]

    def __str__(self):
        return f"{self.level.code} - {self.name} ({self.academic_year})"

    @property
    def student_count(self):
        return self.enrollments.filter(status="active").count()


class Subject(models.Model):
    """Matière enseignée (bilingue français/arabe)."""

    name_fr = models.CharField(_("nom (français)"), max_length=80)
    name_ar = models.CharField(_("nom (arabe)"), max_length=80, blank=True)
    coefficient = models.DecimalField(_("coefficient"), max_digits=4,
                                      decimal_places=1, default=1)

    class Meta:
        verbose_name = _("matière")
        verbose_name_plural = _("matières")
        ordering = ["name_fr"]

    def __str__(self):
        return self.name_fr
