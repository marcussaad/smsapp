from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ProcessedSMSEvent",
            fields=[
                ("id",             models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message_sid",    models.CharField(db_index=True, max_length=64, unique=True)),
                ("from_number",    models.CharField(max_length=20)),
                ("to_number",      models.CharField(max_length=20)),
                ("body",           models.TextField()),
                ("received_at",    models.DateTimeField(auto_now_add=True)),
                ("status",         models.CharField(
                    choices=[("processed", "Processed"), ("failed", "Failed"), ("skipped", "Skipped")],
                    default="processed",
                    max_length=16,
                )),
                ("failure_reason", models.TextField(blank=True, default="")),
            ],
            options={
                "ordering": ["-received_at"],
            },
        ),
    ]
