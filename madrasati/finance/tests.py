import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from core.models import AcademicYear, Level, SchoolClass
from students.models import Enrollment, Student
from .models import (Payment, TuitionPlan, expected_monthly_amount,
                     unpaid_months)


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


class AmountInWordsTests(TestCase):
    """Montants en toutes lettres — règles d'accord du français."""

    def test_simple_amounts(self):
        from .amount_words import amount_in_words
        self.assertEqual(amount_in_words(Decimal("1")), "un dirham")
        self.assertEqual(amount_in_words(Decimal("810")), "huit cent dix dirhams")
        self.assertEqual(amount_in_words(Decimal("1000")), "mille dirhams")

    def test_french_agreement_rules(self):
        from .amount_words import amount_in_words
        # « quatre-vingts » prend un -s isolé, pas devant mille
        self.assertEqual(amount_in_words(Decimal("80")), "quatre-vingts dirhams")
        self.assertEqual(amount_in_words(Decimal("180350")),
                         "cent quatre-vingt mille trois cent cinquante dirhams")
        # « cent » invariable devant mille
        self.assertEqual(amount_in_words(Decimal("200000")), "deux cent mille dirhams")
        self.assertEqual(amount_in_words(Decimal("200")), "deux cents dirhams")
        # « et un », « et onze »
        self.assertEqual(amount_in_words(Decimal("21")), "vingt et un dirhams")
        self.assertEqual(amount_in_words(Decimal("71")), "soixante et onze dirhams")
        # million est un nom : « de dirhams »
        self.assertEqual(amount_in_words(Decimal("1000000")), "un million de dirhams")

    def test_centimes(self):
        from .amount_words import amount_in_words
        self.assertEqual(amount_in_words(Decimal("1150.50")),
                         "mille cent cinquante dirhams et cinquante centimes")
        self.assertEqual(amount_in_words(Decimal("0.01")), "zéro dirham et un centime")


class DiscountRequestTests(TestCase):
    """Une remise ne s'applique qu'après approbation."""

    def setUp(self):
        self.year = AcademicYear.objects.create(
            name="2026-2027", start_date=datetime.date(2026, 9, 1),
            end_date=datetime.date(2027, 7, 10), is_current=True)
        self.level = Level.objects.create(
            cycle=Level.Cycle.PRIMARY, code="3AP",
            name_fr="3e année primaire", order=3)
        self.school_class = SchoolClass.objects.create(
            academic_year=self.year, level=self.level, name="A")
        self.plan = TuitionPlan.objects.create(
            academic_year=self.year, level=self.level,
            monthly_fee=Decimal("1000"), months_count=10)
        self.student = Student.objects.create(
            first_name="Hiba", last_name="Fassi", gender="F",
            birth_date=datetime.date(2018, 5, 4))
        self.enrollment = Enrollment.objects.create(
            student=self.student, school_class=self.school_class,
            tuition_plan=self.plan)

    def _request(self, **kwargs):
        from .models import DiscountRequest
        defaults = dict(enrollment=self.enrollment, percentage=Decimal("25"),
                        reason="Fratrie")
        return DiscountRequest.objects.create(**{**defaults, **kwargs})

    def test_pending_request_has_no_effect(self):
        self._request()
        self.assertEqual(expected_monthly_amount(self.enrollment, month=10),
                         Decimal("1000.00"))

    def test_approved_request_applies_to_the_whole_year(self):
        from .models import DiscountRequest
        discount = self._request()
        discount.decide(DiscountRequest.Status.APPROVED, None)
        for month in (9, 1, 6):
            self.assertEqual(expected_monthly_amount(self.enrollment, month=month),
                             Decimal("750.00"))

    def test_rejected_request_has_no_effect(self):
        from .models import DiscountRequest
        discount = self._request()
        discount.decide(DiscountRequest.Status.REJECTED, None)
        self.assertEqual(expected_monthly_amount(self.enrollment, month=10),
                         Decimal("1000.00"))

    def test_period_request_applies_only_within_its_months(self):
        from .models import DiscountRequest
        discount = self._request(scope=DiscountRequest.Scope.PERIOD,
                                 start_month=11, end_month=1)
        discount.decide(DiscountRequest.Status.APPROVED, None)
        # Novembre → janvier : couverts ; octobre et février : non.
        self.assertEqual(expected_monthly_amount(self.enrollment, month=11),
                         Decimal("750.00"))
        self.assertEqual(expected_monthly_amount(self.enrollment, month=1),
                         Decimal("750.00"))
        self.assertEqual(expected_monthly_amount(self.enrollment, month=10),
                         Decimal("1000.00"))
        self.assertEqual(expected_monthly_amount(self.enrollment, month=2),
                         Decimal("1000.00"))

    def test_permanent_discount_is_kept_when_more_favourable(self):
        from .models import DiscountRequest
        self.enrollment.discount_pct = Decimal("30")
        self.enrollment.save()
        discount = self._request(percentage=Decimal("10"))
        discount.decide(DiscountRequest.Status.APPROVED, None)
        self.assertEqual(expected_monthly_amount(self.enrollment, month=10),
                         Decimal("700.00"))

    def test_period_needs_both_months(self):
        from .models import DiscountRequest
        discount = DiscountRequest(enrollment=self.enrollment,
                                   percentage=Decimal("20"), reason="Bourse",
                                   scope=DiscountRequest.Scope.PERIOD)
        with self.assertRaises(ValidationError):
            discount.full_clean()

    def test_period_months_must_follow_the_school_year_order(self):
        from .models import DiscountRequest
        discount = DiscountRequest(enrollment=self.enrollment,
                                   percentage=Decimal("20"), reason="Bourse",
                                   scope=DiscountRequest.Scope.PERIOD,
                                   start_month=2, end_month=11)
        with self.assertRaises(ValidationError):
            discount.full_clean()


class DiscountApprovalPermissionTests(TestCase):
    """Seuls les comptes habilités peuvent trancher une demande."""

    def setUp(self):
        from django.contrib.auth.models import Permission, User
        from .models import DiscountRequest

        year = AcademicYear.objects.create(
            name="2026-2027", start_date=datetime.date(2026, 9, 1),
            end_date=datetime.date(2027, 7, 10), is_current=True)
        level = Level.objects.create(cycle=Level.Cycle.PRIMARY, code="4AP",
                                     name_fr="4e année primaire", order=4)
        school_class = SchoolClass.objects.create(
            academic_year=year, level=level, name="A")
        plan = TuitionPlan.objects.create(academic_year=year, level=level,
                                          monthly_fee=Decimal("900"))
        student = Student.objects.create(first_name="Omar", last_name="Idrissi",
                                         gender="M",
                                         birth_date=datetime.date(2017, 2, 2))
        enrollment = Enrollment.objects.create(student=student,
                                               school_class=school_class,
                                               tuition_plan=plan)
        self.discount = DiscountRequest.objects.create(
            enrollment=enrollment, percentage=Decimal("20"), reason="Fratrie")

        # Secrétaire : peut saisir les demandes, pas les approuver.
        self.secretary = User.objects.create_user(
            "secretaire", password="x", is_staff=True)
        self.secretary.user_permissions.add(
            *Permission.objects.filter(
                codename__in=["view_discountrequest", "add_discountrequest",
                              "change_discountrequest"]))
        # Direction : peut approuver.
        self.director = User.objects.create_user(
            "direction", password="x", is_staff=True)
        self.director.user_permissions.add(
            *Permission.objects.filter(
                codename__in=["view_discountrequest", "change_discountrequest",
                              "approve_discountrequest"]))

    def _post_action(self, user, action):
        self.client.force_login(user)
        return self.client.post(
            "/admin/finance/discountrequest/",
            {"action": action, "_selected_action": [str(self.discount.pk)],
             "index": "0"}, follow=True)

    def test_secretary_cannot_approve(self):
        from .models import DiscountRequest
        self._post_action(self.secretary, "approve_selected")
        self.discount.refresh_from_db()
        self.assertEqual(self.discount.status, DiscountRequest.Status.PENDING)

    def test_director_can_approve(self):
        from .models import DiscountRequest
        self._post_action(self.director, "approve_selected")
        self.discount.refresh_from_db()
        self.assertEqual(self.discount.status, DiscountRequest.Status.APPROVED)
        self.assertEqual(self.discount.decided_by, self.director)
        self.assertIsNotNone(self.discount.decided_on)

    def test_decided_request_is_not_reopened(self):
        from .models import DiscountRequest
        self._post_action(self.director, "approve_selected")
        self._post_action(self.director, "reject_selected")
        self.discount.refresh_from_db()
        self.assertEqual(self.discount.status, DiscountRequest.Status.APPROVED)
