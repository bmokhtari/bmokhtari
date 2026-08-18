from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render

from .models import Payment


@staff_member_required
def receipt_view(request, payment_id):
    """Reçu de paiement imprimable (bilingue français/arabe)."""
    payment = get_object_or_404(
        Payment.objects.select_related(
            "enrollment__student",
            "enrollment__school_class__level",
            "enrollment__school_class__academic_year",
        ),
        pk=payment_id,
    )
    return render(request, "finance/receipt.html", {"payment": payment})
