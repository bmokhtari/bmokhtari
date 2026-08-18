from django.contrib import admin
from django.urls import path
from django.utils.translation import gettext_lazy as _
from django.views.generic import RedirectView

from finance.views import receipt_view
from hr.views import payslip_view

admin.site.site_header = _("Madrasati — Gestion d'école")
admin.site.site_title = _("Madrasati")
admin.site.index_title = _("Tableau de bord")
admin.site.index_template = "admin/dashboard_index.html"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="admin:index", permanent=False)),
    path("finance/recu/<int:payment_id>/", receipt_view, name="payment-receipt"),
    path("hr/bulletin/<int:payslip_id>/", payslip_view, name="payslip"),
    path("admin/", admin.site.urls),
]
