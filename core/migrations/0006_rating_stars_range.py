from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_remove_exchangerequest_unique_active_direct_exchange_and_more"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="rating",
            constraint=models.CheckConstraint(
                condition=models.Q(stars__gte=1, stars__lte=5),
                name="rating_stars_1_to_5",
            ),
        ),
    ]
