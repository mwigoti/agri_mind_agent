from django.core.management.base import BaseCommand

from base.dashboard_cache import warmup_all_field_summaries


class Command(BaseCommand):
    help = 'Warm field dashboard summaries on app startup so the page is populated before the first browser visit.'

    def handle(self, *args, **options):
        summaries = warmup_all_field_summaries()
        if not summaries:
            self.stdout.write(self.style.WARNING('No fields found to warm.'))
            return

        self.stdout.write(self.style.SUCCESS(f'Warmed dashboard summaries for {len(summaries)} field(s).'))
        for field_id, payload in summaries.items():
            self.stdout.write(f'- field {field_id}: {payload.get("field_name")} | risk={payload.get("risk_level")} | pending={payload.get("pending_reviews")}')
