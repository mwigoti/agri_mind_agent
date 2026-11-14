from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0010_vraanalysisjob"),
    ]

    operations = [
        migrations.AddField(
            model_name="advisoryreview",
            name="analysis_result",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="advisory_reviews",
                to="base.analysisresult",
            ),
        ),
    ]
