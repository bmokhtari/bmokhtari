"""Natures de faits courantes, et reprise des enregistrements existants."""

from django.db import migrations

# (nom, arabe, négatif, ordre)
COMMON_TYPES = [
    ("Félicitations", "تهنئة", False, 10),
    ("Encouragements", "تشجيعات", False, 11),
    ("Participation active", "مشاركة فعالة", False, 12),
    ("Entraide entre élèves", "التعاون بين التلاميذ", False, 13),
    ("Progrès remarquables", "تقدم ملحوظ", False, 14),
    ("Remarque", "ملاحظة", True, 20),
    ("Bavardage répété", "ثرثرة متكررة", True, 21),
    ("Devoirs non faits", "عدم إنجاز الواجبات", True, 22),
    ("Matériel oublié", "نسيان الأدوات", True, 23),
    ("Retard répété", "تأخر متكرر", True, 24),
    ("Absence injustifiée", "غياب غير مبرر", True, 25),
    ("Téléphone en classe", "استعمال الهاتف داخل القسم", True, 26),
    ("Insolence envers un adulte", "سوء أدب تجاه أحد الأطر", True, 27),
    ("Dégradation de matériel", "إتلاف التجهيزات", True, 28),
    ("Bagarre", "عراك", True, 29),
    ("Avertissement", "إنذار", True, 30),
    ("Retenue", "احتجاز", True, 31),
    ("Exclusion temporaire", "إقصاء مؤقت", True, 32),
]

# Correspondance avec les natures figées de la version précédente.
LEGACY = {
    "commendation": "Félicitations",
    "encouragement": "Encouragements",
    "remark": "Remarque",
    "warning": "Avertissement",
    "detention": "Retenue",
    "exclusion": "Exclusion temporaire",
}


def seed(apps, schema_editor):
    BehaviourType = apps.get_model("students", "BehaviourType")
    BehaviourRecord = apps.get_model("students", "BehaviourRecord")

    for name, name_ar, is_negative, order in COMMON_TYPES:
        BehaviourType.objects.get_or_create(
            name=name,
            defaults={"name_ar": name_ar, "is_negative": is_negative,
                      "order": order},
        )

    by_name = {t.name: t for t in BehaviourType.objects.all()}
    for record in BehaviourRecord.objects.filter(type__isnull=True):
        record.type = by_name[LEGACY.get(record.kind, "Remarque")]
        record.save(update_fields=["type"])


def unseed(apps, schema_editor):
    # Les natures restent : elles peuvent avoir été enrichies par l'équipe.
    pass


class Migration(migrations.Migration):

    dependencies = [("students", "0004_behaviourtype_behaviourrecord_type")]

    operations = [migrations.RunPython(seed, unseed)]
