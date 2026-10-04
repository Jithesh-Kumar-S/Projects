from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_profile_onboarding_complete"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="profile_picture",
            field=models.URLField(blank=True, help_text="Optional link to your profile picture"),
        ),
        migrations.AddField(
            model_name="profile",
            name="experience_level",
            field=models.CharField(
                blank=True,
                choices=[("beginner", "Beginner"), ("intermediate", "Intermediate"), ("advanced", "Advanced")],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="availability",
            field=models.CharField(blank=True, max_length=160),
        ),
    ]
