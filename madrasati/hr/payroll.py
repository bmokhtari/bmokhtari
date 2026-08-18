"""
Calcul de paie selon la réglementation marocaine.

Références (à jour Loi de finances 2025) :
- CNSS part salariale : 4,48 % du brut, plafonné à 6 000 DH/mois.
- AMO part salariale : 2,26 % du brut, non plafonné.
- Frais professionnels : 35 % si brut imposable mensuel ≤ 6 500 DH,
  sinon 25 %, plafonnés à 2 916,67 DH/mois (35 000 DH/an).
- IR barème mensuel 2025 (LF 2025) — voir IR_BRACKETS.
- Charges de famille : 41,67 DH/mois (500 DH/an) par personne à charge,
  maximum 6 personnes.

Les taux sont regroupés ici en constantes pour suivre facilement les
évolutions des lois de finances.
"""

from decimal import Decimal, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")

# --- Cotisations sociales (part salariale) ---------------------------------
CNSS_EMPLOYEE_RATE = Decimal("0.0448")
CNSS_MONTHLY_CAP = Decimal("6000.00")          # plafond d'assiette CNSS
AMO_EMPLOYEE_RATE = Decimal("0.0226")

# --- Cotisations patronales (coût employeur) --------------------------------
CNSS_EMPLOYER_SOCIAL_RATE = Decimal("0.0898")  # prestations sociales (plafonné)
CNSS_FAMILY_ALLOWANCE_RATE = Decimal("0.0640")  # allocations familiales
AMO_EMPLOYER_RATE = Decimal("0.0411")
TRAINING_TAX_RATE = Decimal("0.0160")           # taxe de formation professionnelle

# --- Frais professionnels ----------------------------------------------------
PRO_EXPENSES_HIGH_RATE = Decimal("0.35")   # brut imposable ≤ seuil
PRO_EXPENSES_LOW_RATE = Decimal("0.25")
PRO_EXPENSES_THRESHOLD = Decimal("6500.00")
PRO_EXPENSES_MONTHLY_CAP = Decimal("2916.67")   # 35 000 DH / an

# --- IR : barème mensuel 2025 (borne supérieure, taux, somme à déduire) -----
IR_BRACKETS = [
    (Decimal("3333.33"), Decimal("0.00"), Decimal("0.00")),
    (Decimal("5000.00"), Decimal("0.10"), Decimal("333.33")),
    (Decimal("6666.67"), Decimal("0.20"), Decimal("833.33")),
    (Decimal("8333.33"), Decimal("0.30"), Decimal("1500.00")),
    (Decimal("15000.00"), Decimal("0.34"), Decimal("1833.33")),
    (None, Decimal("0.37"), Decimal("2283.33")),
]

# --- Charges de famille ------------------------------------------------------
FAMILY_DEDUCTION_PER_PERSON = Decimal("41.67")  # 500 DH/an
FAMILY_DEDUCTION_MAX_PERSONS = 6


def _round(value):
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def compute_payslip(gross_salary, dependents=0):
    """Calcule un bulletin de paie mensuel marocain.

    :param gross_salary: salaire brut mensuel en DH (salaire de base + primes
        imposables).
    :param dependents: personnes à charge (conjoint et enfants), max 6 prises
        en compte.
    :return: dict avec toutes les lignes du bulletin, en ``Decimal``.
    """
    gross = Decimal(gross_salary)

    # Cotisations salariales
    cnss_base = min(gross, CNSS_MONTHLY_CAP)
    cnss = _round(cnss_base * CNSS_EMPLOYEE_RATE)
    amo = _round(gross * AMO_EMPLOYEE_RATE)

    # Frais professionnels
    pro_rate = (PRO_EXPENSES_HIGH_RATE if gross <= PRO_EXPENSES_THRESHOLD
                else PRO_EXPENSES_LOW_RATE)
    pro_expenses = min(_round(gross * pro_rate), PRO_EXPENSES_MONTHLY_CAP)

    # Salaire net imposable
    taxable = gross - pro_expenses - cnss - amo
    if taxable < 0:
        taxable = Decimal("0.00")

    # IR brut (barème progressif par somme à déduire)
    ir_gross = Decimal("0.00")
    for upper, rate, deduction in IR_BRACKETS:
        if upper is None or taxable <= upper:
            ir_gross = _round(taxable * rate - deduction)
            break
    if ir_gross < 0:
        ir_gross = Decimal("0.00")

    # Déduction pour charges de famille
    persons = min(int(dependents or 0), FAMILY_DEDUCTION_MAX_PERSONS)
    family_deduction = _round(FAMILY_DEDUCTION_PER_PERSON * persons)
    ir_net = max(ir_gross - family_deduction, Decimal("0.00"))

    net_salary = _round(gross - cnss - amo - ir_net)

    # Coût employeur
    employer_cnss = _round(cnss_base * CNSS_EMPLOYER_SOCIAL_RATE)
    employer_family = _round(gross * CNSS_FAMILY_ALLOWANCE_RATE)
    employer_amo = _round(gross * AMO_EMPLOYER_RATE)
    employer_training = _round(gross * TRAINING_TAX_RATE)
    employer_cost = _round(gross + employer_cnss + employer_family
                           + employer_amo + employer_training)

    return {
        "gross": _round(gross),
        "cnss": cnss,
        "amo": amo,
        "pro_expenses": pro_expenses,
        "taxable": _round(taxable),
        "ir_gross": ir_gross,
        "family_deduction": family_deduction,
        "ir": ir_net,
        "net": net_salary,
        "employer_cnss": employer_cnss,
        "employer_family": employer_family,
        "employer_amo": employer_amo,
        "employer_training": employer_training,
        "employer_cost": employer_cost,
    }
