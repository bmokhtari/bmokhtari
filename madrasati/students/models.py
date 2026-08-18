import datetime

from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# Indicatif téléphonique marocain : 06XXXXXXXX, 07XXXXXXXX, +2126..., 05... (fixe)
moroccan_phone_validator = RegexValidator(
    regex=r"^(\+212|0)[5-8]\d{8}$",
    message=_("Numéro marocain attendu, ex. 0612345678 ou +212612345678."),
)

# CIN marocaine : 1 ou 2 lettres suivies de 5 à 7 chiffres (ex. AB123456)
cin_validator = RegexValidator(
    regex=r"^[A-Za-z]{1,2}\d{5,7}$",
    message=_("CIN invalide, ex. AB123456."),
)


class Guardian(models.Model):
    """Parent ou tuteur légal de l'élève."""

    class Relationship(models.TextChoices):
        FATHER = "father", _("Père")
        MOTHER = "mother", _("Mère")
        GUARDIAN = "guardian", _("Tuteur légal")

    first_name = models.CharField(_("prénom"), max_length=60)
    last_name = models.CharField(_("nom"), max_length=60)
    relationship = models.CharField(_("lien de parenté"), max_length=10,
                                    choices=Relationship.choices,
                                    default=Relationship.FATHER)
    cin = models.CharField(_("CIN"), max_length=10, blank=True,
                           validators=[cin_validator],
                           help_text=_("Carte d'identité nationale, ex. AB123456"))
    phone = models.CharField(_("téléphone"), max_length=13,
                             validators=[moroccan_phone_validator])
    email = models.EmailField(_("e-mail"), blank=True)
    profession = models.CharField(_("profession"), max_length=80, blank=True)
    address = models.TextField(_("adresse"), blank=True)

    class Meta:
        verbose_name = _("tuteur")
        verbose_name_plural = _("tuteurs")
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_relationship_display()})"


class Student(models.Model):
    """Élève : état civil bilingue, code Massar, tuteurs, scolarité."""

    class Gender(models.TextChoices):
        MALE = "M", _("Garçon")
        FEMALE = "F", _("Fille")

    # État civil (bilingue, comme sur les documents officiels marocains)
    first_name = models.CharField(_("prénom (français)"), max_length=60)
    last_name = models.CharField(_("nom (français)"), max_length=60)
    first_name_ar = models.CharField(_("prénom (arabe)"), max_length=60, blank=True)
    last_name_ar = models.CharField(_("nom (arabe)"), max_length=60, blank=True)
    gender = models.CharField(_("sexe"), max_length=1, choices=Gender.choices)
    birth_date = models.DateField(_("date de naissance"))
    birth_place = models.CharField(_("lieu de naissance"), max_length=80, blank=True)

    # Identifiants officiels
    massar_code = models.CharField(
        _("code Massar"), max_length=12, blank=True,
        help_text=_("Code national de l'élève (système Massar du ministère), "
                    "ex. G123456789"))

    # Coordonnées
    address = models.TextField(_("adresse"), blank=True)
    city = models.CharField(_("ville"), max_length=60, blank=True, default="Casablanca")
    phone = models.CharField(_("téléphone"), max_length=13, blank=True,
                             validators=[moroccan_phone_validator])

    guardians = models.ManyToManyField(Guardian, related_name="students",
                                       verbose_name=_("tuteurs"), blank=True)

    # Dossier
    medical_notes = models.TextField(_("observations médicales"), blank=True)
    previous_school = models.CharField(_("établissement précédent"),
                                       max_length=120, blank=True)
    registered_on = models.DateField(_("date d'inscription"), default=timezone.localdate)
    is_active = models.BooleanField(_("actif"), default=True)

    class Meta:
        verbose_name = _("élève")
        verbose_name_plural = _("élèves")
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self):
        today = datetime.date.today()
        born = self.birth_date
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    age.fget.short_description = _("âge")

    @property
    def full_name_ar(self):
        return f"{self.first_name_ar} {self.last_name_ar}".strip()

    def current_enrollment(self):
        return (self.enrollments
                .filter(status=Enrollment.Status.ACTIVE,
                        school_class__academic_year__is_current=True)
                .select_related("school_class__level")
                .first())


class Enrollment(models.Model):
    """Inscription d'un élève dans une classe pour une année scolaire."""

    class Status(models.TextChoices):
        ACTIVE = "active", _("Inscrit")
        TRANSFERRED = "transferred", _("Transféré")
        WITHDRAWN = "withdrawn", _("Retiré")
        GRADUATED = "graduated", _("Diplômé")

    student = models.ForeignKey(Student, on_delete=models.CASCADE,
                                related_name="enrollments", verbose_name=_("élève"))
    school_class = models.ForeignKey("core.SchoolClass", on_delete=models.PROTECT,
                                     related_name="enrollments",
                                     verbose_name=_("classe"))
    date = models.DateField(_("date d'inscription"), default=timezone.localdate)
    status = models.CharField(_("statut"), max_length=12, choices=Status.choices,
                              default=Status.ACTIVE)
    tuition_plan = models.ForeignKey(
        "finance.TuitionPlan", on_delete=models.PROTECT, null=True, blank=True,
        related_name="enrollments", verbose_name=_("formule de frais"))
    discount_pct = models.DecimalField(
        _("remise (%)"), max_digits=5, decimal_places=2, default=0,
        help_text=_("Remise accordée (fratrie, bourse…), en pourcentage."))

    class Meta:
        verbose_name = _("inscription")
        verbose_name_plural = _("inscriptions")
        unique_together = [("student", "school_class")]
        ordering = ["-date"]

    def __str__(self):
        return f"{self.student} → {self.school_class}"


class Attendance(models.Model):
    """Absence ou retard d'un élève à une date donnée."""

    class Kind(models.TextChoices):
        ABSENT = "absent", _("Absence")
        LATE = "late", _("Retard")

    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE,
                                   related_name="attendance",
                                   verbose_name=_("inscription"))
    date = models.DateField(_("date"), default=timezone.localdate)
    kind = models.CharField(_("type"), max_length=8, choices=Kind.choices,
                            default=Kind.ABSENT)
    justified = models.BooleanField(_("justifiée"), default=False)
    note = models.CharField(_("remarque"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("absence / retard")
        verbose_name_plural = _("absences / retards")
        unique_together = [("enrollment", "date", "kind")]
        ordering = ["-date"]

    def __str__(self):
        return f"{self.enrollment.student} — {self.get_kind_display()} {self.date}"


class Grade(models.Model):
    """Note d'un contrôle continu (sur 20, système marocain)."""

    class Term(models.TextChoices):
        S1 = "s1", _("1er semestre")
        S2 = "s2", _("2e semestre")

    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE,
                                   related_name="grades",
                                   verbose_name=_("inscription"))
    subject = models.ForeignKey("core.Subject", on_delete=models.PROTECT,
                                related_name="grades", verbose_name=_("matière"))
    term = models.CharField(_("semestre"), max_length=2, choices=Term.choices)
    label = models.CharField(_("intitulé"), max_length=60,
                             help_text=_("Ex. : Contrôle 1, Devoir surveillé"))
    score = models.DecimalField(_("note (/20)"), max_digits=4, decimal_places=2)
    date = models.DateField(_("date"), default=timezone.localdate)

    class Meta:
        verbose_name = _("note")
        verbose_name_plural = _("notes")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.enrollment.student} — {self.subject} : {self.score}/20"
