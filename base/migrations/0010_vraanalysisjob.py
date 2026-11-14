from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0009_fieldmetric_advisoryreview_advisorycomment"),
    ]

    operations = [
        migrations.CreateModel(
            name="VRAAnalysisJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("request_data", models.JSONField(default=dict)),
                ("result_data", models.JSONField(blank=True, default=dict)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("running", "Running"), ("done", "Done"), ("error", "Error")], default="queued", max_length=20)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("field", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vra_analysis_jobs", to="base.field")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
