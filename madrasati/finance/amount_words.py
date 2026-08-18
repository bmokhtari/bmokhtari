"""Montants en toutes lettres (français), pour les reçus officiels."""

from decimal import Decimal

UNITS = [
    "zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit",
    "neuf", "dix", "onze", "douze", "treize", "quatorze", "quinze", "seize",
    "dix-sept", "dix-huit", "dix-neuf",
]
TENS = {
    20: "vingt", 30: "trente", 40: "quarante", 50: "cinquante",
    60: "soixante", 80: "quatre-vingt",
}


def _below_hundred(n, invariable=False):
    """*invariable* : « quatre-vingt » ne prend pas de -s devant mille."""
    if n < 20:
        return UNITS[n]
    if n < 70 or 80 <= n < 100:
        ten = 80 if n >= 80 else n // 10 * 10
        rest = n - ten
        word = TENS[ten]
        if rest == 0:
            return word + ("s" if ten == 80 and not invariable else "")
        if rest == 1 and ten != 80:
            return f"{word} et un"
        return f"{word}-{UNITS[rest]}"
    # 70-79 et 90-99 : soixante-dix…, quatre-vingt-dix…
    base = 60 if n < 80 else 80
    rest = n - base
    word = TENS[base]
    if rest == 11 and base == 60:
        return f"{word} et onze"
    return f"{word}-{UNITS[rest]}"


def _below_thousand(n, invariable=False):
    """*invariable* : « cent » reste invariable devant mille (deux cent mille)."""
    hundreds, rest = divmod(n, 100)
    parts = []
    if hundreds == 1:
        parts.append("cent")
    elif hundreds > 1:
        plural = "s" if rest == 0 and not invariable else ""
        parts.append(f"{UNITS[hundreds]} cent{plural}")
    if rest:
        parts.append(_below_hundred(rest, invariable))
    return " ".join(parts)


def number_in_words(n):
    """Entier positif en toutes lettres (jusqu'à 999 999 999)."""
    n = int(n)
    if n == 0:
        return "zéro"

    parts = []
    millions, rest = divmod(n, 1_000_000)
    if millions:
        prefix = "un" if millions == 1 else number_in_words(millions)
        parts.append(f"{prefix} million" + ("s" if millions > 1 else ""))

    thousands, units = divmod(rest, 1000)
    if thousands == 1:
        parts.append("mille")
    elif thousands > 1:
        parts.append(f"{_below_thousand(thousands, invariable=True)} mille")
    if units:
        parts.append(_below_thousand(units))
    return " ".join(parts)


def amount_in_words(amount):
    """Montant en dirhams et centimes, en toutes lettres.

    >>> amount_in_words(Decimal("810.00"))
    'huit cent dix dirhams'
    """
    amount = Decimal(amount).quantize(Decimal("0.01"))
    dirhams = int(amount)
    centimes = int((amount - dirhams) * 100)

    spelled = number_in_words(dirhams)
    # « million » et « milliard » sont des noms : un million DE dirhams.
    if spelled.endswith(("million", "millions")):
        words = f"{spelled} de dirhams"
    else:
        words = f"{spelled} dirham" + ("s" if dirhams > 1 else "")
    if centimes:
        words += (f" et {number_in_words(centimes)} centime"
                  + ("s" if centimes > 1 else ""))
    return words
