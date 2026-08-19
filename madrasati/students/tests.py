from django.test import TestCase

# Create your tests here.
import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import AcademicYear, Level, SchoolClass
from finance.models import Payment, TuitionPlan, overdue_months
from .models import (BehaviourRecord, BehaviourType, Enrollment,
                     Student)


class DocumentGatingTests(TestCase):
    """Aucun document officiel tant que la scolarité n'est pas à jour."""

    def setUp(self):
        # Année scolaire entièrement écoulée : les dix mensualités sont dues,
        # quelle que soit la date à laquelle les tests s'exécutent.
        today = datetime.date.today()
        self.year = AcademicYear.objects.create(
            name=f"{today.year - 2}-{today.year - 1}",
            start_date=datetime.date(today.year - 2, 9, 1),
            end_date=datetime.date(today.year - 1, 7, 10), is_current=True)
        level = Level.objects.create(cycle=Level.Cycle.PRIMARY, code="6AP",
                                     name_fr="6e année primaire", order=6)
        self.school_class = SchoolClass.objects.create(
            academic_year=self.year, level=level, name="A")
        plan = TuitionPlan.objects.create(academic_year=self.year, level=level,
                                          monthly_fee=Decimal("900"),
                                          months_count=10)
        student = Student.objects.create(
            first_name="Sofia", last_name="Lahlou", gender="F",
            birth_date=datetime.date(2015, 4, 12), massar_code="G777888999")
        self.enrollment = Enrollment.objects.create(
            student=student, school_class=self.school_class, tuition_plan=plan)

        User.objects.create_superuser("dir", "d@example.com", "x")
        self.client.force_login(User.objects.get(username="dir"))
        self.url = reverse("enrollment-certificate", args=[self.enrollment.pk])

    def _pay(self, *months):
        start = self.year.start_date.year
        for month in months:
            year = start if month >= 9 else start + 1
            Payment.objects.create(
                enrollment=self.enrollment, kind=Payment.Kind.TUITION,
                month=month, amount=Decimal("900"),
                date=datetime.date(year, month, 5))

    def test_certificate_is_refused_when_months_are_due(self):
        # Sans aucun paiement, l'attestation est bloquée.
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "students/document_blocked.html")
        self.assertContains(response, "Document indisponible", status_code=403)

    def test_certificate_is_issued_once_the_family_is_up_to_date(self):
        self._pay(*[m for m in (9, 10, 11, 12, 1, 2, 3, 4, 5, 6)])
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "students/certificate.html")
        self.assertContains(response, "Sofia Lahlou")
        self.assertContains(response, "G777888999")

    def test_receipts_stay_available_despite_arrears(self):
        # Un reçu constate un versement déjà encaissé : il n'est pas bloqué.
        self._pay(9)
        payment = Payment.objects.get(enrollment=self.enrollment, month=9)
        self.assertTrue(overdue_months(self.enrollment))
        response = self.client.get(reverse("payment-receipt", args=[payment.pk]))
        self.assertEqual(response.status_code, 200)

    def test_blocked_page_lists_the_months_and_the_amount(self):
        self._pay(9, 10)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.context["unpaid_count"],
                         len(overdue_months(self.enrollment)))
        self.assertGreater(response.context["amount_due"], 0)


class BehaviourRecordTests(TestCase):
    """Vie scolaire : natures gérées en base, positives comme négatives."""

    def setUp(self):
        year = AcademicYear.objects.create(
            name="2026-2027", start_date=datetime.date(2026, 9, 1),
            end_date=datetime.date(2027, 7, 10), is_current=True)
        level = Level.objects.create(cycle=Level.Cycle.MIDDLE, code="1AC",
                                     name_fr="1re année collège", order=10)
        school_class = SchoolClass.objects.create(academic_year=year,
                                                  level=level, name="A")
        student = Student.objects.create(
            first_name="Mehdi", last_name="Kettani", gender="M",
            birth_date=datetime.date(2013, 9, 1))
        self.enrollment = Enrollment.objects.create(student=student,
                                                    school_class=school_class)

    def test_common_types_are_available_out_of_the_box(self):
        # La migration de données installe les cas courants.
        self.assertGreaterEqual(BehaviourType.objects.count(), 15)
        self.assertTrue(BehaviourType.objects.filter(
            name="Bavardage répété", is_negative=True).exists())
        self.assertTrue(BehaviourType.objects.filter(
            name="Félicitations", is_negative=False).exists())

    def test_negative_and_positive_records_are_distinguished(self):
        warning = BehaviourRecord.objects.create(
            enrollment=self.enrollment,
            type=BehaviourType.objects.get(name="Avertissement"),
            summary="Bavardage répété")
        praise = BehaviourRecord.objects.create(
            enrollment=self.enrollment,
            type=BehaviourType.objects.get(name="Félicitations"),
            summary="Aide apportée à un camarade")
        self.assertTrue(warning.is_negative)
        self.assertFalse(praise.is_negative)

    def test_a_new_type_is_kept_for_later_use(self):
        # Une nature saisie par l'équipe reste disponible ensuite.
        created = BehaviourType.objects.create(name="Sortie non autorisée",
                                               is_negative=True)
        BehaviourRecord.objects.create(enrollment=self.enrollment,
                                       type=created, summary="Sortie à 10h")
        self.assertIn(created, BehaviourType.objects.filter(is_active=True))
        self.assertEqual(created.records.count(), 1)

    def test_a_type_in_use_cannot_be_deleted(self):
        from django.db.models import ProtectedError

        used = BehaviourType.objects.get(name="Remarque")
        BehaviourRecord.objects.create(enrollment=self.enrollment, type=used,
                                       summary="Oubli de cahier")
        with self.assertRaises(ProtectedError):
            used.delete()

    def test_records_are_listed_most_recent_first(self):
        remark = BehaviourType.objects.get(name="Remarque")
        older = BehaviourRecord.objects.create(
            enrollment=self.enrollment, type=remark, summary="Retard",
            date=datetime.date(2026, 10, 1))
        newer = BehaviourRecord.objects.create(
            enrollment=self.enrollment, type=remark,
            summary="Oubli de matériel", date=datetime.date(2026, 11, 4))
        self.assertEqual(list(self.enrollment.behaviour_records.all()),
                         [newer, older])


class EnrollmentAdminFormTests(TestCase):
    """Les frais optionnels proposés sont ceux de la formule de l'élève."""

    def setUp(self):
        from core.models import School
        from finance.models import FeeLine, TuitionPlan

        year = AcademicYear.objects.create(
            name="2026-2027", start_date=datetime.date(2026, 9, 1),
            end_date=datetime.date(2027, 7, 10), is_current=True)
        level = Level.objects.create(cycle=Level.Cycle.PRIMARY, code="3AP",
                                     name_fr="3e année", order=3)
        tahadi = School.objects.create(name="Tahadi")
        jefferson = School.objects.create(name="Thomas Jefferson")

        self.plan = TuitionPlan.objects.create(
            academic_year=year, level=level, school=tahadi,
            monthly_fee=Decimal("900"))
        self.mine = FeeLine.objects.create(
            plan=self.plan, kind=FeeLine.Kind.BOOKS_D, amount=Decimal("350"),
            mandatory=False)
        other_plan = TuitionPlan.objects.create(
            academic_year=year, level=level, school=jefferson,
            monthly_fee=Decimal("950"))
        self.theirs = FeeLine.objects.create(
            plan=other_plan, kind=FeeLine.Kind.BOOKS_D, amount=Decimal("400"),
            mandatory=False)

        school_class = SchoolClass.objects.create(
            school=tahadi, academic_year=year, level=level, name="A")
        student = Student.objects.create(
            first_name="Nour", last_name="Sabri", gender="F",
            birth_date=datetime.date(2017, 6, 1))
        self.enrollment = Enrollment.objects.create(
            student=student, school_class=school_class, tuition_plan=self.plan)

    def test_only_the_plan_s_optional_lines_are_offered(self):
        from django.contrib.admin.sites import site
        from django.test import RequestFactory

        from .admin import EnrollmentAdmin
        from .models import Enrollment as EnrollmentModel

        admin_instance = EnrollmentAdmin(EnrollmentModel, site)
        request = RequestFactory().get("/")
        request.user = User.objects.create_superuser("staff", "s@e.com", "x")
        form = admin_instance.get_form(request, self.enrollment)()
        offered = list(form.fields["optional_fees"].queryset)
        self.assertIn(self.mine, offered)
        self.assertNotIn(self.theirs, offered)
