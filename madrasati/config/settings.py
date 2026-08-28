"""
Réglages Django pour Madrasati — gestion d'école (Maroc).

Localisation : français par défaut, arabe disponible (RTL pris en charge
par l'interface d'administration Django). Fuseau horaire Casablanca,
monnaie dirham marocain (MAD).
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-change-me-in-production",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# Hébergement infogéré : le nom d'hôte public est fourni par la plateforme.
for _var in ("RENDER_EXTERNAL_HOSTNAME", "RAILWAY_PUBLIC_DOMAIN", "APP_HOSTNAME"):
    _host = os.environ.get(_var)
    if _host and _host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_host)

# Derrière un proxy (Render, Railway, nginx…), TLS est terminé en amont :
# sans cet en-tête Django croit répondre en HTTP, compare l'origine
# « https://… » du navigateur à sa propre vue « http://… » et rejette tout
# formulaire avec « La vérification CSRF a échoué ».
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# Origines autorisées à poster des formulaires : les hôtes connus, plus
# celles fournies explicitement (CSRF_TRUSTED_ORIGINS="https://ecole.ma").
CSRF_TRUSTED_ORIGINS = [
    f"https://{host.lstrip('.')}" if not host.startswith(".")
    else f"https://*{host}"
    for host in ALLOWED_HOSTS
    if host not in ("localhost", "127.0.0.1", "*", "")
]
CSRF_TRUSTED_ORIGINS += [
    origin.strip()
    for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "core",
    "students",
    "finance",
    "hr",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "core.context_processors.school",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("SQLITE_PATH", BASE_DIR / "db.sqlite3"),
    }
}

# En production, DATABASE_URL (ex. Postgres géré par l'hébergeur) prime sur
# SQLite — indispensable sur les plateformes au disque éphémère.
if os.environ.get("DATABASE_URL"):
    import dj_database_url

    DATABASES["default"] = dj_database_url.config(conn_max_age=600)

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation — Maroc
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "fr"

LANGUAGES = [
    ("fr", "Français"),
    ("ar", "العربية"),
]

LOCALE_PATHS = [BASE_DIR / "locale"]

TIME_ZONE = "Africa/Casablanca"

USE_I18N = True
USE_TZ = True

# Format marocain : 1 234,56 (espace pour les milliers, virgule décimale)
USE_THOUSAND_SEPARATOR = True

# Monnaie utilisée dans toute l'application
CURRENCY_CODE = "MAD"
CURRENCY_SYMBOL = "DH"

# En-tête des documents officiels (reçus, bulletins de paie).
# À personnaliser pour chaque établissement, ou via variables d'environnement.
SCHOOL = {
    "name": os.environ.get("SCHOOL_NAME", "Madrasati"),
    "name_ar": os.environ.get("SCHOOL_NAME_AR", "مدرستي"),
    "kind": os.environ.get("SCHOOL_KIND", "Établissement d'enseignement privé"),
    "kind_ar": os.environ.get("SCHOOL_KIND_AR", "مؤسسة للتعليم الخصوصي"),
    "address": os.environ.get("SCHOOL_ADDRESS", "Casablanca, Maroc"),
    "address_ar": os.environ.get("SCHOOL_ADDRESS_AR", "الدار البيضاء، المغرب"),
}

# Durcissement appliqué dès que DEBUG est désactivé (mise en production).
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    X_FRAME_OPTIONS = "DENY"

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
