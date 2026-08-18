from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from finance.models import overdue_months, overdue_total

from .models import Enrollment


@staff_member_required
def enrollment_certificate_view(request, enrollment_id):
    """Attestation de scolarité, délivrée si la scolarité est à jour.

    Règle de l'établissement : aucun document officiel n'est remis tant que
    des mensualités échues restent dues. Les reçus de paiement ne sont pas
    concernés — ils attestent de sommes déjà versées.
    """
    enrollment = get_object_or_404(
        Enrollment.objects.select_related(
            "student", "tuition_plan",
            "school_class__level", "school_class__academic_year",
        ),
        pk=enrollment_id,
    )

    today = timezone.localdate()
    unpaid = overdue_months(enrollment, today)
    if unpaid:
        context = {
            "enrollment": enrollment,
            "unpaid_months": unpaid,
            "unpaid_count": len(unpaid),
            "amount_due": overdue_total(enrollment, today),
            "document": _("attestation de scolarité"),
        }
        return render(request, "students/document_blocked.html", context,
                      status=403)

    return render(request, "students/certificate.html", {
        "enrollment": enrollment,
        "student": enrollment.student,
        "today": today,
    })
