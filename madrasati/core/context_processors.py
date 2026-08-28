from django.conf import settings


def school(request):
    """Expose l'en-tête de l'établissement aux documents imprimables."""
    return {"school": settings.SCHOOL}
