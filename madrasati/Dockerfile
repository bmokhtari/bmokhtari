FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Migrations + données de base au démarrage, puis serveur
CMD ["sh", "-c", "python manage.py migrate && python manage.py seed && \
     if [ -n \"${DJANGO_SUPERUSER_USERNAME:-}\" ]; then python manage.py createsuperuser --noinput || true; fi && \
     gunicorn config.wsgi:application --bind 0.0.0.0:8000"]
