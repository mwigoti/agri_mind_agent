from django.core.management.base import BaseCommand

from base.tasks import refresh_stale_field_analysis


class Command(BaseCommand):
    help = 'Refresh stale Earth Engine crop analysis records when they are older than the configured threshold.'

    def add_arguments(self, parser):
        parser.add_argument('--max-age-days', type=int, default=12)
        parser.add_argument('--limit', type=int, default=None)
        parser.add_argument('--dry-run', action='store_true', help='List stale records without running the pipeline.')

    def handle(self, *args, **options):
        max_age_days = options['max_age_days']
        dry_run = options['dry_run']
        limit = options['limit']

        summary = refresh_stale_field_analysis(
            max_age_days=max_age_days,
            dry_run=dry_run,
            limit=limit,
        )

        refreshed = summary.get('refreshed', [])
        if not refreshed:
            self.stdout.write(self.style.SUCCESS(f'No stale field analyses older than {max_age_days} days were found.'))
            return

        self.stdout.write(self.style.SUCCESS(f'Found {len(refreshed)} stale analysis record(s) to refresh.'))
        for item in refreshed:
            if item.get('dry_run'):
                self.stdout.write(
                    f"- DRY RUN: {item['field_name']} ({item['crop_name']}) | activity {item['activity_id']} | age > {max_age_days} days"
                )
                continue

            yield_label = item.get('yield_t_ha')
            ndvi_label = item.get('ndvi_latest')
            self.stdout.write(
                f"- {item['field_name']} | activity {item['activity_id']} | status={item.get('pipeline_status', 'unknown')} | "
                f"yield={yield_label if yield_label is not None else 'n/a'} t/ha | NDVI={ndvi_label if ndvi_label is not None else 'n/a'}"
            )
