"""Échéanciers : enseignement général au mois, formations à l'année."""

import datetime
from decimal import Decimal

from django.test import TestCase

from core.models import AcademicYear, Level, School, SchoolClass
from students.models import Enrollment, Student

from .models import FeeLine, Payment, TuitionPlan
from .schedule import (balance_due, fee_schedule, overdue_entries,
                       schedule_total, tuition_total)


class ScheduleTestCase(TestCase):
    def setUp(self):
        self.year = AcademicYear.objects.create(
            name="2026-2027", start_date=datetime.date(2026, 9, 1),
            end_date=datetime.date(2027, 7, 10), is_current=True)
        self.student = Student.objects.create(
            first_name="Yasmine", last_name="Idrissi", gender="F",
            birth_date=datetime.date(2010, 3, 3))

    def _enrol(self, plan, school, level, **kwargs):
        school_class = SchoolClass.objects.create(
            school=school, academic_year=self.year, level=level, name="A")
        return Enrollment.objects.create(student=self.student,
                                         school_class=school_class,
                                         tuition_plan=plan, **kwargs)


class GeneralEducationScheduleTests(ScheduleTestCase):
    """Tahadi & co : mensualité sur dix mois, frais de rentrée en septembre."""

    def setUp(self):
        super().setUp()
        self.school = School.objects.create(
            name="Tahadi", programme=School.Programme.GENERAL)
        self.level = Level.objects.create(cycle=Level.Cycle.PRIMARY,
                                          code="2AP", name_fr="2e année",
                                          order=2)
        self.plan = TuitionPlan.objects.create(
            academic_year=self.year, level=self.level, school=self.school,
            billing=TuitionPlan.Billing.MONTHLY,
            monthly_fee=Decimal("900"), months_count=10,
            cash_discount_pct=Decimal("10"))
        self.fea = FeeLine.objects.create(
            plan=self.plan, kind=FeeLine.Kind.REGISTRATION,
            amount=Decimal("1000"))
        self.books_a = FeeLine.objects.create(
            plan=self.plan, kind=FeeLine.Kind.BOOKS_A, amount=Decimal("600"))
        self.books_d = FeeLine.objects.create(
            plan=self.plan, kind=FeeLine.Kind.BOOKS_D, amount=Decimal("350"),
            mandatory=False)

    def test_monthly_plan_spreads_tuition_and_charges_entry_fees_upfront(self):
        enrollment = self._enrol(self.plan, self.school, self.level)
        schedule = fee_schedule(enrollment)
        self.assertEqual(len(schedule), 10)
        # Septembre : mensualité + inscription + manuels obligatoires.
        self.assertEqual(schedule[0]["month"], 9)
        self.assertEqual(schedule[0]["amount"], Decimal("2500.00"))
        self.assertEqual(schedule[1]["amount"], Decimal("900.00"))
        self.assertEqual(schedule_total(enrollment), Decimal("10600.00"))

    def test_list_d_is_billed_only_when_bought_from_the_school(self):
        enrollment = self._enrol(self.plan, self.school, self.level)
        self.assertEqual(schedule_total(enrollment), Decimal("10600.00"))
        enrollment.optional_fees.add(self.books_d)
        self.assertEqual(schedule_total(enrollment), Decimal("10950.00"))

    def test_paying_upfront_earns_the_cash_discount(self):
        enrollment = self._enrol(
            self.plan, self.school, self.level,
            payment_plan=Enrollment.PaymentPlan.UPFRONT)
        schedule = fee_schedule(enrollment)
        self.assertEqual(len(schedule), 1)
        self.assertEqual(schedule[0]["month"], 9)
        # 10 600 DH − 10 %
        self.assertEqual(schedule[0]["amount"], Decimal("9540.00"))

    def test_student_discount_applies_to_tuition_only(self):
        enrollment = self._enrol(self.plan, self.school, self.level,
                                 discount_pct=Decimal("10"))
        # Scolarité 9 000 − 10 % = 8 100, frais de rentrée inchangés.
        self.assertEqual(tuition_total(enrollment), Decimal("8100.00"))
        self.assertEqual(schedule_total(enrollment), Decimal("9700.00"))


class VocationalScheduleTests(ScheduleTestCase):
    """ESTEP : montant annuel, diplôme à part au 6e mois, 3/6/10 versements."""

    def setUp(self):
        super().setUp()
        self.school = School.objects.create(
            name="ESTEP", programme=School.Programme.VOCATIONAL)
        self.level = Level.objects.create(cycle=Level.Cycle.VOCATIONAL,
                                          code="TS1",
                                          name_fr="Technicien spécialisé 1",
                                          order=20)
        self.plan = TuitionPlan.objects.create(
            academic_year=self.year, level=self.level, school=self.school,
            billing=TuitionPlan.Billing.ANNUAL,
            annual_fee=Decimal("24000"), monthly_fee=Decimal("0"),
            months_count=10, cash_discount_pct=Decimal("10"))
        # Le diplôme se règle séparément, au sixième mois (février).
        self.diploma = FeeLine.objects.create(
            plan=self.plan, kind=FeeLine.Kind.DIPLOMA, amount=Decimal("1500"),
            due_month=2)

    def test_annual_amount_covers_registration_and_the_year(self):
        enrollment = self._enrol(self.plan, self.school, self.level)
        self.assertEqual(tuition_total(enrollment), Decimal("24000.00"))

    def test_three_instalments(self):
        enrollment = self._enrol(self.plan, self.school, self.level,
                                 payment_plan=Enrollment.PaymentPlan.THREE)
        schedule = fee_schedule(enrollment)
        instalments = [e for e in schedule if not e["separate"]]
        self.assertEqual([e["month"] for e in instalments], [9, 12, 3])
        self.assertEqual([e["amount"] for e in instalments],
                         [Decimal("8000.00")] * 3)

    def test_six_instalments(self):
        enrollment = self._enrol(self.plan, self.school, self.level,
                                 payment_plan=Enrollment.PaymentPlan.SIX)
        instalments = [e for e in fee_schedule(enrollment) if not e["separate"]]
        self.assertEqual(len(instalments), 6)
        self.assertEqual(sum(e["amount"] for e in instalments),
                         Decimal("24000.00"))

    def test_diploma_is_billed_apart_in_the_sixth_month(self):
        enrollment = self._enrol(self.plan, self.school, self.level,
                                 payment_plan=Enrollment.PaymentPlan.THREE)
        schedule = fee_schedule(enrollment)
        diploma = [e for e in schedule if e["separate"]]
        self.assertEqual(len(diploma), 1)
        self.assertEqual(diploma[0]["month"], 2)
        self.assertEqual(diploma[0]["amount"], Decimal("1500.00"))
        self.assertEqual(schedule_total(enrollment), Decimal("25500.00"))

    def test_cash_discount_spares_the_diploma(self):
        enrollment = self._enrol(self.plan, self.school, self.level,
                                 payment_plan=Enrollment.PaymentPlan.UPFRONT)
        schedule = fee_schedule(enrollment)
        upfront = [e for e in schedule if not e["separate"]][0]
        diploma = [e for e in schedule if e["separate"]][0]
        self.assertEqual(upfront["amount"], Decimal("21600.00"))  # 24 000 − 10 %
        self.assertEqual(diploma["amount"], Decimal("1500.00"))

    def test_instalments_absorb_rounding(self):
        self.plan.annual_fee = Decimal("24001")
        self.plan.save()
        enrollment = self._enrol(self.plan, self.school, self.level,
                                 payment_plan=Enrollment.PaymentPlan.THREE)
        instalments = [e for e in fee_schedule(enrollment) if not e["separate"]]
        self.assertEqual(sum(e["amount"] for e in instalments),
                         Decimal("24001.00"))


class ArrearsTests(ScheduleTestCase):
    """Le retard se mesure sur les échéances exigibles, pas sur les mois."""

    def setUp(self):
        super().setUp()
        school = School.objects.create(name="Thomas Jefferson",
                                       programme=School.Programme.GENERAL)
        level = Level.objects.create(cycle=Level.Cycle.MIDDLE, code="1AC",
                                     name_fr="1re collège", order=10)
        plan = TuitionPlan.objects.create(
            academic_year=self.year, level=level, school=school,
            billing=TuitionPlan.Billing.MONTHLY, monthly_fee=Decimal("1000"),
            months_count=10)
        self.enrollment = self._enrol(plan, school, level)
        self.mid_year = datetime.date(2026, 11, 15)

    def test_payments_are_applied_to_the_oldest_instalments_first(self):
        Payment.objects.create(enrollment=self.enrollment,
                               kind=Payment.Kind.TUITION, month=9,
                               amount=Decimal("1000"),
                               date=datetime.date(2026, 9, 4))
        unpaid = overdue_entries(self.enrollment, self.mid_year)
        # Septembre (1 000) est couvert ; octobre et novembre restent dus.
        self.assertEqual([entry["month"] for entry in unpaid], [10, 11])
        self.assertEqual(balance_due(self.enrollment, self.mid_year),
                         Decimal("2000.00"))

    def test_no_arrears_before_the_school_year_starts(self):
        self.assertEqual(overdue_entries(self.enrollment,
                                         datetime.date(2026, 8, 20)), [])

    def test_a_partial_payment_leaves_the_remainder_due(self):
        Payment.objects.create(enrollment=self.enrollment,
                               kind=Payment.Kind.TUITION, month=9,
                               amount=Decimal("400"),
                               date=datetime.date(2026, 9, 4))
        unpaid = overdue_entries(self.enrollment, datetime.date(2026, 9, 20))
        self.assertEqual(len(unpaid), 1)
        self.assertEqual(unpaid[0]["remaining"], Decimal("600.00"))
