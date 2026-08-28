"""Échéancier de scolarité : ce qu'une famille doit, et quand.

Le groupe applique deux modes de facturation :

* **enseignement général** — une mensualité sur les dix mois de l'année
  scolaire (septembre → juin), à laquelle s'ajoutent les frais annexes de
  début d'année (inscription FEA, manuels, fournitures, photocopies) ;
* **formation professionnelle et supérieure** — un montant annuel global,
  inscription comprise, que la famille échelonne en 3, 6 ou 10 versements.
  Les frais qui ont leur propre échéance, comme le diplôme, restent hors
  de cet étalement.

Régler la totalité comptant en début d'année ouvre droit à la remise de la
formule (10 % par défaut). Elle ne porte pas sur les frais à échéance
propre, qui ne sont pas payés d'avance.
"""

from decimal import Decimal, ROUND_HALF_UP

from .models import SCHOOL_MONTHS, Payment, expected_monthly_amount

CENT = Decimal("0.01")

# Mois de règlement selon l'échéancier retenu, dans l'ordre de l'année
# scolaire (septembre = 9).
INSTALMENT_MONTHS = {
    "three": [9, 12, 3],
    "six": [9, 11, 1, 3, 5, 6],
}


def _round(amount):
    return Decimal(amount).quantize(CENT, rounding=ROUND_HALF_UP)


def _school_months(plan):
    months = [month for month, _label in SCHOOL_MONTHS]
    return months[:plan.months_count] if plan.months_count else months


def billable_lines(enrollment):
    """Frais annexes facturés : obligatoires + optionnels retenus."""
    plan = enrollment.tuition_plan
    if plan is None:
        return []
    chosen = {line.pk for line in enrollment.optional_fees.all()}
    return [line for line in plan.lines.all()
            if line.mandatory or line.pk in chosen]


def tuition_total(enrollment):
    """Scolarité de l'année, remises d'inscription appliquées."""
    plan = enrollment.tuition_plan
    if plan is None:
        return Decimal("0.00")
    if plan.billing == plan.Billing.ANNUAL:
        from .models import effective_discount_pct
        pct = effective_discount_pct(enrollment)
        return _round(plan.annual_fee * (Decimal("1") - pct / Decimal("100")))
    return _round(sum((expected_monthly_amount(enrollment, month)
                       for month in _school_months(plan)), Decimal("0")))


def fee_schedule(enrollment):
    """Échéances attendues : [{mois, intitulé, montant, …}, …].

    Les entrées sont classées dans l'ordre de l'année scolaire.
    """
    plan = enrollment.tuition_plan
    if plan is None:
        return []

    months = _school_months(plan)
    first_month = months[0]
    lines = billable_lines(enrollment)
    spread_extras = sum((line.amount for line in lines if not line.is_separate),
                        Decimal("0"))
    separate = [line for line in lines if line.is_separate]

    entries = []
    payable = tuition_total(enrollment) + spread_extras
    upfront = enrollment.payment_plan == enrollment.PaymentPlan.UPFRONT

    if upfront:
        discount = plan.cash_discount_pct or Decimal("0")
        entries.append({
            "month": first_month,
            "label": _label_upfront(discount),
            "amount": _round(payable * (Decimal("1") - discount / Decimal("100"))),
            "separate": False,
        })
    elif enrollment.payment_plan == enrollment.PaymentPlan.MONTHLY:
        # Chaque mois porte sa mensualité ; les frais de rentrée s'ajoutent
        # à la première échéance.
        for index, month in enumerate(months):
            amount = (expected_monthly_amount(enrollment, month)
                      if plan.billing == plan.Billing.MONTHLY
                      else _round(tuition_total(enrollment) / len(months)))
            if index == 0:
                amount += spread_extras
            entries.append({"month": month, "label": _label_month(month),
                            "amount": _round(amount), "separate": False})
        entries = _absorb_rounding(entries, payable)
    else:
        due_months = INSTALMENT_MONTHS[enrollment.payment_plan]
        share = _round(payable / len(due_months))
        for position, month in enumerate(due_months, start=1):
            entries.append({
                "month": month,
                "label": _label_instalment(position, len(due_months)),
                "amount": share,
                "separate": False,
            })
        entries = _absorb_rounding(entries, payable)

    for line in separate:
        entries.append({"month": line.due_month, "label": line.title,
                        "amount": _round(line.amount), "separate": True})

    order = {month: index for index, month in enumerate(
        [m for m, _label in SCHOOL_MONTHS])}
    entries.sort(key=lambda entry: order.get(entry["month"], 99))
    return entries


def _absorb_rounding(entries, expected_total):
    """Reporte l'écart d'arrondi sur la dernière échéance."""
    if not entries:
        return entries
    difference = _round(expected_total) - sum(e["amount"] for e in entries)
    if difference:
        entries[-1]["amount"] = _round(entries[-1]["amount"] + difference)
    return entries


def _label_upfront(discount):
    from django.utils.translation import gettext as _

    if discount:
        return _("Règlement comptant (remise %(pct)s %%)") % {
            "pct": _trim(discount)}
    return _("Règlement comptant")


def _label_month(month):
    return dict(SCHOOL_MONTHS)[month]


def _label_instalment(position, total):
    from django.utils.translation import gettext as _

    return _("Versement %(n)d / %(total)d") % {"n": position, "total": total}


def _trim(value):
    text = f"{Decimal(value).normalize():f}"
    return text


def schedule_total(enrollment):
    return sum((entry["amount"] for entry in fee_schedule(enrollment)),
               Decimal("0.00"))


def paid_total(enrollment):
    return sum((payment.amount for payment in enrollment.payments.all()),
               Decimal("0.00"))


def due_entries(enrollment, today=None):
    """Échéances déjà exigibles à la date du jour."""
    from django.utils import timezone

    plan = enrollment.tuition_plan
    if plan is None:
        return []

    today = today or timezone.localdate()
    year = enrollment.school_class.academic_year
    schedule = fee_schedule(enrollment)

    if today >= year.end_date:
        return schedule
    if today < year.start_date:
        return []

    months = [m for m, _label in SCHOOL_MONTHS]
    if today.month in months:
        reached = set(months[:months.index(today.month) + 1])
        return [entry for entry in schedule if entry["month"] in reached]
    return schedule


def overdue_entries(enrollment, today=None):
    """Échéances exigibles que les versements ne couvrent pas encore.

    Les paiements sont imputés dans l'ordre des échéances, comme le ferait
    un caissier : la plus ancienne d'abord.
    """
    remaining = paid_total(enrollment)
    unpaid = []
    for entry in due_entries(enrollment, today):
        if remaining >= entry["amount"]:
            remaining -= entry["amount"]
            continue
        unpaid.append({**entry, "remaining": _round(entry["amount"] - remaining)})
        remaining = Decimal("0.00")
    return unpaid


def balance_due(enrollment, today=None):
    """Somme restant due sur les échéances déjà exigibles."""
    return sum((entry["remaining"] for entry in overdue_entries(enrollment, today)),
               Decimal("0.00"))
