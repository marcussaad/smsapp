from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Room",
            fields=[
                ("id",            models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name",          models.CharField(max_length=255)),
                ("twilio_number", models.CharField(blank=True, max_length=20, null=True, unique=True)),
                ("created_at",    models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="Membership",
            fields=[
                ("id",        models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                ("room",      models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="rooms.room")),
                ("user",      models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="users.user")),
            ],
            options={
                "ordering": ["-joined_at"],
                "unique_together": {("user", "room")},
            },
        ),
    ]
