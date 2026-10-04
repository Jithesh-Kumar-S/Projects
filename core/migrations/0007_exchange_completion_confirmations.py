from django.db import migrations, models


def preserve_existing_completed(apps, schema_editor):
    ExchangeRequest = apps.get_model("core", "ExchangeRequest")
    ExchangeRequest.objects.filter(status="completed").update(
        requester_confirmed=True,
        provider_confirmed=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_rating_stars_range"),
    ]

    operations = [
        migrations.AddField(
            model_name="exchangerequest",
            name="requester_confirmed",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="exchangerequest",
            name="provider_confirmed",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(preserve_existing_completed, migrations.RunPython.noop),
    ]
