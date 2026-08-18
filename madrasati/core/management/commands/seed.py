"""Commande « seed » : données de démarrage pour une école marocaine.

Crée l'année scolaire en cours, tous les niveaux du système éducatif
marocain, des matières, des formules de frais, et (avec --demo) des
élèves, employés et paiements d'exemple.
"""

import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import AcademicYear, Level, SchoolClass, Subject
from finance.models import Payment, TuitionPlan
from hr.models import Employee, PayrollRun
from students.models import Enrollment, Guardian, Student

LEVELS = [
    # (cycle, code, nom_fr, nom_ar)
    ("preschool", "PS", "Petite section", "القسم الأول - التعليم الأولي"),
    ("preschool", "MS", "Moyenne section", "القسم الثاني - التعليم الأولي"),
    ("preschool", "GS", "Grande section", "القسم الثالث - التعليم الأولي"),
    ("primary", "1AP", "1re année primaire", "الأولى ابتدائي"),
    ("primary", "2AP", "2e année primaire", "الثانية ابتدائي"),
    ("primary", "3AP", "3e année primaire", "الثالثة ابتدائي"),
    ("primary", "4AP", "4e année primaire", "الرابعة ابتدائي"),
    ("primary", "5AP", "5e année primaire", "الخامسة ابتدائي"),
    ("primary", "6AP", "6e année primaire", "السادسة ابتدائي"),
    ("middle", "1AC", "1re année collège", "الأولى إعدادي"),
    ("middle", "2AC", "2e année collège", "الثانية إعدادي"),
    ("middle", "3AC", "3e année collège", "الثالثة إعدادي"),
    ("high", "TC", "Tronc commun", "الجذع المشترك"),
    ("high", "1BAC", "1re année baccalauréat", "الأولى باكالوريا"),
    ("high", "2BAC", "2e année baccalauréat", "الثانية باكالوريا"),
]

SUBJECTS = [
    ("Arabe", "اللغة العربية", 3),
    ("Français", "اللغة الفرنسية", 3),
    ("Anglais", "اللغة الإنجليزية", 2),
    ("Mathématiques", "الرياضيات", 4),
    ("Sciences de la vie et de la terre", "علوم الحياة والأرض", 2),
    ("Physique-chimie", "الفيزياء والكيمياء", 2),
    ("Histoire-géographie", "الاجتماعيات", 2),
    ("Éducation islamique", "التربية الإسلامية", 2),
    ("Éducation physique", "التربية البدنية", 1),
    ("Informatique", "المعلوميات", 1),
]


class Command(BaseCommand):
    help = "Initialise les données de base (niveaux marocains, année scolaire, matières)."

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true",
                            help="Ajoute aussi des données de démonstration "
                                 "(élèves, employés, paiements).")

    def handle(self, *args, **options):
        today = timezone.localdate()
        # Année scolaire marocaine : septembre → juillet.
        start_year = today.year if today.month >= 8 else today.year - 1
        year, _ = AcademicYear.objects.get_or_create(
            name=f"{start_year}-{start_year + 1}",
            defaults={
                "start_date": datetime.date(start_year, 9, 1),
                "end_date": datetime.date(start_year + 1, 7, 10),
                "is_current": True,
            },
        )

        for order, (cycle, code, name_fr, name_ar) in enumerate(LEVELS):
            Level.objects.get_or_create(
                code=code,
                defaults={"cycle": cycle, "name_fr": name_fr,
                          "name_ar": name_ar, "order": order},
            )

        for name_fr, name_ar, coef in SUBJECTS:
            Subject.objects.get_or_create(
                name_fr=name_fr,
                defaults={"name_ar": name_ar, "coefficient": coef},
            )

        # Formules de frais indicatives par cycle (en DH)
        fees_by_cycle = {
            "preschool": ("800", "700"),
            "primary": ("1000", "900"),
            "middle": ("1200", "1100"),
            "high": ("1500", "1300"),
        }
        for level in Level.objects.all():
            registration, monthly = fees_by_cycle[level.cycle]
            TuitionPlan.objects.get_or_create(
                academic_year=year, level=level,
                defaults={
                    "registration_fee": Decimal(registration),
                    "monthly_fee": Decimal(monthly),
                    "insurance_fee": Decimal("150"),
                    "months_count": 10,
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f"Données de base créées (année {year})."))

        if options["demo"]:
            self._create_demo(year)
            self.stdout.write(self.style.SUCCESS("Données de démonstration créées."))

    def _create_demo(self, year):
        teacher, _ = Employee.objects.get_or_create(
            matricule="EMP001",
            defaults=dict(
                first_name="Fatima", last_name="El Amrani",
                first_name_ar="فاطمة", last_name_ar="العمراني",
                cin="BK456789", cnss_number="112233445",
                role=Employee.Role.TEACHER, phone="0661234567",
                hire_date=datetime.date(year.start_date.year, 9, 1),
                base_salary=Decimal("7500"), allowances=Decimal("500"),
                dependents=2,
            ),
        )
        Employee.objects.get_or_create(
            matricule="EMP002",
            defaults=dict(
                first_name="Youssef", last_name="Benali",
                first_name_ar="يوسف", last_name_ar="بنعلي",
                cin="AB123456", cnss_number="998877665",
                role=Employee.Role.ADMIN, phone="0662345678",
                hire_date=datetime.date(year.start_date.year, 9, 1),
                base_salary=Decimal("5000"), allowances=Decimal("0"),
                dependents=0,
            ),
        )

        level_2ap = Level.objects.get(code="2AP")
        school_class, _ = SchoolClass.objects.get_or_create(
            academic_year=year, level=level_2ap, name="A",
            defaults={"capacity": 30, "main_teacher": teacher},
        )
        plan = TuitionPlan.objects.get(academic_year=year, level=level_2ap)

        guardian, _ = Guardian.objects.get_or_create(
            cin="C654321",
            defaults=dict(
                first_name="Mohammed", last_name="Alaoui",
                relationship=Guardian.Relationship.FATHER,
                phone="0663456789", profession="Commerçant",
                address="12 rue Hassan II, Casablanca",
            ),
        )
        student, created = Student.objects.get_or_create(
            massar_code="G123456789",
            defaults=dict(
                first_name="Amina", last_name="Alaoui",
                first_name_ar="أمينة", last_name_ar="العلوي",
                gender=Student.Gender.FEMALE,
                birth_date=datetime.date(year.start_date.year - 7, 3, 15),
                birth_place="Casablanca", city="Casablanca",
                address="12 rue Hassan II, Casablanca",
            ),
        )
        if created:
            student.guardians.add(guardian)

        enrollment, _ = Enrollment.objects.get_or_create(
            student=student, school_class=school_class,
            defaults={"tuition_plan": plan},
        )
        if not enrollment.payments.exists():
            Payment.objects.create(
                enrollment=enrollment, kind=Payment.Kind.REGISTRATION,
                amount=plan.registration_fee,
                date=datetime.date(year.start_date.year, 9, 1),
            )
            Payment.objects.create(
                enrollment=enrollment, kind=Payment.Kind.TUITION, month=9,
                amount=plan.monthly_fee,
                date=datetime.date(year.start_date.year, 9, 1),
            )

        run, created = PayrollRun.objects.get_or_create(
            year=year.start_date.year, month=9)
        if created:
            run.generate_payslips()
