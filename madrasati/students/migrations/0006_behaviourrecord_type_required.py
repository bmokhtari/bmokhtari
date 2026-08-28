"""La nature devient obligatoire ; l'ancien champ figé disparaît."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("students", "0005_seed_behaviour_types")]

    operations = [
        # 0005 a déjà attribué une nature à chaque fait existant.
        migrations.AlterField(
            model_name="behaviourrecord",
            name="type",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="records", to="students.behaviourtype",
                verbose_name="nature"),
        ),
        migrations.RemoveField(model_name="behaviourrecord", name="kind"),
    ]
