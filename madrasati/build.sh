#!/usr/bin/env bash
# Script de build pour l'hébergement (Render, Railway…).
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --noinput
python manage.py migrate

# Données de base (idempotent : ne duplique rien si déjà présent)
python manage.py seed

# Compte administrateur initial, si les variables sont définies
if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    python manage.py createsuperuser --noinput || true
fi
