from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render

from .models import Payslip


@staff_member_required
def payslip_view(request, payslip_id):
    """Bulletin de paie imprimable (bilingue français/arabe)."""
    payslip = get_object_or_404(
        Payslip.objects.select_related("employee", "payroll_run"),
        pk=payslip_id,
    )
    return render(request, "hr/payslip.html", {"payslip": payslip})
