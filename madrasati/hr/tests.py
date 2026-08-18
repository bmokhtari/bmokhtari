"""Tests du calcul de paie marocain (CNSS, AMO, IR barème 2025)."""

from decimal import Decimal

from django.test import TestCase

from .models import Employee, PayrollRun
from .payroll import compute_payslip


class PayrollComputationTests(TestCase):
    def test_salary_below_ir_threshold_pays_no_tax(self):
        # 3 000 DH brut : sous le seuil d'exonération après frais pro.
        result = compute_payslip(Decimal("3000"))
        self.assertEqual(result["cnss"], Decimal("134.40"))   # 4,48 %
        self.assertEqual(result["amo"], Decimal("67.80"))     # 2,26 %
        self.assertEqual(result["ir"], Decimal("0.00"))
        self.assertEqual(result["net"], Decimal("2797.80"))

    def test_mid_salary_ir_bracket(self):
        # 8 000 DH brut, sans personne à charge.
        result = compute_payslip(Decimal("8000"))
        self.assertEqual(result["cnss"], Decimal("268.80"))   # plafonné à 6000 : 6000×4,48 %
        self.assertEqual(result["amo"], Decimal("180.80"))
        # Frais pro 25 % (brut > 6 500) : 2 000 → imposable 5 550,40
        self.assertEqual(result["taxable"], Decimal("5550.40"))
        # Tranche 20 % : 5550,40 × 0,20 − 833,33 = 276,75
        self.assertEqual(result["ir"], Decimal("276.75"))
        self.assertEqual(result["net"], Decimal("7273.65"))

    def test_cnss_capped_at_6000(self):
        result = compute_payslip(Decimal("20000"))
        self.assertEqual(result["cnss"], Decimal("268.80"))
        # AMO non plafonnée
        self.assertEqual(result["amo"], Decimal("452.00"))

    def test_family_deduction_reduces_ir(self):
        without = compute_payslip(Decimal("8000"), dependents=0)
        with_deps = compute_payslip(Decimal("8000"), dependents=2)
        self.assertEqual(without["ir"] - with_deps["ir"], Decimal("83.34"))

    def test_family_deduction_capped_at_six_persons(self):
        six = compute_payslip(Decimal("10000"), dependents=6)
        ten = compute_payslip(Decimal("10000"), dependents=10)
        self.assertEqual(six["ir"], ten["ir"])

    def test_ir_never_negative(self):
        result = compute_payslip(Decimal("4000"), dependents=6)
        self.assertGreaterEqual(result["ir"], Decimal("0.00"))

    def test_employer_cost_exceeds_gross(self):
        result = compute_payslip(Decimal("6000"))
        self.assertGreater(result["employer_cost"], result["gross"])


class PayrollRunTests(TestCase):
    def _make_employee(self, matricule, salary, active=True):
        return Employee.objects.create(
            matricule=matricule, first_name="Test", last_name=matricule,
            cin=f"T{matricule[-5:].zfill(5)}", phone="0612345678",
            base_salary=Decimal(salary), is_active=active,
        )

    def test_generate_payslips_only_for_active_employees(self):
        self._make_employee("EMP10", "6000")
        self._make_employee("EMP11", "8000")
        self._make_employee("EMP12", "5000", active=False)
        run = PayrollRun.objects.create(year=2026, month=9)
        created = run.generate_payslips()
        self.assertEqual(created, 2)
        self.assertEqual(run.payslips.count(), 2)

    def test_validated_run_is_immutable(self):
        self._make_employee("EMP20", "6000")
        run = PayrollRun.objects.create(year=2026, month=10)
        run.generate_payslips()
        run.status = PayrollRun.Status.VALIDATED
        run.save()
        self._make_employee("EMP21", "7000")
        self.assertEqual(run.generate_payslips(), 0)
        self.assertEqual(run.payslips.count(), 1)

    def test_payslip_snapshot_matches_computation(self):
        employee = self._make_employee("EMP30", "8000")
        run = PayrollRun.objects.create(year=2026, month=11)
        run.generate_payslips()
        payslip = run.payslips.get(employee=employee)
        expected = compute_payslip(employee.gross_salary, employee.dependents)
        self.assertEqual(payslip.net, expected["net"])
        self.assertEqual(payslip.ir, expected["ir"])
