import datetime
from decimal import Decimal

from django.test import TestCase

from core.models import AcademicYear, Level, SchoolClass
from students.models import Enrollment, Student
from .models import Payment, TuitionPlan, expected_monthly_amount, unpaid_months


class FinanceTests(TestCase):
    def setUp(self):
        self.year = AcademicYear.objects.create(
            name="2026-2027", start_date=datetime.date(2026, 9, 1),
            end_date=datetime.date(2027, 7, 10), is_current=True)
        self.level = Level.objects.create(
            cycle=Level.Cycle.PRIMARY, code="1AP",
            name_fr="1re année primaire", order=1)
        self.school_class = SchoolClass.objects.create(
            academic_year=self.year, level=self.level, name="A")
        self.plan = TuitionPlan.objects.create(
            academic_year=self.year, level=self.level,
            registration_fee=Decimal("1000"), monthly_fee=Decimal("900"),
            insurance_fee=Decimal("150"), months_count=10)
        self.student = Student.objects.create(
            first_name="Amina", last_name="Alaoui", gender="F",
            birth_date=datetime.date(2019, 3, 15))
        self.enrollment = Enrollment.objects.create(
            student=self.student, school_class=self.school_class,
            tuition_plan=self.plan)

    def test_receipt_numbers_are_sequential_per_year(self):
        p1 = Payment.objects.create(enrollment=self.enrollment,
                                    amount=Decimal("900"), month=9,
                                    date=datetime.date(2026, 9, 1))
        p2 = Payment.objects.create(enrollment=self.enrollment,
                                    amount=Decimal("900"), month=10,
                                    date=datetime.date(2026, 10, 1))
        self.assertEqual(p1.receipt_number, "REC-2026-00001")
        self.assertEqual(p2.receipt_number, "REC-2026-00002")

    def test_annual_total(self):
        # 1000 + 150 + 900 × 10
        self.assertEqual(self.plan.annual_total, Decimal("10150"))

    def test_discount_applies_to_monthly_amount(self):
        self.enrollment.discount_pct = Decimal("10")
        self.assertEqual(expected_monthly_amount(self.enrollment),
                         Decimal("810.00"))

    def test_unpaid_months_tracks_tuition_payments(self):
        months = unpaid_months(self.enrollment)
        self.assertEqual(len(months), 10)
        self.assertEqual(months[0], 9)
        Payment.objects.create(enrollment=self.enrollment, month=9,
                               kind=Payment.Kind.TUITION,
                               amount=Decimal("900"),
                               date=datetime.date(2026, 9, 5))
        self.assertNotIn(9, unpaid_months(self.enrollment))

    def test_student_age(self):
        self.assertEqual(
            self.student.age,
            datetime.date.today().year - 2019
            - ((datetime.date.today().month, datetime.date.today().day) < (3, 15)))
