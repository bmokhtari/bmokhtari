"""Garde-fous sur la configuration de déploiement."""

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings


@override_settings(
    ALLOWED_HOSTS=["ecole.example.com"],
    CSRF_TRUSTED_ORIGINS=["https://ecole.example.com"],
    SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
    SECURE_SSL_REDIRECT=False,
)
class ProxiedLoginTests(TestCase):
    """Connexion derrière un proxy TLS (Render, Railway, nginx…).

    Sans en-tête de proxy ni origine de confiance, Django compare
    « https://… » (navigateur) à « http://… » (sa propre vue) et répond
    « La vérification CSRF a échoué » sur le formulaire de connexion.
    """

    def setUp(self):
        User.objects.create_superuser("directrice", "d@example.com", "motdepasse")
        self.client = Client(enforce_csrf_checks=True)

    def _login_post(self, **extra):
        page = self.client.get("/admin/login/", HTTP_HOST="ecole.example.com",
                               HTTP_X_FORWARDED_PROTO="https")
        token = page.cookies["csrftoken"].value
        return self.client.post(
            "/admin/login/",
            {"username": "directrice", "password": "motdepasse",
             "csrfmiddlewaretoken": token, "next": "/admin/"},
            HTTP_HOST="ecole.example.com",
            HTTP_ORIGIN="https://ecole.example.com",
            HTTP_X_FORWARDED_PROTO="https",
            **extra,
        )

    def test_https_login_behind_proxy_is_accepted(self):
        response = self._login_post()
        self.assertNotEqual(response.status_code, 403,
                            "La vérification CSRF rejette la connexion HTTPS.")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/admin/")

    def test_unknown_origin_is_still_rejected(self):
        page = self.client.get("/admin/login/", HTTP_HOST="ecole.example.com",
                               HTTP_X_FORWARDED_PROTO="https")
        token = page.cookies["csrftoken"].value
        response = self.client.post(
            "/admin/login/",
            {"username": "directrice", "password": "motdepasse",
             "csrfmiddlewaretoken": token},
            HTTP_HOST="ecole.example.com",
            HTTP_ORIGIN="https://site-malveillant.example",
            HTTP_X_FORWARDED_PROTO="https",
        )
        self.assertEqual(response.status_code, 403)


class EmptyChangeListTests(TestCase):
    """Une liste vide ne doit afficher ni cadre ni barre sans contenu."""

    def setUp(self):
        User.objects.create_superuser("directrice", "d@example.com", "motdepasse")
        self.client.force_login(User.objects.get(username="directrice"))

    def test_empty_list_shows_guidance_and_hides_empty_controls(self):
        # Paiements : ce modèle a une navigation par date, qui laissait un
        # trait vide en haut de la carte.
        response = self.client.get("/admin/finance/payment/")
        html = response.content.decode()
        self.assertContains(response, "m-blank")
        self.assertNotIn("toplinks", html)          # navigation par date
        self.assertNotIn("changelist-search", html)
        self.assertNotIn("changelist-filter", html)

    def test_search_without_result_keeps_the_search_box(self):
        response = self.client.get("/admin/finance/payment/", {"q": "introuvable"})
        html = response.content.decode()
        self.assertContains(response, "m-blank")
        self.assertIn("changelist-search", html)    # pour corriger sa recherche
