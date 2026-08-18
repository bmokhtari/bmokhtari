"""Filtres d'affichage communs à l'interface de gestion."""

from decimal import Decimal, InvalidOperation

from django import template
from django.utils.html import format_html

register = template.Library()


@register.filter
def dirhams(value, decimals=0):
    """Montant en dirhams, groupé par milliers avec une espace insécable.

    Le format marocain (« 59 020 ») est conservé quelle que soit la langue
    de l'interface : les catalogues arabes de Django ne définissent pas de
    séparateur de milliers, et les montants perdaient leur lisibilité.
    """
    try:
        amount = Decimal(value or 0)
    except (TypeError, ValueError, InvalidOperation):
        return value
    formatted = f"{amount:,.{int(decimals)}f}".replace(",", " ")
    return formatted.replace(".", ",")


@register.filter
def dh(value, decimals=0):
    """Montant suivi de son unité, isolé du sens d'écriture.

    En arabe (RTL), « {{ x }} DH » se réordonnait en « DH 6 300 » : l'îlot
    directionnel fige l'ordre correct dans les deux langues.
    """
    return format_html('<span class="m-money" dir="ltr">{}\u00a0DH</span>',
                       dirhams(value, decimals))
