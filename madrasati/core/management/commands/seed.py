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
from finance.models import (SCHOOL_MONTHS, DiscountRequest, Payment,
                            TuitionPlan, expected_monthly_amount)
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
        """Jeu de démonstration : personnel, classes, élèves et paiements."""
        start_year = year.start_date.year

        staff = [
            ("EMP001", "Fatima", "El Amrani", "فاطمة", "العمراني", "BK456789",
             Employee.Role.TEACHER, "0661234567", "7500", "500", 2),
            ("EMP002", "Youssef", "Benali", "يوسف", "بنعلي", "AB123456",
             Employee.Role.ADMIN, "0662345678", "5000", "0", 0),
            ("EMP003", "Khadija", "Ouazzani", "خديجة", "الوزاني", "BE778120",
             Employee.Role.TEACHER, "0663456781", "8200", "600", 3),
            ("EMP004", "Rachid", "Tazi", "رشيد", "التازي", "C321987",
             Employee.Role.TEACHER, "0664567812", "6900", "0", 1),
            ("EMP005", "Nadia", "Chraibi", "نادية", "الشرايبي", "BJ556677",
             Employee.Role.DIRECTION, "0665678123", "14000", "2000", 2),
            ("EMP006", "Hassan", "Bouzid", "حسن", "بوزيد", "D889001",
             Employee.Role.SUPPORT, "0666781234", "3600", "0", 4),
        ]
        employees = {}
        for (matricule, first, last, first_ar, last_ar, cin, role, phone,
             salary, bonus, dependents) in staff:
            employee, _ = Employee.objects.get_or_create(
                matricule=matricule,
                defaults=dict(
                    first_name=first, last_name=last,
                    first_name_ar=first_ar, last_name_ar=last_ar,
                    cin=cin, cnss_number=f"1122{matricule[-3:]}00",
                    role=role, phone=phone,
                    hire_date=datetime.date(start_year, 9, 1),
                    base_salary=Decimal(salary), allowances=Decimal(bonus),
                    dependents=dependents,
                ),
            )
            employees[matricule] = employee

        classes = {}
        for code, name, teacher in [("2AP", "A", "EMP001"),
                                    ("2AP", "B", "EMP004"),
                                    ("5AP", "A", "EMP003")]:
            level = Level.objects.get(code=code)
            school_class, _ = SchoolClass.objects.get_or_create(
                academic_year=year, level=level, name=name,
                defaults={"capacity": 30, "main_teacher": employees[teacher]},
            )
            classes[f"{code}-{name}"] = school_class

        # (prénom, nom, prénom ar, nom ar, sexe, classe, mensualités réglées)
        pupils = [
            ("Amina", "Alaoui", "أمينة", "العلوي", "F", "2AP-A", 6),
            ("Zakaria", "Berrada", "زكرياء", "برادة", "M", "2AP-A", 6),
            ("Salma", "Bennani", "سلمى", "بناني", "F", "2AP-A", 4),
            ("Ilyas", "Cherkaoui", "إلياس", "الشرقاوي", "M", "2AP-B", 6),
            ("Hiba", "Fassi", "هبة", "الفاسي", "F", "2AP-B", 5),
            ("Omar", "Idrissi", "عمر", "الإدريسي", "M", "2AP-B", 6),
            ("Lina", "Sabri", "لينا", "الصبري", "F", "5AP-A", 6),
            ("Adam", "Naciri", "آدم", "الناصري", "M", "5AP-A", 3),
            ("Sofia", "Lahlou", "صوفيا", "لحلو", "F", "5AP-A", 6),
            ("Mehdi", "Kettani", "مهدي", "الكتاني", "M", "5AP-A", 6),
        ]

        months = [m for m, _label in SCHOOL_MONTHS][:10]

        for index, (first, last, first_ar, last_ar, gender, class_key,
                    paid_months) in enumerate(pupils):
            guardian, _ = Guardian.objects.get_or_create(
                cin=f"C{600000 + index}",
                defaults=dict(
                    first_name="Mohammed" if index % 2 else "Latifa",
                    last_name=last,
                    relationship=(Guardian.Relationship.FATHER if index % 2
                                  else Guardian.Relationship.MOTHER),
                    phone=f"066{3000000 + index * 111}",
                    profession="Commerçant" if index % 2 else "Enseignante",
                    address=f"{10 + index} rue Hassan II, Casablanca",
                ),
            )
            student, created = Student.objects.get_or_create(
                massar_code=f"G{123456780 + index}",
                defaults=dict(
                    first_name=first, last_name=last,
                    first_name_ar=first_ar, last_name_ar=last_ar,
                    gender=gender,
                    birth_date=datetime.date(start_year - 7 - index % 4,
                                             1 + index % 12, 5 + index),
                    birth_place="Casablanca", city="Casablanca",
                    address=f"{10 + index} rue Hassan II, Casablanca",
                ),
            )
            if created:
                student.guardians.add(guardian)

            school_class = classes[class_key]
            plan = TuitionPlan.objects.get(academic_year=year,
                                           level=school_class.level)
            enrollment, _ = Enrollment.objects.get_or_create(
                student=student, school_class=school_class,
                defaults={"tuition_plan": plan,
                          # fratrie : une remise sur un élève sur cinq
                          "discount_pct": Decimal("10") if index % 5 == 0
                          else Decimal("0")},
            )

            if enrollment.payments.exists():
                continue

            Payment.objects.create(
                enrollment=enrollment, kind=Payment.Kind.REGISTRATION,
                amount=plan.registration_fee + plan.insurance_fee,
                method=Payment.Method.TRANSFER,
                date=datetime.date(start_year, 9, 1),
            )
            monthly = expected_monthly_amount(enrollment)
            for position, month in enumerate(months[:paid_months]):
                pay_year = start_year if month >= 9 else start_year + 1
                Payment.objects.create(
                    enrollment=enrollment, kind=Payment.Kind.TUITION,
                    month=month, amount=monthly,
                    method=(Payment.Method.CASH if position % 2
                            else Payment.Method.CHEQUE),
                    reference="" if position % 2 else f"44701{index}{position}",
                    date=datetime.date(pay_year, month, 3 + position % 5),
                )

        # Deux demandes de remise : une en attente, une déjà approuvée,
        # pour illustrer le circuit d'approbation.
        first, second = Enrollment.objects.order_by("pk")[:2]
        if not DiscountRequest.objects.exists():
            DiscountRequest.objects.create(
                enrollment=first, percentage=Decimal("20"),
                scope=DiscountRequest.Scope.YEAR,
                reason="Deuxième enfant scolarisé dans l'établissement.")
            approved = DiscountRequest.objects.create(
                enrollment=second, percentage=Decimal("15"),
                scope=DiscountRequest.Scope.PERIOD,
                start_month=1, end_month=3,
                reason="Absence prolongée pour raisons médicales.")
            approved.decide(DiscountRequest.Status.APPROVED, None,
                            note="Justificatif médical fourni.")

        for month in (9, 10, 11, 12):
            run, created = PayrollRun.objects.get_or_create(
                year=start_year, month=month)
            if created:
                run.generate_payslips()
                run.status = (PayrollRun.Status.PAID if month < 12
                              else PayrollRun.Status.DRAFT)
                run.save()
